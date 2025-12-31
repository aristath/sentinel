"""Single best action pattern generator.

Select the single highest priority action for minimal intervention.
"""

from typing import Any, Dict, List

from app.domain.models import TradeSide
from app.modules.planning.domain.calculations.patterns.base import (
    PatternGenerator,
    pattern_generator_registry,
)
from app.modules.planning.domain.holistic_planner import ActionCandidate


class SingleBestPattern(PatternGenerator):
    """Single best action pattern: Minimal intervention strategy."""

    @property
    def name(self) -> str:
        return "single_best"

    def default_params(self) -> Dict[str, Any]:
        return {
            "max_depth": 1,  # Always 1 for single best
            "available_cash_eur": 0.0,
        }

    def generate(
        self,
        opportunities: Dict[str, List[ActionCandidate]],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]:
        """
        Generate single best pattern: One highest priority action.

        Args:
            opportunities: Dict of categorized opportunities
            params: Pattern parameters

        Returns:
            List containing one sequence with single action, or empty list
        """
        max_depth = params.get("max_depth", 1)
        if max_depth < 1:
            return []

        available_cash = params.get("available_cash_eur", 0.0)

        # Combine all opportunities
        all_candidates = (
            opportunities.get("profit_taking", [])
            + opportunities.get("averaging_down", [])
            + opportunities.get("rebalance_sells", [])
            + opportunities.get("rebalance_buys", [])
            + opportunities.get("opportunity_buys", [])
        )

        if not all_candidates:
            return []

        # Find highest priority action
        best = max(all_candidates, key=lambda x: x.priority)

        # Check if we can execute it
        if best.side == TradeSide.BUY and best.value_eur <= available_cash:
            return [[best]]
        elif best.side == TradeSide.SELL:
            return [[best]]

        return []


# Auto-register this pattern
_single_best_pattern = SingleBestPattern()
pattern_generator_registry.register(_single_best_pattern.name, _single_best_pattern)
