"""Yahoo Finance data models.

Data classes for Yahoo Finance API responses.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AnalystData:
    """Analyst recommendation data."""

    symbol: str
    recommendation: str  # strongBuy, buy, hold, sell, strongSell
    target_price: float
    current_price: float
    upside_pct: float
    num_analysts: int
    recommendation_score: float  # 0-1 normalized score


@dataclass
class FundamentalData:
    """Fundamental analysis data."""

    symbol: str
    pe_ratio: Optional[float]
    forward_pe: Optional[float]
    peg_ratio: Optional[float]
    price_to_book: Optional[float]
    revenue_growth: Optional[float]
    earnings_growth: Optional[float]
    profit_margin: Optional[float]
    operating_margin: Optional[float]
    roe: Optional[float]
    debt_to_equity: Optional[float]
    current_ratio: Optional[float]
    market_cap: Optional[float]
    dividend_yield: Optional[float]
    five_year_avg_dividend_yield: Optional[float]  # For DRIP scoring


@dataclass
class HistoricalPrice:
    """Historical price data."""

    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: float
