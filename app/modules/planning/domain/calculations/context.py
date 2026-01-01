"""Context classes for planner operations.

These dataclasses standardize inputs to various planner operations,
making the code more maintainable and testable.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from app.domain.models import Position, Security
from app.modules.scoring.domain.models import PortfolioContext


@dataclass
class OpportunityContext:
    """
    Context for opportunity identification.

    Contains all data needed by opportunity calculators to identify
    trading opportunities (buys, sells, rebalancing, etc.).
    """

    # Portfolio state
    portfolio_context: PortfolioContext
    positions: List[Position]
    securities: List[Security]
    available_cash_eur: float
    total_portfolio_value_eur: float

    # Market data
    current_prices: Dict[str, float]
    stocks_by_symbol: Dict[str, Security] = field(default_factory=dict)

    # Optional enrichment data
    security_scores: Optional[Dict[str, float]] = None  # Final scores by symbol
    country_allocations: Optional[Dict[str, float]] = None  # Current allocations
    country_to_group: Optional[Dict[str, str]] = None  # Country groupings
    country_weights: Optional[Dict[str, float]] = None  # Target weights by country
    target_weights: Optional[Dict[str, float]] = None  # Optimizer target weights

    # Constraints
    ineligible_symbols: Set[str] = field(default_factory=set)  # Can't sell these
    recently_sold: Set[str] = field(default_factory=set)  # Recently sold (cooldown)
    recently_bought: Set[str] = field(default_factory=set)  # Recently bought

    # Configuration
    transaction_cost_fixed: float = 2.0
    transaction_cost_percent: float = 0.002
    allow_sell: bool = True
    allow_buy: bool = True

    # Services (for data fetching if needed)
    exchange_rate_service: Optional[Any] = None

    def __post_init__(self):
        """Initialize computed fields."""
        if not self.stocks_by_symbol and self.securities:
            self.stocks_by_symbol = {s.symbol: s for s in self.securities}


@dataclass
class EvaluationContext:
    """
    Context for sequence evaluation.

    Contains all data needed to simulate and score action sequences.
    """

    # Portfolio state (same as OpportunityContext)
    portfolio_context: PortfolioContext
    positions: List[Position]
    securities: List[Security]
    available_cash_eur: float
    total_portfolio_value_eur: float

    # Market data
    current_prices: Dict[str, float]
    stocks_by_symbol: Dict[str, Security] = field(default_factory=dict)

    # Configuration
    transaction_cost_fixed: float = 2.0
    transaction_cost_percent: float = 0.002

    # Services
    exchange_rate_service: Optional[Any] = None

    # Optional: Price adjustment scenarios for stochastic evaluation
    price_adjustments: Optional[Dict[str, float]] = None

    def __post_init__(self):
        """Initialize computed fields."""
        if not self.stocks_by_symbol and self.securities:
            self.stocks_by_symbol = {s.symbol: s for s in self.securities}


@dataclass
class PlannerContext:
    """
    Top-level context for holistic planning.

    Combines opportunity and evaluation contexts with planner-specific settings.
    """

    # Opportunity identification context
    opportunity_context: OpportunityContext

    # Evaluation context
    evaluation_context: EvaluationContext

    # Planner configuration
    max_depth: int = 5
    max_opportunities_per_category: int = 5
    priority_threshold: float = 0.3
    enable_diverse_selection: bool = True
    diversity_weight: float = 0.3

    # Advanced settings
    beam_width: int = 10  # For beam search in multi-objective mode
    evaluation_mode: str = (
        "single_objective"  # or "multi_objective", "stochastic", "monte_carlo"
    )
    stochastic_price_shifts: List[float] = field(
        default_factory=lambda: [-0.10, -0.05, 0.0, 0.05, 0.10]
    )
    monte_carlo_path_count: int = 100

    # Module enablement (can be overridden by configuration)
    enable_combinatorial: bool = True
    enable_adaptive_patterns: bool = True

    @classmethod
    def from_opportunity_context(
        cls,
        opportunity_context: OpportunityContext,
        **kwargs,
    ) -> "PlannerContext":
        """
        Create PlannerContext from OpportunityContext.

        Automatically creates EvaluationContext from the same data.
        """
        # Create evaluation context from opportunity context
        evaluation_context = EvaluationContext(
            portfolio_context=opportunity_context.portfolio_context,
            positions=opportunity_context.positions,
            securities=opportunity_context.securities,
            available_cash_eur=opportunity_context.available_cash_eur,
            total_portfolio_value_eur=opportunity_context.total_portfolio_value_eur,
            current_prices=opportunity_context.current_prices,
            stocks_by_symbol=opportunity_context.stocks_by_symbol,
            transaction_cost_fixed=opportunity_context.transaction_cost_fixed,
            transaction_cost_percent=opportunity_context.transaction_cost_percent,
            exchange_rate_service=opportunity_context.exchange_rate_service,
        )

        return cls(
            opportunity_context=opportunity_context,
            evaluation_context=evaluation_context,
            **kwargs,
        )
