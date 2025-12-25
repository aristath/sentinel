"""
Domain Models - All dataclasses for the application.

This consolidates all domain models in one place for easy imports.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.domain.value_objects.currency import Currency
from app.domain.value_objects.trade_side import TradeSide
from app.domain.value_objects.recommendation_status import RecommendationStatus


@dataclass
class Stock:
    """Stock in the investment universe."""
    symbol: str
    name: str
    geography: str
    yahoo_symbol: Optional[str] = None
    industry: Optional[str] = None
    priority_multiplier: float = 1.0
    min_lot: int = 1
    active: bool = True
    allow_buy: bool = True
    allow_sell: bool = False
    currency: Optional[Currency] = None


@dataclass
class Position:
    """Current position in a stock."""
    symbol: str
    quantity: float
    avg_price: float
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


@dataclass
class Trade:
    """Executed trade record."""
    symbol: str
    side: TradeSide  # BUY or SELL
    quantity: float
    price: float
    executed_at: datetime
    order_id: Optional[str] = None
    currency: Optional[Currency] = None
    currency_rate: Optional[float] = None
    value_eur: Optional[float] = None
    source: str = "tradernet"
    id: Optional[int] = None


@dataclass
class StockScore:
    """Calculated score for a stock."""
    symbol: str

    # Primary component scores (0-1 range)
    quality_score: Optional[float] = None
    opportunity_score: Optional[float] = None
    analyst_score: Optional[float] = None
    allocation_fit_score: Optional[float] = None

    # Quality breakdown
    cagr_score: Optional[float] = None
    consistency_score: Optional[float] = None
    financial_strength_score: Optional[float] = None
    sharpe_score: Optional[float] = None
    drawdown_score: Optional[float] = None
    dividend_bonus: Optional[float] = None

    # Technical indicators
    rsi: Optional[float] = None
    ema_200: Optional[float] = None
    below_52w_high_pct: Optional[float] = None

    # Combined scores
    total_score: Optional[float] = None
    sell_score: Optional[float] = None

    # Legacy compatibility scores
    technical_score: Optional[float] = None
    fundamental_score: Optional[float] = None

    # Metadata
    history_years: Optional[float] = None
    volatility: Optional[float] = None
    calculated_at: Optional[datetime] = None


@dataclass
class AllocationTarget:
    """Target allocation for geography or industry."""
    type: str  # 'geography' or 'industry'
    name: str
    target_pct: float  # Weight from -1.0 to 1.0


@dataclass
class CashFlow:
    """Cash flow transaction (deposit, withdrawal, dividend, etc.)."""
    transaction_id: str
    type_doc_id: int
    date: str
    amount: float
    currency: Currency
    amount_eur: float
    transaction_type: Optional[str] = None
    status: Optional[str] = None
    status_c: Optional[int] = None
    description: Optional[str] = None
    params_json: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    id: Optional[int] = None


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


@dataclass
class DailyPrice:
    """Daily OHLC price data for a stock."""
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


# Allocation and Portfolio Models
# Moved from app/services/allocator.py


@dataclass
class AllocationStatus:
    """Current allocation vs target."""
    category: str  # geography or industry
    name: str  # EU, ASIA, US or Technology, etc.
    target_pct: float
    current_pct: float
    current_value: float
    deviation: float  # current - target (negative = underweight)


@dataclass
class PortfolioSummary:
    """Complete portfolio allocation summary."""
    total_value: float
    cash_balance: float
    geographic_allocations: list
    industry_allocations: list


@dataclass
class Recommendation:
    """Unified trade recommendation model.
    
    Replaces both TradeRecommendation and service-level Recommendation.
    """
    symbol: str
    name: str
    side: TradeSide  # BUY or SELL
    quantity: float
    estimated_price: float
    estimated_value: float
    reason: str  # Why this trade is recommended
    geography: str
    currency: Currency = Currency.EUR  # Stock's native currency
    status: RecommendationStatus = RecommendationStatus.PENDING
    industry: Optional[str] = None
    priority: Optional[float] = None
    current_portfolio_score: Optional[float] = None
    new_portfolio_score: Optional[float] = None
    score_change: Optional[float] = None
    uuid: Optional[str] = None
    portfolio_hash: Optional[str] = None
    
    def __post_init__(self):
        """Calculate score_change if both portfolio scores are provided."""
        if self.current_portfolio_score is not None and self.new_portfolio_score is not None:
            if self.score_change is None:
                self.score_change = self.new_portfolio_score - self.current_portfolio_score


@dataclass
class StockPriority:
    """Priority score for a stock candidate."""
    symbol: str
    name: str
    geography: str
    industry: str
    stock_score: float
    volatility: float  # Raw volatility (0.0-1.0)
    multiplier: float  # Manual priority multiplier
    min_lot: int  # Minimum lot size for trading
    combined_priority: float  # Enhanced priority score
    # Score breakdown (for display)
    quality_score: Optional[float] = None
    opportunity_score: Optional[float] = None
    allocation_fit_score: Optional[float] = None
