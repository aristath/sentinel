"""
Scoring Models - All dataclasses for scoring calculations.

These models represent the computed scores and their components.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict


@dataclass
class QualityScore:
    """Long-term quality score components."""
    total_return_score: float  # 0-1, bell curve for CAGR + dividend
    consistency_score: float   # 0-1, 5y vs 10y CAGR similarity
    financial_strength_score: float  # 0-1, margins, debt, liquidity
    dividend_bonus: float      # 0-0.10, extra for high dividend stocks
    sharpe_ratio_score: float  # 0-1, risk-adjusted return quality
    max_drawdown_score: float  # 0-1, resilience to losses
    total: float

    # Metadata
    cagr_5y: Optional[float] = None   # 5-year CAGR
    cagr_10y: Optional[float] = None  # 10-year CAGR (if available)
    total_return: Optional[float] = None  # CAGR + dividend yield
    dividend_yield: Optional[float] = None
    sharpe_ratio: Optional[float] = None  # Actual Sharpe ratio value
    max_drawdown: Optional[float] = None  # Actual max drawdown (negative)
    history_years: float = 0  # Years of price data available


@dataclass
class OpportunityScore:
    """Buy-the-dip opportunity score components."""
    below_52w_high: float    # 0-1, further below = higher (BUY signal)
    ema_distance: float      # 0-1, below 200-EMA = higher (BUY signal)
    pe_vs_historical: float  # 0-1, below avg P/E = higher (BUY signal)
    rsi_score: float         # 0-1, RSI < 30 = 1.0, RSI > 70 = 0.0
    bollinger_score: float   # 0-1, near lower band = higher
    total: float


@dataclass
class AnalystScore:
    """Analyst recommendation score components."""
    recommendation_score: float  # 0-1, based on buy/hold/sell
    target_score: float          # 0-1, based on upside potential
    total: float


@dataclass
class AllocationFitScore:
    """Allocation fit score components (portfolio awareness)."""
    geo_gap_score: float         # 0-1, boost for underweight geographies
    industry_gap_score: float    # 0-1, boost for underweight industries
    averaging_down_score: float  # 0-1, bonus for quality dips we own
    total: float


@dataclass
class PortfolioContext:
    """Portfolio context for allocation fit calculations."""
    geo_weights: Dict[str, float]       # name -> weight (-1 to +1)
    industry_weights: Dict[str, float]  # name -> weight (-1 to +1)
    positions: Dict[str, float]         # symbol -> position_value
    total_value: float

    # Additional data for portfolio scoring
    stock_geographies: Optional[Dict[str, str]] = None  # symbol -> geography
    stock_industries: Optional[Dict[str, str]] = None   # symbol -> industry
    stock_scores: Optional[Dict[str, float]] = None     # symbol -> quality_score
    stock_dividends: Optional[Dict[str, float]] = None  # symbol -> dividend_yield

    # Cost basis data for averaging down
    position_avg_prices: Optional[Dict[str, float]] = None   # symbol -> avg_purchase_price
    current_prices: Optional[Dict[str, float]] = None        # symbol -> current_market_price


@dataclass
class PortfolioScore:
    """Overall portfolio health score."""
    diversification_score: float  # Geographic + industry balance (0-100)
    dividend_score: float         # Weighted average dividend yield score (0-100)
    quality_score: float          # Weighted average stock quality (0-100)
    total: float                  # Combined score (0-100)


@dataclass
class CalculatedStockScore:
    """Complete stock score with all components."""
    symbol: str
    quality: QualityScore
    opportunity: OpportunityScore
    analyst: AnalystScore
    allocation_fit: Optional[AllocationFitScore]  # None if no portfolio context
    total_score: float          # Final weighted score
    volatility: Optional[float] # Raw annualized volatility
    calculated_at: datetime


@dataclass
class PrefetchedStockData:
    """Pre-fetched data to avoid duplicate API calls."""
    daily_prices: list   # List of dicts with date, close, high, low, open, volume
    monthly_prices: list # List of dicts with month, avg_adj_close
    fundamentals: object # Yahoo fundamentals data (can be None)


@dataclass
class TechnicalData:
    """Technical indicators for instability detection."""
    current_volatility: float     # Last 60 days
    historical_volatility: float  # Last 365 days
    distance_from_ma_200: float   # Positive = above MA, negative = below


@dataclass
class SellScore:
    """Result of sell score calculation."""
    symbol: str
    eligible: bool                  # Whether sell is allowed at all
    block_reason: Optional[str]     # If not eligible, why
    underperformance_score: float
    time_held_score: float
    portfolio_balance_score: float
    instability_score: float
    total_score: float
    suggested_sell_pct: float       # 0.10 to 0.50
    suggested_sell_quantity: int
    suggested_sell_value: float
    profit_pct: float
    days_held: int
