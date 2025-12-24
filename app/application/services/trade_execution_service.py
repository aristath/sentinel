"""Trade execution application service.

Orchestrates trade execution via Tradernet and records trades.
"""

import logging
from typing import List, Optional
from datetime import datetime
import aiosqlite

from app.domain.repositories import TradeRepository, PositionRepository
from app.services.allocator import TradeRecommendation
from app.services.tradernet import get_tradernet_client
from app.database import transaction
from app.infrastructure.events import emit, SystemEvent
from app.application.services.currency_exchange_service import (
    CurrencyExchangeService,
    get_currency_exchange_service,
)

logger = logging.getLogger(__name__)


class TradeExecutionService:
    """Application service for trade execution."""

    def __init__(
        self,
        trade_repo: TradeRepository,
        db: Optional[aiosqlite.Connection] = None,
        position_repo: Optional[PositionRepository] = None
    ):
        self._trade_repo = trade_repo
        self._position_repo = position_repo
        self._db = db
        # Try to get db from repository if it has one
        if db is None and hasattr(trade_repo, 'db'):
            self._db = trade_repo.db

    async def execute_trades(
        self,
        trades: List[TradeRecommendation],
        use_transaction: bool = True,
        currency_balances: Optional[dict[str, float]] = None,
        auto_convert_currency: bool = False,
        source_currency: str = "EUR"
    ) -> List[dict]:
        """
        Execute a list of trade recommendations via Tradernet.

        Args:
            trades: List of trade recommendations to execute
            use_transaction: If True and db is available, wrap all trades in a transaction
            currency_balances: Per-currency cash balances for validation (optional)
            auto_convert_currency: If True, automatically convert currency before buying
            source_currency: Currency to convert from when auto_convert is enabled (default: EUR)

        Returns:
            List of execution results with status for each trade
        """
        client = get_tradernet_client()

        if not client.is_connected:
            if not client.connect():
                emit(SystemEvent.ERROR_OCCURRED, message="TRADE FAIL")
                raise ConnectionError("Failed to connect to Tradernet")

        # Get currency exchange service if auto-convert is enabled
        currency_service = get_currency_exchange_service() if auto_convert_currency else None

        # Use transaction if available and requested
        if use_transaction and self._db:
            async with transaction(self._db) as tx_db:
                return await self._execute_trades_internal(
                    trades, client, auto_commit=False, currency_balances=currency_balances,
                    currency_service=currency_service, source_currency=source_currency
                )
        else:
            return await self._execute_trades_internal(
                trades, client, auto_commit=True, currency_balances=currency_balances,
                currency_service=currency_service, source_currency=source_currency
            )

    async def _execute_trades_internal(
        self,
        trades: List[TradeRecommendation],
        client,
        auto_commit: bool = True,
        currency_balances: Optional[dict[str, float]] = None,
        currency_service: Optional[CurrencyExchangeService] = None,
        source_currency: str = "EUR"
    ) -> List[dict]:
        """Internal method to execute trades."""
        results = []
        skipped_count = 0
        converted_currencies = set()  # Track which currencies we've converted to

        for trade in trades:
            try:
                # Check currency balance before executing (BUY orders only)
                if trade.side.upper() == "BUY":
                    required = trade.quantity * trade.estimated_price
                    trade_currency = trade.currency or "EUR"

                    # If auto-convert is enabled and currency differs from source
                    if currency_service and trade_currency != source_currency:
                        # Check if we need to convert
                        available = currency_balances.get(trade_currency, 0) if currency_balances else 0

                        if available < required:
                            # Only convert once per currency per batch
                            if trade_currency not in converted_currencies:
                                logger.info(
                                    f"Auto-converting {source_currency} to {trade_currency} "
                                    f"for {trade.symbol} (need {required:.2f} {trade_currency})"
                                )

                                # Ensure we have enough balance
                                if currency_service.ensure_balance(
                                    trade_currency, required, source_currency
                                ):
                                    converted_currencies.add(trade_currency)
                                    logger.info(f"Currency conversion successful for {trade_currency}")
                                else:
                                    logger.warning(
                                        f"Currency conversion failed for {trade.symbol}: "
                                        f"could not convert {source_currency} to {trade_currency}"
                                    )
                                    results.append({
                                        "symbol": trade.symbol,
                                        "status": "skipped",
                                        "error": f"Currency conversion failed ({source_currency} to {trade_currency})",
                                    })
                                    skipped_count += 1
                                    continue

                    # Validate balance if currency_balances provided and no auto-convert
                    elif currency_balances is not None:
                        available = currency_balances.get(trade_currency, 0)

                        if available < required:
                            logger.warning(
                                f"Skipping {trade.symbol}: insufficient {trade_currency} balance "
                                f"(need {required:.2f}, have {available:.2f})"
                            )
                            results.append({
                                "symbol": trade.symbol,
                                "status": "skipped",
                                "error": f"Insufficient {trade_currency} balance (need {required:.2f}, have {available:.2f})",
                            })
                            skipped_count += 1
                            continue

                # For SELL orders, validate quantity against position
                if trade.side.upper() == "SELL" and self._position_repo:
                    position = await self._position_repo.get_by_symbol(trade.symbol)
                    if not position:
                        logger.warning(f"Skipping SELL {trade.symbol}: no position found")
                        results.append({
                            "symbol": trade.symbol,
                            "status": "skipped",
                            "error": "No position found for SELL order",
                        })
                        skipped_count += 1
                        continue

                    if trade.quantity > position.quantity:
                        logger.warning(
                            f"Skipping SELL {trade.symbol}: quantity {trade.quantity} "
                            f"> position {position.quantity}"
                        )
                        results.append({
                            "symbol": trade.symbol,
                            "status": "skipped",
                            "error": f"SELL quantity ({trade.quantity}) exceeds position ({position.quantity})",
                        })
                        skipped_count += 1
                        continue

                result = client.place_order(
                    symbol=trade.symbol,
                    side=trade.side,
                    quantity=trade.quantity,
                )

                if result:
                    # Note: Trade recording is handled by sync_trades job
                    # which fetches executed trades from Tradernet API.
                    # This prevents sync issues if user cancels orders externally.

                    # For successful SELL orders, update last_sold_at in positions
                    if trade.side.upper() == "SELL" and self._position_repo:
                        if hasattr(self._position_repo, 'update_last_sold_at'):
                            await self._position_repo.update_last_sold_at(
                                trade.symbol, auto_commit=auto_commit
                            )
                            logger.info(f"Updated last_sold_at for {trade.symbol}")

                    results.append({
                        "symbol": trade.symbol,
                        "status": "success",
                        "order_id": result.order_id,
                        "side": trade.side,
                    })
                else:
                    emit(SystemEvent.ERROR_OCCURRED, message="ORDER FAIL")
                    results.append({
                        "symbol": trade.symbol,
                        "status": "failed",
                        "error": "Order placement returned None",
                    })

            except Exception as e:
                logger.error(f"Failed to execute trade for {trade.symbol}: {e}")
                emit(SystemEvent.ERROR_OCCURRED, message="ORDER FAIL")
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
                emit(SystemEvent.ERROR_OCCURRED, message="LOW FX BAL")

        return results
