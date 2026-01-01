"""Base class for opportunity calculators.

Opportunity calculators identify potential trading actions (buy/sell candidates)
based on different strategies and criteria.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.domain.models import Position, Security
from app.modules.planning.domain.models import ActionCandidate


@dataclass
class OpportunityContext:
    """Context provided to opportunity calculators."""

    positions: List[Position]
    securities: List[Security]
    stocks_by_symbol: Dict[str, Security]
    available_cash_eur: float
    total_portfolio_value_eur: float

    # Optional context for rebalancing
    country_allocations: Optional[Dict[str, float]] = None  # Current allocations
    industry_allocations: Optional[Dict[str, float]] = None
    country_to_group: Optional[Dict[str, str]] = None  # Country -> group mapping
    country_weights: Optional[Dict[str, float]] = None  # Target weights per group

    # Optional context for other features
    target_weights: Optional[Dict[str, float]] = None  # Optimizer target weights
    recently_traded: Optional[Dict[str, str]] = None  # symbol -> last_trade_date
    security_scores: Optional[Dict[str, float]] = None  # symbol -> score


class OpportunityCalculator(ABC):
    """Base class for all opportunity calculators.

    Each calculator identifies a specific type of trading opportunity.
    Calculators are registered automatically and loaded by the planner.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this calculator."""
        pass

    @abstractmethod
    def default_params(self) -> Dict[str, Any]:
        """Default parameters for this calculator."""
        pass

    @abstractmethod
    async def calculate(
        self,
        context: OpportunityContext,
        params: Dict[str, Any],
    ) -> List[ActionCandidate]:
        """
        Calculate opportunities based on context and parameters.

        Args:
            context: Portfolio and market context
            params: Calculator-specific parameters

        Returns:
            List of action candidates (buy/sell opportunities)
        """
        pass

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        return f"{self.__class__.__name__}(name='{self.name}')"


# Registry instance (initialized on first import)
from app.modules.planning.domain.calculations.base import Registry  # noqa: E402

opportunity_calculator_registry = Registry[OpportunityCalculator]()
