"""
Domain Models - All dataclasses for the application.

This consolidates all domain models in one place for easy imports.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.domain.exceptions import ValidationError
from app.shared.domain.value_objects.currency import Currency
from app.domain.value_objects.recommendation_status import RecommendationStatus
from app.domain.value_objects.trade_side import TradeSide

# AllocationTarget moved to modules/allocation/domain/models.py
# Backward compatibility re-export (temporary - will be removed in Phase 5)
from app.modules.allocation.domain.models import AllocationTarget

# CashFlow moved to modules/cash_flows/domain/models.py
# Backward compatibility re-export (temporary - will be removed in Phase 5)
from app.modules.cash_flows.domain.models import CashFlow


@dataclass
class Stock:
    """Stock in the investment universe."""

    symbol: str
    name: str
    country: Optional[str] = None
    fullExchangeName: Optional[str] = None
    yahoo_symbol: Optional[str] = None
    isin: Optional[str] = None  # International Securities Identification Number
    industry: Optional[str] = None
    priority_multiplier: float = 1.0
    min_lot: int = 1
    active: bool = True
    allow_buy: bool = True
    allow_sell: bool = False
    currency: Optional[Currency] = None
    last_synced: Optional[str] = None  # ISO datetime when stock data was last synced
    min_portfolio_target: Optional[float] = (
        None  # Minimum target portfolio allocation percentage (0-20)
    )
    max_portfolio_target: Optional[float] = (
        None  # Maximum target portfolio allocation percentage (0-30)
    )

    def __post_init__(self):
        """Validate stock data."""
        if not self.symbol or not self.symbol.strip():
            raise ValidationError("Symbol cannot be empty")

        if not self.name or not self.name.strip():
            raise ValidationError("Name cannot be empty")

        # Normalize symbol
        object.__setattr__(self, "symbol", self.symbol.upper().strip())

        # Ensure min_lot is at least 1
        if self.min_lot < 1:
            object.__setattr__(self, "min_lot", 1)

        # Validate min_portfolio_target
        if self.min_portfolio_target is not None:
            if self.min_portfolio_target < 0 or self.min_portfolio_target > 20:
                raise ValidationError("min_portfolio_target must be between 0 and 20")

        # Validate max_portfolio_target
        if self.max_portfolio_target is not None:
            if self.max_portfolio_target < 0 or self.max_portfolio_target > 30:
                raise ValidationError("max_portfolio_target must be between 0 and 30")

        # Validate that max >= min when both are provided
        if (
            self.min_portfolio_target is not None
            and self.max_portfolio_target is not None
        ):
            if self.max_portfolio_target < self.min_portfolio_target:
                raise ValidationError(
                    "max_portfolio_target must be >= min_portfolio_target"
                )


# Position moved to modules/portfolio/domain/models.py
# Backward compatibility re-export (temporary - will be removed in Phase 5)
from app.modules.portfolio.domain.models import Position


@dataclass
class Trade:
    """Executed trade record."""

    symbol: str
    side: TradeSide  # BUY or SELL
    quantity: float
    price: float
    executed_at: datetime
    isin: Optional[str] = None  # ISIN for broker-agnostic identification
    order_id: Optional[str] = None
    currency: Optional[Currency] = None
    currency_rate: Optional[float] = None
    value_eur: Optional[float] = None
    source: str = "tradernet"
    id: Optional[int] = None

    def __post_init__(self):
        """Validate trade data."""
        if not self.symbol or not self.symbol.strip():
            raise ValidationError("Symbol cannot be empty")

        if self.quantity <= 0:
            raise ValidationError("Quantity must be positive")

        if self.price <= 0:
            raise ValidationError("Price must be positive")

        # Normalize symbol
        object.__setattr__(self, "symbol", self.symbol.upper().strip())


# Export all models including re-exported CashFlow
__all__ = [
    "Stock",
    "Position",
    "Trade",
    "StockScore",
    "AllocationTarget",
    "CashFlow",  # Re-exported from modules/cash_flows/domain/models.py
    "PortfolioSnapshot",
    "DailyPrice",
    "MonthlyPrice",
    "AllocationStatus",
    "PortfolioSummary",
    "Recommendation",
    "StockPriority",
    "MultiStepRecommendation",
    "DividendRecord",
]


@dataclass
class StockScore:
    """Calculated score for a stock."""

    symbol: str
    isin: Optional[str] = None  # ISIN for broker-agnostic identification

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

    technical_score: Optional[float] = None
    fundamental_score: Optional[float] = None

    # Metadata
    history_years: Optional[float] = None
    volatility: Optional[float] = None
    calculated_at: Optional[datetime] = None


# PortfolioSnapshot, DailyPrice, MonthlyPrice moved to modules/portfolio/domain/models.py
# Backward compatibility re-export (temporary - will be removed in Phase 5)
from app.modules.portfolio.domain.models import (
    DailyPrice,
    MonthlyPrice,
    PortfolioSnapshot,
)


# Allocation and Portfolio Models
# Moved from app/services/allocator.py


@dataclass
class AllocationStatus:
    """Current allocation vs target."""

    category: str  # country or industry
    name: str  # Country name or Industry name
    target_pct: float
    current_pct: float
    current_value: float
    deviation: float  # current - target (negative = underweight)


@dataclass
class PortfolioSummary:
    """Complete portfolio allocation summary."""

    total_value: float
    cash_balance: float
    country_allocations: list
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
    isin: Optional[str] = None  # ISIN for broker-agnostic identification
    country: Optional[str] = None
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
        """Validate recommendation data and calculate score_change."""
        if not self.symbol or not self.symbol.strip():
            raise ValidationError("Symbol cannot be empty")

        if not self.name or not self.name.strip():
            raise ValidationError("Name cannot be empty")

        if self.quantity <= 0:
            raise ValidationError("Quantity must be positive")

        if self.estimated_price <= 0:
            raise ValidationError("Estimated price must be positive")

        if self.estimated_value <= 0:
            raise ValidationError("Estimated value must be positive")

        if not self.reason or not self.reason.strip():
            raise ValidationError("Reason cannot be empty")

        # Normalize symbol
        object.__setattr__(self, "symbol", self.symbol.upper().strip())

        # Calculate score_change if both portfolio scores are provided
        if (
            self.current_portfolio_score is not None
            and self.new_portfolio_score is not None
        ):
            if self.score_change is None:
                object.__setattr__(
                    self,
                    "score_change",
                    self.new_portfolio_score - self.current_portfolio_score,
                )


@dataclass
class StockPriority:
    """Priority score for a stock candidate."""

    symbol: str
    name: str
    industry: str
    stock_score: float
    volatility: float  # Raw volatility (0.0-1.0)
    multiplier: float  # Manual priority multiplier
    min_lot: int  # Minimum lot size for trading
    combined_priority: float  # Enhanced priority score
    country: Optional[str] = None
    # Score breakdown (for display)
    quality_score: Optional[float] = None
    opportunity_score: Optional[float] = None
    allocation_fit_score: Optional[float] = None


@dataclass
class MultiStepRecommendation:
    """A single step in a multi-step recommendation sequence.

    Multi-step recommendations show a planned sequence of trades
    (e.g., SELL X then BUY Y) with portfolio score projections.
    """

    step: int  # 1-indexed step number
    side: str  # "BUY" or "SELL"
    symbol: str
    name: str
    quantity: int
    estimated_price: float
    estimated_value: float  # In EUR
    currency: str
    reason: str
    portfolio_score_before: float
    portfolio_score_after: float
    score_change: float
    available_cash_before: float
    available_cash_after: float


@dataclass
class DividendRecord:
    """Record of a dividend payment with DRIP tracking.

    Tracks dividend payments and whether they were successfully reinvested.
    If reinvestment wasn't possible (dividend too small), a pending_bonus
    is calculated which the optimizer uses to boost the stock's expected return.
    """

    symbol: str
    amount: float  # Original dividend amount
    currency: str
    amount_eur: float  # Converted to EUR
    payment_date: str  # ISO date string
    isin: Optional[str] = None  # ISIN for broker-agnostic identification
    id: Optional[int] = None
    cash_flow_id: Optional[int] = None  # Link to cash_flows table
    reinvested: bool = False
    reinvested_at: Optional[str] = None
    reinvested_quantity: Optional[int] = None
    pending_bonus: float = 0.0  # Expected return bonus (0.0 to 1.0)
    bonus_cleared: bool = False
    cleared_at: Optional[str] = None
    created_at: Optional[str] = None

    def __post_init__(self):
        """Validate dividend record data."""
        if not self.symbol or not self.symbol.strip():
            raise ValidationError("Symbol cannot be empty")

        if self.amount <= 0:
            raise ValidationError("Dividend amount must be positive")

        if self.amount_eur <= 0:
            raise ValidationError("Dividend amount in EUR must be positive")

        # Normalize symbol
        object.__setattr__(self, "symbol", self.symbol.upper().strip())


# Export all models including re-exported CashFlow
__all__ = [
    "Stock",
    "Position",
    "Trade",
    "StockScore",
    "AllocationTarget",
    "CashFlow",  # Re-exported from modules/cash_flows/domain/models.py
    "PortfolioSnapshot",
    "DailyPrice",
    "MonthlyPrice",
    "AllocationStatus",
    "PortfolioSummary",
    "Recommendation",
    "StockPriority",
    "MultiStepRecommendation",
    "DividendRecord",
]
