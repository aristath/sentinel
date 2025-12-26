"""Trade execution application service.

Orchestrates trade execution via Tradernet and records trades.
"""

import logging
from typing import List, Optional
from datetime import datetime

from app.repositories import TradeRepository, PositionRepository
from app.domain.models import Recommendation, Trade
from app.domain.value_objects.currency import Currency
from app.domain.value_objects.trade_side import TradeSide
from app.domain.factories.trade_factory import TradeFactory
from app.domain.events import TradeExecutedEvent, get_event_bus
from app.infrastructure.external.tradernet import get_tradernet_client
from app.infrastructure.events import emit, SystemEvent
from app.infrastructure.hardware.led_display import set_activity
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
        position_repo: Optional[PositionRepository] = None
    ):
        self._trade_repo = trade_repo
        self._position_repo = position_repo

    async def record_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        order_id: Optional[str] = None,
        currency: Optional[str] = None,
        estimated_price: Optional[float] = None,
        source: str = "tradernet"
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
        # Use estimated_price if actual price is invalid
        final_price = price if price > 0 else (estimated_price or 0)
        
        try:
            # Check if order_id already exists (might have been stored by sync_trades)
            if order_id:
                exists = await self._trade_repo.exists(order_id)
                if exists:
                    logger.debug(f"Order {order_id} already exists in database, skipping")
                    return None
            
            # Convert side to TradeSide enum
            trade_side = TradeSide.from_string(side)
            
            # Convert currency to Currency enum and get exchange rate
            trade_currency = Currency.EUR
            currency_rate = None
            if currency:
                if isinstance(currency, str):
                    trade_currency = Currency.from_string(currency)
                else:
                    trade_currency = currency
                
                # Get exchange rate if not EUR
                if trade_currency != Currency.EUR:
                    from app.domain.services.exchange_rate_service import get_exchange_rate
                    currency_rate = await get_exchange_rate(str(trade_currency), str(Currency.EUR))
            
            # Use factory to create trade
            trade_record = TradeFactory.create_from_execution(
                symbol=symbol,
                side=trade_side,
                quantity=quantity,
                price=final_price,
                order_id=order_id,
                executed_at=datetime.now(),
                currency=trade_currency,
                currency_rate=currency_rate,
                source=source,
            )
            
            await self._trade_repo.create(trade_record)
            logger.info(f"Stored order {order_id or '(no order_id)'} for {symbol} immediately")
            
            # Publish domain event
            event_bus = get_event_bus()
            event_bus.publish(TradeExecutedEvent(trade=trade_record))
            
            # For successful SELL orders, update last_sold_at in positions
            if trade_side.is_sell() and self._position_repo:
                try:
                    await self._position_repo.update_last_sold_at(symbol)
                    logger.info(f"Updated last_sold_at for {symbol}")
                except Exception as e:
                    logger.warning(f"Failed to update last_sold_at: {e}")
            
            return trade_record
            
        except Exception as e:
            # Log but don't fail - order was placed successfully
            # This might be a duplicate key error if sync_trades already inserted it
            logger.warning(f"Failed to store order immediately (may already exist): {e}")
            return None

    async def execute_trades(
        self,
        trades: List[Recommendation],
        currency_balances: Optional[dict[str, float]] = None,
        auto_convert_currency: bool = False,
        source_currency: str = Currency.EUR
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
        client = get_tradernet_client()

        if not client.is_connected:
            if not client.connect():
                emit(SystemEvent.ERROR_OCCURRED, message="TRADE EXECUTION FAILED")
                raise ConnectionError("Failed to connect to Tradernet")

        # Get currency exchange service if auto-convert is enabled
        currency_service = get_currency_exchange_service() if auto_convert_currency else None

        return await self._execute_trades_internal(
            trades, client, currency_balances=currency_balances,
            currency_service=currency_service, source_currency=source_currency
        )

    async def _execute_trades_internal(
        self,
        trades: List[Recommendation],
        client,
        currency_balances: Optional[dict[str, float]] = None,
        currency_service: Optional[CurrencyExchangeService] = None,
        source_currency: str = Currency.EUR
    ) -> List[dict]:
        """Internal method to execute trades."""
        results = []
        skipped_count = 0
        converted_currencies = set()  # Track which currencies we've converted to

        # Get recently bought symbols for cooldown safety check
        from app.domain.constants import BUY_COOLDOWN_DAYS
        recently_bought = set()
        try:
            recently_bought = await self._trade_repo.get_recently_bought_symbols(BUY_COOLDOWN_DAYS)
        except Exception as e:
            logger.error(f"SAFETY: Failed to get recently bought symbols: {e}")
            # If we can't check cooldown, refuse to execute any buys
            return [{"symbol": t.symbol, "status": "failed", "error": "Cooldown check failed"} for t in trades if t.side.upper() == "BUY"]

        for trade in trades:
            try:
                # Check currency balance before executing (BUY orders only)
                if trade.side.upper() == "BUY":
                    # SAFETY: Final cooldown check before any BUY
                    if trade.symbol in recently_bought:
                        logger.warning(
                            f"SAFETY BLOCK: {trade.symbol} in cooldown period, refusing to execute"
                        )
                        results.append({
                            "symbol": trade.symbol,
                            "status": "blocked",
                            "error": f"Cooldown active (bought within {BUY_COOLDOWN_DAYS} days)"
                        })
                        continue

                    required = trade.quantity * trade.estimated_price
                    trade_currency = trade.currency or Currency.EUR

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

                                set_activity(f"CONVERTING {source_currency} TO {trade_currency}...", duration=10.0)

                                # Ensure we have enough balance
                                if currency_service.ensure_balance(
                                    trade_currency, required, source_currency
                                ):
                                    converted_currencies.add(trade_currency)
                                    logger.info(f"Currency conversion successful for {trade_currency}")
                                    set_activity(f"CURRENCY CONVERSION COMPLETE", duration=3.0)
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

                # Check for pending orders for this symbol (applies to both BUY and SELL)
                # Check both broker API and local database for recent orders
                has_pending = client.has_pending_order_for_symbol(trade.symbol)
                
                # Also check database for recent SELL orders (catches orders just placed)
                if not has_pending and trade.side.upper() == "SELL":
                    try:
                        has_recent = await self._trade_repo.has_recent_sell_order(trade.symbol, hours=2)
                        if has_recent:
                            has_pending = True
                            logger.info(f"Found recent SELL order in database for {trade.symbol}")
                    except Exception as e:
                        logger.warning(f"Failed to check database for recent sell orders: {e}")
                
                if has_pending:
                    logger.warning(f"SAFETY BLOCK: {trade.symbol} has pending order, refusing to execute")
                    results.append({
                        "symbol": trade.symbol,
                        "status": "blocked",
                        "error": f"Pending order already exists for {trade.symbol}",
                    })
                    continue

                # Show activity message for the trade
                side_text = "BUYING" if trade.side.upper() == "BUY" else "SELLING"
                value = int(trade.quantity * trade.estimated_price)
                symbol_short = trade.symbol.split(".")[0]  # Remove .US/.EU suffix
                set_activity(f"{side_text} {symbol_short} €{value}", duration=10.0)

                result = client.place_order(
                    symbol=trade.symbol,
                    side=trade.side,
                    quantity=trade.quantity,
                )

                if result:
                    # Store order immediately in database to prevent duplicate submissions
                    # The sync_trades job will still sync executed trades from the API,
                    # but storing immediately allows us to check for recent orders locally.
                    await self.record_trade(
                        symbol=trade.symbol,
                        side=trade.side,
                        quantity=trade.quantity,
                        price=result.price,
                        order_id=result.order_id,
                        currency=trade.currency,
                        estimated_price=trade.estimated_price,
                        source="tradernet"
                    )

                    results.append({
                        "symbol": trade.symbol,
                        "status": "success",
                        "order_id": result.order_id,
                        "side": trade.side,
                    })
                else:
                    emit(SystemEvent.ERROR_OCCURRED, message="ORDER PLACEMENT FAILED")
                    results.append({
                        "symbol": trade.symbol,
                        "status": "failed",
                        "error": "Order placement returned None",
                    })

            except Exception as e:
                logger.error(f"Failed to execute trade for {trade.symbol}: {e}")
                emit(SystemEvent.ERROR_OCCURRED, message="ORDER PLACEMENT FAILED")
                results.append({
                    "symbol": trade.symbol,
                    "status": "error",
                    "error": str(e),
                })

        # Show LED warning if trades were skipped due to insufficient currency balance
        if skipped_count > 0:
            logger.warning(f"Skipped {skipped_count} trades due to insufficient currency balance")
            if skipped_count >= 2:
                emit(SystemEvent.ERROR_OCCURRED, message="INSUFFICIENT FOREIGN CURRENCY BALANCE")

        return results
