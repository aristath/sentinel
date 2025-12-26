"""Trade execution application service.

Orchestrates trade execution via Tradernet and records trades.
"""

import logging
from typing import List, Optional

from app.application.services.currency_exchange_service import (
    CurrencyExchangeService,
)
from app.application.services.trade_execution.trade_recorder import record_trade
from app.domain.models import Recommendation, Trade
from app.domain.repositories.protocols import IPositionRepository, ITradeRepository
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.value_objects.currency import Currency
from app.infrastructure.events import SystemEvent, emit
from app.infrastructure.external.tradernet import TradernetClient
from app.infrastructure.hardware.display_service import set_error, set_processing

logger = logging.getLogger(__name__)


async def _check_buy_cooldown(
    trade, recently_bought: set, cooldown_days: int
) -> Optional[dict]:
    """Check if BUY trade is in cooldown period."""
    if trade.symbol in recently_bought:
        logger.warning(
            f"SAFETY BLOCK: {trade.symbol} in cooldown period, refusing to execute"
        )
        return {
            "symbol": trade.symbol,
            "status": "blocked",
            "error": f"Cooldown active (bought within {cooldown_days} days)",
        }
    return None


async def _handle_buy_currency(
    trade,
    currency_balances: Optional[dict],
    currency_service: Optional[CurrencyExchangeService],
    source_currency: str,
    converted_currencies: set,
) -> Optional[dict]:
    """Handle currency validation and conversion for BUY orders."""
    required = trade.quantity * trade.estimated_price
    trade_currency = trade.currency or Currency.EUR

    if currency_service and trade_currency != source_currency:
        available = currency_balances.get(trade_currency, 0) if currency_balances else 0

        if available < required:
            if trade_currency not in converted_currencies:
                logger.info(
                    f"Auto-converting {source_currency} to {trade_currency} "
                    f"for {trade.symbol} (need {required:.2f} {trade_currency})"
                )
                set_processing(f"CONVERTING {source_currency} TO {trade_currency}...")

                if currency_service.ensure_balance(
                    trade_currency, required, source_currency
                ):
                    converted_currencies.add(trade_currency)
                    logger.info(f"Currency conversion successful for {trade_currency}")
                    set_processing("CURRENCY CONVERSION COMPLETE")
                else:
                    logger.warning(
                        f"Currency conversion failed for {trade.symbol}: "
                        f"could not convert {source_currency} to {trade_currency}"
                    )
                    return {
                        "symbol": trade.symbol,
                        "status": "skipped",
                        "error": f"Currency conversion failed ({source_currency} to {trade_currency})",
                    }

    elif currency_balances is not None:
        available = currency_balances.get(trade_currency, 0)
        if available < required:
            logger.warning(
                f"Skipping {trade.symbol}: insufficient {trade_currency} balance "
                f"(need {required:.2f}, have {available:.2f})"
            )
            return {
                "symbol": trade.symbol,
                "status": "skipped",
                "error": f"Insufficient {trade_currency} balance (need {required:.2f}, have {available:.2f})",
            }

    return None


async def _validate_sell_order(trade, position_repo) -> Optional[dict]:
    """Validate SELL order against position."""
    if not position_repo:
        return None

    position = await position_repo.get_by_symbol(trade.symbol)
    if not position:
        logger.warning(f"Skipping SELL {trade.symbol}: no position found")
        return {
            "symbol": trade.symbol,
            "status": "skipped",
            "error": "No position found for SELL order",
        }

    if trade.quantity > position.quantity:
        logger.warning(
            f"Skipping SELL {trade.symbol}: quantity {trade.quantity} "
            f"> position {position.quantity}"
        )
        return {
            "symbol": trade.symbol,
            "status": "skipped",
            "error": f"SELL quantity ({trade.quantity}) exceeds position ({position.quantity})",
        }

    return None


async def _check_pending_orders(trade, client, trade_repo) -> bool:
    """Check if there are pending orders for this symbol."""
    has_pending = client.has_pending_order_for_symbol(trade.symbol)

    if not has_pending and trade.side.upper() == "SELL":
        try:
            has_recent = await trade_repo.has_recent_sell_order(trade.symbol, hours=2)
            if has_recent:
                has_pending = True
                logger.info(f"Found recent SELL order in database for {trade.symbol}")
        except Exception as e:
            logger.warning(f"Failed to check database for recent sell orders: {e}")

    if has_pending:
        logger.warning(f"SAFETY BLOCK: {trade.symbol} has pending order, refusing to execute")

    return has_pending


async def _execute_single_trade(trade, client) -> Optional[dict]:
    """Execute a single trade and return result."""
    side_text = "BUYING" if trade.side.upper() == "BUY" else "SELLING"
    value = int(trade.quantity * trade.estimated_price)
    symbol_short = trade.symbol.split(".")[0]
    set_processing(f"{side_text} {symbol_short} €{value}")

    result = client.place_order(
        symbol=trade.symbol,
        side=trade.side,
        quantity=trade.quantity,
    )

    if result:
        return {
            "symbol": trade.symbol,
            "status": "success",
            "order_id": result.order_id,
            "side": trade.side,
            "price": result.price,
            "result": result,
        }
    else:
        error_msg = "ORDER PLACEMENT FAILED"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_error(error_msg)
        return {
            "symbol": trade.symbol,
            "status": "failed",
            "error": "Order placement returned None",
        }


class TradeExecutionService:
    """Application service for trade execution."""

    def __init__(
        self,
        trade_repo: ITradeRepository,
        position_repo: IPositionRepository,
        tradernet_client: TradernetClient,
        currency_exchange_service: CurrencyExchangeService,
        exchange_rate_service: ExchangeRateService,
    ):
        self._trade_repo = trade_repo
        self._position_repo = position_repo
        self._tradernet_client = tradernet_client
        self._currency_exchange_service = currency_exchange_service
        self._exchange_rate_service = exchange_rate_service

    async def record_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        order_id: Optional[str] = None,
        currency: Optional[str] = None,
        estimated_price: Optional[float] = None,
        source: str = "tradernet",
    ) -> Optional[Trade]:
        """
        Record a trade in the database.

        Handles duplicate order_id checking and creates Trade record.

        Args:
            symbol: Stock symbol
            side: Trade side (BUY or SELL)
            quantity: Trade quantity
            price: Execution price (use estimated_price if price <= 0)
            order_id: Broker order ID (optional)
            currency: Trade currency (optional)
            estimated_price: Estimated price to use if price <= 0 (optional)
            source: Trade source (default: "tradernet")

        Returns:
            Trade object if recorded successfully, None if duplicate or error
        """
        return await record_trade(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            trade_repo=self._trade_repo,
            position_repo=self._position_repo,
            exchange_rate_service=self._exchange_rate_service,
            order_id=order_id,
            currency=currency,
            estimated_price=estimated_price,
            source=source,
        )

    async def execute_trades(
        self,
        trades: List[Recommendation],
        currency_balances: Optional[dict[str, float]] = None,
        auto_convert_currency: bool = False,
        source_currency: str = Currency.EUR,
    ) -> List[dict]:
        """
        Execute a list of trade recommendations via Tradernet.

        Args:
            trades: List of trade recommendations to execute
            currency_balances: Per-currency cash balances for validation (optional)
            auto_convert_currency: If True, automatically convert currency before buying
            source_currency: Currency to convert from when auto_convert is enabled (default: EUR)

        Returns:
            List of execution results with status for each trade
        """
        client = self._tradernet_client

        if not client.is_connected:
            if not client.connect():
                error_msg = "TRADE EXECUTION FAILED"
                emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
                set_error(error_msg)
                raise ConnectionError("Failed to connect to Tradernet")

        # Use currency exchange service if auto-convert is enabled
        currency_service = (
            self._currency_exchange_service if auto_convert_currency else None
        )

        return await self._execute_trades_internal(
            trades,
            client,
            currency_balances=currency_balances,
            currency_service=currency_service,
            source_currency=source_currency,
        )

    async def _execute_trades_internal(
        self,
        trades: List[Recommendation],
        client,
        currency_balances: Optional[dict[str, float]] = None,
        currency_service: Optional[CurrencyExchangeService] = None,
        source_currency: str = Currency.EUR,
    ) -> List[dict]:
        """Internal method to execute trades."""
        results = []
        skipped_count = 0
        converted_currencies = set()  # Track which currencies we've converted to

        # Get recently bought symbols for cooldown safety check
        from app.domain.constants import BUY_COOLDOWN_DAYS

        recently_bought = set()
        try:
            recently_bought = await self._trade_repo.get_recently_bought_symbols(
                BUY_COOLDOWN_DAYS
            )
        except Exception as e:
            logger.error(f"SAFETY: Failed to get recently bought symbols: {e}")
            # If we can't check cooldown, refuse to execute any buys
            return [
                {
                    "symbol": t.symbol,
                    "status": "failed",
                    "error": "Cooldown check failed",
                }
                for t in trades
                if t.side.upper() == "BUY"
            ]

        for trade in trades:
            try:
                # Check cooldown for BUY orders
                if trade.side.upper() == "BUY":
                    cooldown_result = await _check_buy_cooldown(
                        trade, recently_bought, BUY_COOLDOWN_DAYS
                    )
                    if cooldown_result:
                        results.append(cooldown_result)
                        continue

                # Validate and handle currency for BUY orders
                if trade.side.upper() == "BUY":
                    currency_result = await _handle_buy_currency(
                        trade,
                        currency_balances,
                        currency_service,
                        source_currency,
                        converted_currencies,
                    )
                    if currency_result:
                        results.append(currency_result)
                        skipped_count += 1
                        continue

                # Validate SELL orders
                if trade.side.upper() == "SELL":
                    sell_result = await _validate_sell_order(trade, self._position_repo)
                    if sell_result:
                        results.append(sell_result)
                        skipped_count += 1
                        continue

                # Check for pending orders
                has_pending = await _check_pending_orders(
                    trade, client, self._trade_repo
                )
                if has_pending:
                    results.append(
                        {
                            "symbol": trade.symbol,
                            "status": "blocked",
                            "error": f"Pending order already exists for {trade.symbol}",
                        }
                    )
                    continue

                # Execute the trade
                execution_result = await _execute_single_trade(trade, client)
                if execution_result and execution_result.get("status") == "success":
                    result = execution_result["result"]
                    await self.record_trade(
                        symbol=trade.symbol,
                        side=trade.side,
                        quantity=trade.quantity,
                        price=result.price,
                        order_id=result.order_id,
                        currency=trade.currency,
                        estimated_price=trade.estimated_price,
                        source="tradernet",
                    )
                    results.append(execution_result)
                elif execution_result:
                    results.append(execution_result)

            except Exception as e:
                logger.error(f"Failed to execute trade for {trade.symbol}: {e}")
                error_msg = "ORDER PLACEMENT FAILED"
                emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
                set_error(error_msg)
                results.append(
                    {
                        "symbol": trade.symbol,
                        "status": "error",
                        "error": str(e),
                    }
                )

        # Show LED warning if trades were skipped due to insufficient currency balance
        if skipped_count > 0:
            logger.warning(
                f"Skipped {skipped_count} trades due to insufficient currency balance"
            )
            if skipped_count >= 2:
                error_msg = "INSUFFICIENT FOREIGN CURRENCY BALANCE"
                emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
                set_error(error_msg)

        return results
