"""
Daily P&L Tracker - Tiered circuit breaker for volatile days.

Tracks daily portfolio performance and halts trading based on loss thresholds:
- Normal (> -2%): Allow all trading
- Moderate drawdown (-2% to -5%): Block sells, allow buys (buy the dip)
- Severe crash (< -5%): Block all trading (wait for clarity)
"""

import logging
from datetime import datetime
from typing import Optional, Tuple

from app.core.database.manager import get_db_manager
from app.domain.constants import DAILY_LOSS_FULL_HALT, DAILY_LOSS_SELL_HALT

logger = logging.getLogger(__name__)


class DailyPnLTracker:
    """Track daily P&L with tiered circuit breaker for trading decisions."""

    def __init__(self):
        self._db_manager = get_db_manager()
        self._cached_pnl: Optional[float] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 60  # Cache for 1 minute

    async def get_start_of_day_value(self) -> Optional[float]:
        """
        Get portfolio value from start of trading day.

        Returns the most recent snapshot before today, or yesterday's snapshot.
        """
        today = datetime.now().strftime("%Y-%m-%d")

        # Get the most recent snapshot before today (snapshots.db)
        row = await self._db_manager.snapshots.fetchone(
            """
            SELECT total_value, date
            FROM portfolio_snapshots
            WHERE date < ?
            ORDER BY date DESC
            LIMIT 1
            """,
            (today,),
        )

        if row:
            return row["total_value"]

        # Fallback: get today's earliest snapshot if no previous day exists
        row = await self._db_manager.snapshots.fetchone(
            """
            SELECT total_value
            FROM portfolio_snapshots
            WHERE date = ?
            """,
            (today,),
        )

        return row["total_value"] if row else None

    async def get_current_value(self) -> float:
        """Get current portfolio value from positions."""
        row = await self._db_manager.state.fetchone(
            "SELECT SUM(market_value_eur) as total FROM positions"
        )
        return row["total"] if row and row["total"] else 0.0

    async def get_daily_pnl(self) -> Optional[float]:
        """
        Calculate today's P&L as a percentage.

        Returns:
            P&L percentage (e.g., -0.03 for -3%), or None if cannot calculate.
        """
        # Check cache
        now = datetime.now()
        if (
            self._cached_pnl is not None
            and self._cache_time is not None
            and (now - self._cache_time).seconds < self._cache_ttl_seconds
        ):
            return self._cached_pnl

        start_value = await self.get_start_of_day_value()
        if not start_value or start_value <= 0:
            logger.debug("No start-of-day value available for P&L calculation")
            return None

        current_value = await self.get_current_value()
        if current_value <= 0:
            logger.debug("No current portfolio value available")
            return None

        pnl = (current_value - start_value) / start_value

        # Update cache
        self._cached_pnl = pnl
        self._cache_time = now

        logger.debug(
            f"Daily P&L: {pnl*100:.2f}% "
            f"(start: {start_value:.2f}, current: {current_value:.2f})"
        )

        return pnl

    async def can_buy(self) -> Tuple[bool, str]:
        """
        Check if buying is allowed based on daily P&L.

        Returns:
            Tuple of (allowed, reason).
            Buys are blocked only during severe crashes (> 5% loss).
        """
        pnl = await self.get_daily_pnl()

        if pnl is None:
            # Cannot determine P&L, allow trading with caution
            return True, "P&L unknown"

        if pnl <= -DAILY_LOSS_FULL_HALT:
            return (
                False,
                f"Portfolio down {abs(pnl)*100:.1f}% today (full halt at {DAILY_LOSS_FULL_HALT*100:.0f}%)",
            )

        if pnl <= -DAILY_LOSS_SELL_HALT:
            # Moderate drawdown - buys still allowed (buy the dip)
            return True, f"Buying dip: portfolio down {abs(pnl)*100:.1f}%"

        return True, "Normal trading"

    async def can_sell(self) -> Tuple[bool, str]:
        """
        Check if selling is allowed based on daily P&L.

        Returns:
            Tuple of (allowed, reason).
            Sells are blocked during moderate drawdowns (> 2% loss).
        """
        pnl = await self.get_daily_pnl()

        if pnl is None:
            # Cannot determine P&L, allow trading with caution
            return True, "P&L unknown"

        if pnl <= -DAILY_LOSS_SELL_HALT:
            return (
                False,
                f"Sells blocked: portfolio down {abs(pnl)*100:.1f}% (halt at {DAILY_LOSS_SELL_HALT*100:.0f}%)",
            )

        return True, "Normal trading"

    async def get_trading_status(self) -> dict:
        """
        Get comprehensive trading status based on daily P&L.

        Returns:
            Dict with:
            - pnl: Daily P&L percentage
            - pnl_display: Formatted P&L string
            - can_buy: Whether buys are allowed
            - can_sell: Whether sells are allowed
            - status: 'normal', 'dip_buying', or 'halted'
            - reason: Human-readable explanation
        """
        pnl = await self.get_daily_pnl()

        if pnl is None:
            return {
                "pnl": None,
                "pnl_display": "N/A",
                "can_buy": True,
                "can_sell": True,
                "status": "unknown",
                "reason": "Cannot calculate daily P&L (no previous snapshot)",
            }

        can_buy, buy_reason = await self.can_buy()
        can_sell, sell_reason = await self.can_sell()

        if pnl <= -DAILY_LOSS_FULL_HALT:
            status = "halted"
            reason = (
                f"Trading halted: portfolio down {abs(pnl)*100:.1f}% (severe drawdown)"
            )
        elif pnl <= -DAILY_LOSS_SELL_HALT:
            status = "dip_buying"
            reason = f"Dip buying mode: portfolio down {abs(pnl)*100:.1f}% (buys allowed, sells blocked)"
        else:
            status = "normal"
            if pnl >= 0:
                reason = f"Normal trading: portfolio up {pnl*100:.1f}%"
            else:
                reason = f"Normal trading: portfolio down {abs(pnl)*100:.1f}%"

        return {
            "pnl": pnl,
            "pnl_display": f"{pnl*100:+.2f}%",
            "can_buy": can_buy,
            "can_sell": can_sell,
            "status": status,
            "reason": reason,
        }


# Singleton instance
_tracker: Optional[DailyPnLTracker] = None


def get_daily_pnl_tracker() -> DailyPnLTracker:
    """Get or create the singleton DailyPnLTracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = DailyPnLTracker()
    return _tracker
