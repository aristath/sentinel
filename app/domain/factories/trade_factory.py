"""Trade factory for creating Trade domain objects."""

from datetime import datetime
from typing import Optional, Union

from app.domain.models import Trade
from app.shared.domain.value_objects.currency import Currency
from app.domain.value_objects.trade_side import TradeSide


class TradeFactory:
    """Factory for creating Trade domain objects."""

    @classmethod
    def create_from_execution(
        cls,
        symbol: str,
        side: TradeSide,
        quantity: float,
        price: float,
        order_id: str,
        executed_at: datetime,
        currency: Optional[Currency] = None,
        currency_rate: Optional[float] = None,
        source: str = "tradernet",
    ) -> Trade:
        """Create Trade from execution result.

        Args:
            symbol: Stock symbol
            side: Trade side (BUY or SELL)
            quantity: Trade quantity
            price: Execution price
            order_id: Broker order ID
            executed_at: Execution timestamp
            currency: Trade currency (optional, defaults to EUR)
            currency_rate: Exchange rate to EUR (optional)
            source: Trade source (defaults to "tradernet")

        Returns:
            Trade domain object with calculated EUR value
        """
        if currency is None:
            currency = Currency.EUR
            currency_rate = 1.0

        # Calculate EUR value
        value_eur = None
        if currency_rate and currency_rate > 0:
            value_eur = (quantity * price) / currency_rate
        elif currency == Currency.EUR:
            value_eur = quantity * price

        return Trade(
            symbol=symbol.upper(),
            side=side,
            quantity=quantity,
            price=price,
            executed_at=executed_at,
            order_id=order_id,
            currency=currency,
            currency_rate=currency_rate,
            value_eur=value_eur,
            source=source,
        )

    @classmethod
    def create_from_sync(
        cls,
        symbol: str,
        side: Union[str, TradeSide],
        quantity: float,
        price: float,
        executed_at: Union[str, datetime],
        order_id: str,
        currency: Optional[Union[str, Currency]] = None,
        currency_rate: Optional[float] = None,
        source: str = "tradernet",
    ) -> Trade:
        """Create Trade from broker sync data.

        Args:
            symbol: Stock symbol
            side: Trade side (string or TradeSide enum)
            quantity: Trade quantity
            price: Execution price
            executed_at: Execution timestamp (string ISO format or datetime)
            order_id: Broker order ID
            currency: Trade currency (string, Currency enum, or None)
            currency_rate: Exchange rate to EUR (optional)
            source: Trade source (defaults to "tradernet")

        Returns:
            Trade domain object
        """
        # Convert side to TradeSide enum if string
        if isinstance(side, str):
            side = TradeSide.from_string(side)

        # Convert currency to Currency enum if string
        if currency is None:
            currency = Currency.EUR
            currency_rate = 1.0
        elif isinstance(currency, str):
            currency = Currency.from_string(currency)

        # Convert executed_at to datetime if string
        if isinstance(executed_at, str):
            executed_at = datetime.fromisoformat(executed_at)

        return cls.create_from_execution(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_id=order_id,
            executed_at=executed_at,
            currency=currency,
            currency_rate=currency_rate,
            source=source,
        )
