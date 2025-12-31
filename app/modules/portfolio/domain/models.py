"""Portfolio domain models."""

from dataclasses import dataclass
from typing import Optional

from app.domain.exceptions import ValidationError
from app.shared.domain.value_objects.currency import Currency


@dataclass
class Position:
    """Current position in a security."""

    symbol: str
    quantity: float
    avg_price: float
    isin: Optional[str] = None  # ISIN for broker-agnostic identification
    currency: Currency = Currency.EUR
    currency_rate: float = 1.0
    current_price: Optional[float] = None
    market_value_eur: Optional[float] = None
    cost_basis_eur: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    last_updated: Optional[str] = None
    first_bought_at: Optional[str] = None
    last_sold_at: Optional[str] = None
    bucket_id: str = "core"  # Which bucket owns this position (core or satellite)

    def __post_init__(self):
        """Validate position data."""
        if not self.symbol or not self.symbol.strip():
            raise ValidationError("Symbol cannot be empty")

        if self.quantity < 0:
            raise ValidationError("Quantity must be non-negative")

        if self.avg_price <= 0:
            raise ValidationError("Average price must be positive")

        # Normalize symbol
        object.__setattr__(self, "symbol", self.symbol.upper().strip())

        # Validate currency_rate is positive
        if self.currency_rate <= 0:
            object.__setattr__(self, "currency_rate", 1.0)


@dataclass
class PortfolioSnapshot:
    """Daily portfolio summary."""

    date: str
    total_value: float
    cash_balance: float
    invested_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    geo_eu_pct: Optional[float] = None
    geo_asia_pct: Optional[float] = None
    geo_us_pct: Optional[float] = None
    position_count: Optional[int] = None
    annual_turnover: Optional[float] = None


@dataclass
class DailyPrice:
    """Daily OHLC price data for a security."""

    date: str
    close_price: float
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    volume: Optional[int] = None
    source: str = "yahoo"


@dataclass
class MonthlyPrice:
    """Monthly aggregated price data for CAGR calculations."""

    year_month: str  # 'YYYY-MM' format
    avg_close: float
    avg_adj_close: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    source: str = "calculated"
