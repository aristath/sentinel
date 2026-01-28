"""Trading job implementations."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import timedelta

from sentinel.jobs.types import BaseJob, MarketTiming
from sentinel.security import Security
from sentinel.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class CheckMarketsJob(BaseJob):
    """Check which markets are open and execute pending trades."""

    _broker: object = field(default=None, repr=False)
    _db: object = field(default=None, repr=False)
    _planner: object = field(default=None, repr=False)

    def __init__(self, broker, db, planner):
        super().__init__(
            _id="trading:check_markets",
            _job_type="trading:check_markets",
            _timeout=timedelta(minutes=10),
            _market_timing=MarketTiming.DURING_MARKET_OPEN,
        )
        self._broker = broker
        self._db = db
        self._planner = planner

    async def execute(self) -> None:
        """Execute market check and trading."""
        if not self._broker.connected:
            logger.warning("Broker not connected, skipping market check")
            return

        # Get market status
        market_data = await self._broker.get_market_status("*")
        if not market_data:
            logger.warning("Could not get market status")
            return

        markets = market_data.get("m", [])
        open_markets = {m.get("n2"): m for m in markets if m.get("s") == "OPEN"}

        if not open_markets:
            logger.info("No markets currently open")
            return

        logger.info(f"Open markets: {', '.join(open_markets.keys())}")

        # Get securities and check if their market is open
        securities = await self._db.get_all_securities(active_only=True)
        open_securities = []

        for sec in securities:
            data = sec.get("data")
            if data:
                try:
                    sec_data = json.loads(data) if isinstance(data, str) else data
                    market_id = sec_data.get("mrkt", {}).get("mkt_id")
                    for m in markets:
                        if str(m.get("i")) == str(market_id) and m.get("s") == "OPEN":
                            open_securities.append(sec["symbol"])
                            break
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    pass

        if not open_securities:
            logger.info("No securities with open markets")
            return

        logger.info(f"Securities with open markets: {', '.join(open_securities)}")

        # Check for pending trades
        recommendations = await self._planner.get_recommendations()
        actionable = [r for r in recommendations if r.symbol in open_securities]

        if not actionable:
            logger.info("No actionable trades for open markets")
            return

        # Log recommendations (actual execution requires live mode)
        for rec in actionable:
            logger.info(
                f"Ready to {rec.action.upper()}: {rec.quantity} x {rec.symbol} @ {rec.price:.2f} {rec.currency}"
            )


@dataclass
class RebalanceJob(BaseJob):
    """Check if portfolio needs rebalancing and generate recommendations."""

    _planner: object = field(default=None, repr=False)

    def __init__(self, planner):
        super().__init__(
            _id="trading:rebalance",
            _job_type="trading:rebalance",
            _timeout=timedelta(minutes=15),
            _market_timing=MarketTiming.ANY_TIME,
        )
        self._planner = planner

    async def execute(self) -> None:
        """Execute rebalance check."""
        summary = await self._planner.get_rebalance_summary()

        if summary["needs_rebalance"]:
            logger.warning(f"Portfolio needs rebalancing! Total deviation: {summary['total_deviation']:.1%}")

            recommendations = await self._planner.get_recommendations()
            for rec in recommendations:
                logger.warning(f"  {rec.action.upper()} {rec.symbol}: €{abs(rec.value_delta_eur):.0f} ({rec.reason})")
        else:
            logger.info("Portfolio is balanced")


@dataclass
class ExecuteTradesJob(BaseJob):
    """Execute pending trade recommendations.

    Only executes in LIVE trading mode. In research mode, logs what would happen.
    Checks market status before executing and only trades securities with open markets.
    """

    _broker: object = field(default=None, repr=False)
    _db: object = field(default=None, repr=False)
    _planner: object = field(default=None, repr=False)

    def __init__(self, broker, db, planner):
        super().__init__(
            _id="trading:execute",
            _job_type="trading:execute",
            _timeout=timedelta(minutes=15),
            _market_timing=MarketTiming.DURING_MARKET_OPEN,
        )
        self._broker = broker
        self._db = db
        self._planner = planner

    async def execute(self) -> None:
        """Execute pending trades."""
        if not self._broker.connected:
            logger.warning("Broker not connected, skipping trade execution")
            return

        # Check trading mode
        settings = Settings()
        trading_mode = await settings.get("trading_mode", "research")

        if trading_mode != "live":
            logger.info(f"Trading mode is '{trading_mode}', skipping actual execution")
            # Still log what would happen
            await self._log_pending_trades()
            return

        # Get market status to find open markets
        open_symbols = await self._get_open_market_symbols()
        if not open_symbols:
            logger.info("No securities with open markets, skipping execution")
            return

        # Get recommendations
        recommendations = await self._planner.get_recommendations()
        if not recommendations:
            logger.info("No trade recommendations")
            return

        # Filter to actionable (open markets only)
        actionable = [r for r in recommendations if r.symbol in open_symbols]
        if not actionable:
            logger.info("No actionable trades for open markets")
            return

        # Sort by priority (highest first) and execute sells before buys
        sells = sorted([r for r in actionable if r.action == "sell"], key=lambda x: -x.priority)
        buys = sorted([r for r in actionable if r.action == "buy"], key=lambda x: -x.priority)

        executed = []
        failed = []

        # Execute sells first (to free up cash for buys)
        for rec in sells:
            success = await self._execute_trade(rec)
            if success:
                executed.append(rec)
            else:
                failed.append(rec)

        # Then execute buys
        for rec in buys:
            success = await self._execute_trade(rec)
            if success:
                executed.append(rec)
            else:
                failed.append(rec)

        # Log summary
        if executed:
            logger.info(f"Executed {len(executed)} trades successfully")
        if failed:
            logger.warning(f"Failed to execute {len(failed)} trades")

    async def _execute_trade(self, rec) -> bool:
        """Execute a single trade recommendation. Returns True if successful."""
        try:
            security = Security(rec.symbol)
            await security.load()

            if rec.action == "sell":
                order_id = await security.sell(rec.quantity)
                action_str = "SELL"
            else:
                order_id = await security.buy(rec.quantity)
                action_str = "BUY"

            if order_id:
                logger.info(
                    f"Executed {action_str}: {rec.quantity} x {rec.symbol} "
                    f"@ {rec.price:.2f} {rec.currency} (order: {order_id})"
                )
                return True
            else:
                logger.error(f"Failed to {action_str} {rec.symbol}: no order ID returned")
                return False

        except Exception as e:
            logger.error(f"Failed to execute {rec.action} {rec.symbol}: {e}")
            return False

    async def _get_open_market_symbols(self) -> set[str]:
        """Get symbols whose markets are currently open."""
        market_data = await self._broker.get_market_status("*")
        if not market_data:
            return set()

        markets = market_data.get("m", [])
        open_market_ids = {str(m.get("i")) for m in markets if m.get("s") == "OPEN"}

        if not open_market_ids:
            return set()

        securities = await self._db.get_all_securities(active_only=True)
        open_symbols = set()

        for sec in securities:
            data = sec.get("data")
            if data:
                try:
                    sec_data = json.loads(data) if isinstance(data, str) else data
                    market_id = str(sec_data.get("mrkt", {}).get("mkt_id"))
                    if market_id in open_market_ids:
                        open_symbols.add(sec["symbol"])
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    pass

        return open_symbols

    async def _log_pending_trades(self) -> None:
        """Log what trades would be executed (for research mode)."""
        recommendations = await self._planner.get_recommendations()
        if not recommendations:
            logger.info("No pending trade recommendations")
            return

        open_symbols = await self._get_open_market_symbols()

        for rec in recommendations:
            market_status = "OPEN" if rec.symbol in open_symbols else "CLOSED"
            logger.info(
                f"[RESEARCH] Would {rec.action.upper()}: {rec.quantity} x {rec.symbol} "
                f"@ {rec.price:.2f} {rec.currency} (market: {market_status})"
            )


@dataclass
class RefreshPlanJob(BaseJob):
    """Refresh the trading plan by clearing caches and regenerating recommendations.

    Clears the planner caches and recalculates:
    - Ideal portfolio allocations
    - Trade recommendations
    """

    _db: object = field(default=None, repr=False)
    _planner: object = field(default=None, repr=False)

    def __init__(self, db, planner):
        super().__init__(
            _id="planning:refresh",
            _job_type="planning:refresh",
            _timeout=timedelta(minutes=10),
            _market_timing=MarketTiming.ANY_TIME,
        )
        self._db = db
        self._planner = planner

    async def execute(self) -> None:
        """Clear caches and regenerate plan."""
        # Clear planner-related caches
        cleared = await self._db.cache_clear("planner:")
        logger.info(f"Cleared {cleared} planner cache entries")

        # Regenerate ideal portfolio (this will cache the result)
        ideal = await self._planner.calculate_ideal_portfolio()
        logger.info(f"Recalculated ideal portfolio with {len(ideal)} securities")

        # Regenerate recommendations (this will cache the result)
        recommendations = await self._planner.get_recommendations()
        buys = [r for r in recommendations if r.action == "buy"]
        sells = [r for r in recommendations if r.action == "sell"]
        logger.info(f"Generated {len(recommendations)} recommendations: {len(buys)} buys, {len(sells)} sells")
