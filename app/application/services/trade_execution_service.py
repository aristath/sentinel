"""Trade execution application service.

Orchestrates trade execution via Tradernet and records trades.
"""

import logging
from typing import List, Optional
from datetime import datetime
import aiosqlite

from app.domain.repositories import TradeRepository, Trade
from app.services.allocator import TradeRecommendation
from app.services.tradernet import get_tradernet_client
from app.database import transaction
from app.infrastructure.hardware.led_display import get_led_display

logger = logging.getLogger(__name__)


class TradeExecutionService:
    """Application service for trade execution."""

    def __init__(self, trade_repo: TradeRepository, db: Optional[aiosqlite.Connection] = None):
        self._trade_repo = trade_repo
        self._db = db
        # Try to get db from repository if it has one
        if db is None and hasattr(trade_repo, 'db'):
            self._db = trade_repo.db

    async def execute_trades(
        self,
        trades: List[TradeRecommendation],
        use_transaction: bool = True,
        currency_balances: Optional[dict[str, float]] = None
    ) -> List[dict]:
        """
        Execute a list of trade recommendations via Tradernet.

        Args:
            trades: List of trade recommendations to execute
            use_transaction: If True and db is available, wrap all trades in a transaction
            currency_balances: Per-currency cash balances for validation (optional)

        Returns:
            List of execution results with status for each trade
        """
        client = get_tradernet_client()

        if not client.is_connected:
            if not client.connect():
                display = get_led_display()
                if display.is_connected:
                    display.show_error("TRADE FAIL")
                raise ConnectionError("Failed to connect to Tradernet")

        # Use transaction if available and requested
        if use_transaction and self._db:
            async with transaction(self._db) as tx_db:
                return await self._execute_trades_internal(
                    trades, client, auto_commit=False, currency_balances=currency_balances
                )
        else:
            return await self._execute_trades_internal(
                trades, client, auto_commit=True, currency_balances=currency_balances
            )

    async def _execute_trades_internal(
        self,
        trades: List[TradeRecommendation],
        client,
        auto_commit: bool = True,
        currency_balances: Optional[dict[str, float]] = None
    ) -> List[dict]:
        """Internal method to execute trades."""
        results = []
        skipped_count = 0

        for trade in trades:
            try:
                # Check currency balance before executing (BUY orders only)
                if trade.side.upper() == "BUY" and currency_balances is not None:
                    required = trade.quantity * trade.estimated_price
                    available = currency_balances.get(trade.currency, 0)

                    if available < required:
                        logger.warning(
                            f"Skipping {trade.symbol}: insufficient {trade.currency} balance "
                            f"(need {required:.2f}, have {available:.2f})"
                        )
                        results.append({
                            "symbol": trade.symbol,
                            "status": "skipped",
                            "error": f"Insufficient {trade.currency} balance (need {required:.2f}, have {available:.2f})",
                        })
                        skipped_count += 1
                        continue

                result = client.place_order(
                    symbol=trade.symbol,
                    side=trade.side,
                    quantity=trade.quantity,
                )

                if result:
                    # Record trade using repository
                    trade_record = Trade(
                        symbol=trade.symbol,
                        side=trade.side,
                        quantity=trade.quantity,
                        price=result.price or trade.estimated_price,
                        executed_at=datetime.now(),
                        order_id=result.order_id,
                    )
                    # Only auto-commit if not in transaction
                    if hasattr(self._trade_repo, 'create'):
                        # Check if create method supports auto_commit parameter
                        import inspect
                        sig = inspect.signature(self._trade_repo.create)
                        if 'auto_commit' in sig.parameters:
                            await self._trade_repo.create(trade_record, auto_commit=auto_commit)
                        else:
                            await self._trade_repo.create(trade_record)
                    else:
                        await self._trade_repo.create(trade_record)

                    results.append({
                        "symbol": trade.symbol,
                        "status": "success",
                        "order_id": result.order_id,
                    })
                else:
                    display = get_led_display()
                    if display.is_connected:
                        display.show_error("ORDER FAIL")
                    results.append({
                        "symbol": trade.symbol,
                        "status": "failed",
                        "error": "Order placement returned None",
                    })

            except Exception as e:
                logger.error(f"Failed to execute trade for {trade.symbol}: {e}")
                display = get_led_display()
                if display.is_connected:
                    display.show_error("ORDER FAIL")
                results.append({
                    "symbol": trade.symbol,
                    "status": "error",
                    "error": str(e),
                })
                # Note: If place_order() succeeded but DB write failed, the trade
                # is executed externally but not recorded. We log this but continue.
                # The transaction ensures DB consistency for recorded trades.

        # Show LED warning if trades were skipped due to insufficient currency balance
        if skipped_count > 0:
            logger.warning(f"Skipped {skipped_count} trades due to insufficient currency balance")
            if skipped_count >= 2:
                display = get_led_display()
                if display.is_connected:
                    display.show_error("LOW FX BAL")

        return results
