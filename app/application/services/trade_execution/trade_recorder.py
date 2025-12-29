"""Trade recording logic.

Handles recording executed trades to the database.
"""

import logging
from datetime import datetime
from typing import Optional

from app.domain.events import TradeExecutedEvent, get_event_bus
from app.domain.factories.trade_factory import TradeFactory
from app.domain.models import Trade
from app.domain.repositories.protocols import IPositionRepository, ITradeRepository
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.value_objects.currency import Currency
from app.domain.value_objects.trade_side import TradeSide

logger = logging.getLogger(__name__)


async def _check_duplicate_order(
    order_id: Optional[str], trade_repo: ITradeRepository
) -> bool:
    """Check if order_id already exists in database."""
    if not order_id:
        return False
    exists = await trade_repo.exists(order_id)
    if exists:
        logger.debug(f"Order {order_id} already exists in database, skipping")
    return exists


async def _get_currency_and_rate(
    currency: Optional[str],
    exchange_rate_service: ExchangeRateService,
) -> tuple[Currency, Optional[float]]:
    """Convert currency string to enum and get exchange rate if needed."""
    trade_currency = Currency.EUR
    currency_rate = None

    if currency:
        if isinstance(currency, str):
            trade_currency = Currency.from_string(currency)
        else:
            trade_currency = currency

        if trade_currency != Currency.EUR:
            currency_rate = await exchange_rate_service.get_rate(
                str(trade_currency), str(Currency.EUR)
            )

    return trade_currency, currency_rate


async def _update_position_after_sell(
    symbol: str,
    position_repo: Optional[IPositionRepository],
    order_id: Optional[str] = None,
) -> None:
    """Update last_sold_at timestamp for position after successful sell (excluding RESEARCH trades)."""
    # Don't update last_sold_at for RESEARCH mode trades
    if order_id and order_id.startswith("RESEARCH_"):
        logger.debug(f"Skipping last_sold_at update for RESEARCH trade: {order_id}")
        return

    if position_repo:
        try:
            await position_repo.update_last_sold_at(symbol)
            logger.info(f"Updated last_sold_at for {symbol}")
        except Exception as e:
            logger.warning(f"Failed to update last_sold_at: {e}")


async def record_trade(
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    trade_repo: ITradeRepository,
    position_repo: Optional[IPositionRepository],
    exchange_rate_service: ExchangeRateService,
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
        trade_repo: Trade repository
        position_repo: Position repository (optional, for updating last_sold_at)
        exchange_rate_service: Exchange rate service for currency conversion
        order_id: Broker order ID (optional)
        currency: Trade currency (optional)
        estimated_price: Estimated price to use if price <= 0 (optional)
        source: Trade source (default: "tradernet")

    Returns:
        Trade object if recorded successfully, None if duplicate or error
    """
    final_price = price if price > 0 else (estimated_price or 0)

    try:
        if await _check_duplicate_order(order_id, trade_repo):
            return None

        if not order_id or not order_id.strip():
            logger.warning(
                f"Cannot record trade without valid order_id (got: {order_id!r})"
            )
            return None

        trade_side = TradeSide.from_string(side)
        trade_currency, currency_rate = await _get_currency_and_rate(
            currency, exchange_rate_service
        )

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

        await trade_repo.create(trade_record)
        logger.info(
            f"Stored order {order_id or '(no order_id)'} for {symbol} immediately"
        )

        event_bus = get_event_bus()
        event_bus.publish(TradeExecutedEvent(trade=trade_record))

        if trade_side.is_sell():
            await _update_position_after_sell(symbol, position_repo, order_id)

        return trade_record

    except Exception as e:
        logger.warning(f"Failed to store order immediately (may already exist): {e}")
        return None
