"""
Scoring Models - All dataclasses for scoring calculations.

These models represent the computed scores and their components.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional


@dataclass
class PortfolioContext:
    """Portfolio context for allocation fit calculations."""

    country_weights: Dict[str, float]  # group_name -> weight (-1 to +1)
    industry_weights: Dict[str, float]  # group_name -> weight (-1 to +1)
    positions: Dict[str, float]  # symbol -> position_value
    total_value: float

    # Additional data for portfolio scoring
    security_countries: Optional[Dict[str, str]] = (
        None  # symbol -> country (individual)
    )
    security_industries: Optional[Dict[str, str]] = (
        None  # symbol -> industry (individual)
    )
    security_scores: Optional[Dict[str, float]] = None  # symbol -> quality_score
    security_dividends: Optional[Dict[str, float]] = None  # symbol -> dividend_yield

    # Group mappings (for mapping individual countries/industries to groups)
    country_to_group: Optional[Dict[str, str]] = None  # country -> group_name
    industry_to_group: Optional[Dict[str, str]] = None  # industry -> group_name

    # Cost basis data for averaging down
    position_avg_prices: Optional[Dict[str, float]] = (
        None  # symbol -> avg_purchase_price
    )
    current_prices: Optional[Dict[str, float]] = None  # symbol -> current_market_price


@dataclass
class PortfolioScore:
    """Overall portfolio health score."""

    diversification_score: float  # Country + industry balance (0-100)
    dividend_score: float  # Weighted average dividend yield score (0-100)
    quality_score: float  # Weighted average security quality (0-100)
    total: float  # Combined score (0-100)


@dataclass
class CalculatedSecurityScore:
    """Complete security score with all components."""

    symbol: str
    total_score: float  # Final weighted score
    volatility: Optional[float]  # Raw annualized volatility
    calculated_at: datetime

    # New 8-group scores (Dict with long_term, fundamentals, opportunity, etc.)
    group_scores: Optional[Dict[str, float]] = None

    # Sub-component scores for each group (e.g., long_term: {cagr, sortino, sharpe})
    sub_scores: Optional[Dict[str, Dict[str, float]]] = None


@dataclass
class PrefetchedSecurityData:
    """Pre-fetched data to avoid duplicate API calls."""

    daily_prices: list  # List of dicts with date, close, high, low, open, volume
    monthly_prices: list  # List of dicts with month, avg_adj_close
    fundamentals: object  # Yahoo fundamentals data (can be None)


@dataclass
class TechnicalData:
    """Technical indicators for instability detection."""

    current_volatility: float  # Last 60 days
    historical_volatility: float  # Last 365 days
    distance_from_ma_200: float  # Positive = above MA, negative = below


@dataclass
class SellScore:
    """Result of sell score calculation."""

    symbol: str
    eligible: bool  # Whether sell is allowed at all
    block_reason: Optional[str]  # If not eligible, why
    underperformance_score: float
    time_held_score: float
    portfolio_balance_score: float
    instability_score: float
    total_score: float
    suggested_sell_pct: float  # 0.10 to 0.50
    suggested_sell_quantity: int
    suggested_sell_value: float
    profit_pct: float
    days_held: int


# Backward compatibility aliases
CalculatedStockScore = CalculatedSecurityScore
PrefetchedStockData = PrefetchedSecurityData
