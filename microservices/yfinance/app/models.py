"""Pydantic models for request/response handling."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ServiceResponse(BaseModel):
    """Standard response format for all endpoints."""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Request models
class BatchQuotesRequest(BaseModel):
    """Request model for batch quote retrieval."""

    symbols: list[str] = Field(..., min_items=1, max_items=100, description="List of symbols")
    yahoo_overrides: Optional[dict[str, str]] = Field(
        default=None, description="Symbol to Yahoo symbol overrides"
    )


class HistoricalPricesRequest(BaseModel):
    """Request model for historical prices."""

    symbol: str
    yahoo_symbol: Optional[str] = None
    period: str = Field(default="1y", description="Period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max")
    interval: str = Field(default="1d", description="Interval: 1d, 1wk, 1mo")


# Response models
class HistoricalPrice(BaseModel):
    """Historical price data point."""

    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: float


class HistoricalPricesResponse(BaseModel):
    """Response model for historical prices."""

    symbol: str
    prices: list[HistoricalPrice]


class FundamentalData(BaseModel):
    """Fundamental analysis data."""

    symbol: str
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    peg_ratio: Optional[float] = None
    price_to_book: Optional[float] = None
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None
    profit_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    roe: Optional[float] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    market_cap: Optional[float] = None
    dividend_yield: Optional[float] = None
    five_year_avg_dividend_yield: Optional[float] = None


class AnalystData(BaseModel):
    """Analyst recommendations and price targets."""

    symbol: str
    recommendation: str
    target_price: float
    current_price: float
    upside_pct: float
    num_analysts: int
    recommendation_score: float


class SecurityInfo(BaseModel):
    """Security metadata."""

    symbol: str
    industry: Optional[str] = None
    sector: Optional[str] = None
    country: Optional[str] = None
    full_exchange_name: Optional[str] = None
    product_type: Optional[str] = None
    name: Optional[str] = None

