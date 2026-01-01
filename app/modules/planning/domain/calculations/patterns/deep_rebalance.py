"""Deep rebalance pattern generator.

Multiple rebalance sells followed by multiple rebalance buys.
"""

from typing import Any, Dict, List

from app.modules.planning.domain.calculations.patterns.base import (
    PatternGenerator,
    pattern_generator_registry,
)
from app.modules.planning.domain.models import ActionCandidate


class DeepRebalancePattern(PatternGenerator):
    """Deep rebalance: Multiple rebalance sells and buys."""

    @property
    def name(self) -> str:
        return "deep_rebalance"

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
        Generate deep rebalance pattern: Multiple rebalance sells and buys.

        Args:
            opportunities: Dict of categorized opportunities
            params: Pattern parameters

        Returns:
            List containing one sequence, or empty list
        """
        rebalance_sells = opportunities.get("rebalance_sells", [])
        rebalance_buys = opportunities.get("rebalance_buys", [])

        if not rebalance_sells or not rebalance_buys:
            return []

        max_depth = params.get("max_depth", 5)
        available_cash = params.get("available_cash_eur", 0.0)

        sequence: List[ActionCandidate] = []
        total_cash = available_cash

        # Add multiple rebalance sells (up to half of max_depth)
        max_sells = max(1, max_depth // 2)
        for candidate in rebalance_sells[:max_sells]:
            if len(sequence) < max_depth:
                sequence.append(candidate)
                total_cash += candidate.value_eur

        # Add multiple rebalance buys
        for candidate in rebalance_buys:
            if candidate.value_eur <= total_cash and len(sequence) < max_depth:
                sequence.append(candidate)
                total_cash -= candidate.value_eur

        return [sequence] if sequence else []


# Auto-register this pattern
_deep_rebalance_pattern = DeepRebalancePattern()
pattern_generator_registry.register(
    _deep_rebalance_pattern.name, _deep_rebalance_pattern
)
