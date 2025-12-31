"""Tradernet API data models."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:
    """Portfolio position from Tradernet."""

    symbol: str
    quantity: float
    avg_price: float
    current_price: float
    market_value: float
    market_value_eur: float  # Market value converted to EUR
    unrealized_pnl: float
    currency: str
    currency_rate: float  # Exchange rate to EUR (1.0 for EUR positions)


@dataclass
class CashBalance:
    """Cash balance in a currency."""

    currency: str
    amount: float


@dataclass
class Quote:
    """Security quote data."""

    symbol: str
    price: float
    change: float
    change_pct: float
    volume: int
    timestamp: datetime


@dataclass
class OHLC:
    """OHLC candle data."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class OrderResult:
    """Order execution result."""

    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    status: str
