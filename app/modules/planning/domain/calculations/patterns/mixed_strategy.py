"""Mixed strategy pattern generator.

Flexible pattern: any combination of sells followed by any combination of buys.
"""

from typing import Any, Dict, List

from app.modules.planning.domain.calculations.patterns.base import (
    PatternGenerator,
    pattern_generator_registry,
)
from app.modules.planning.domain.models import ActionCandidate


class MixedStrategyPattern(PatternGenerator):
    """Mixed strategy: Flexible combination of sells and buys."""

    @property
    def name(self) -> str:
        return "mixed_strategy"

    def default_params(self) -> Dict[str, Any]:
        return {
            "max_depth": 5,
            "available_cash_eur": 0.0,
        }

    def generate(
        self,
        opportunities: Dict[str, List[ActionCandidate]],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]:
        """
        Generate mixed strategy pattern: Flexible sells and buys.

        Args:
            opportunities: Dict of categorized opportunities
            params: Pattern parameters

        Returns:
            List containing one sequence, or empty list
        """
        max_depth = params.get("max_depth", 5)
        available_cash = params.get("available_cash_eur", 0.0)

        # Combine all sells and buys
        all_sells = opportunities.get("profit_taking", []) + opportunities.get(
            "rebalance_sells", []
        )
        all_buys = (
            opportunities.get("averaging_down", [])
            + opportunities.get("rebalance_buys", [])
            + opportunities.get("opportunity_buys", [])
        )

        if not all_sells and not all_buys:
            return []

        sequence: List[ActionCandidate] = []
        total_cash = available_cash

        # Add sells first (up to half of max_depth)
        max_sells = max(1, max_depth // 2)
        for candidate in all_sells[:max_sells]:
            if len(sequence) < max_depth:
                sequence.append(candidate)
                total_cash += candidate.value_eur

        # Add buys with remaining steps and cash
        for candidate in all_buys:
            if candidate.value_eur <= total_cash and len(sequence) < max_depth:
                sequence.append(candidate)
                total_cash -= candidate.value_eur

        return [sequence] if sequence else []


# Auto-register this pattern
_mixed_strategy_pattern = MixedStrategyPattern()
pattern_generator_registry.register(
    _mixed_strategy_pattern.name, _mixed_strategy_pattern
)
