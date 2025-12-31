"""Multi-sell pattern generator.

Combine profit-taking and rebalance sells, then buy multiple opportunities.
"""

from typing import Any, Dict, List

from app.modules.planning.domain.calculations.patterns.base import (
    PatternGenerator,
    pattern_generator_registry,
)
from app.modules.planning.domain.holistic_planner import ActionCandidate


class MultiSellPattern(PatternGenerator):
    """Multi-sell pattern: Combine sells, reinvest in multiple buys."""

    @property
    def name(self) -> str:
        return "multi_sell"

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
        Generate multi-sell pattern: Multiple sells followed by multiple buys.

        Args:
            opportunities: Dict of categorized opportunities
            params: Pattern parameters

        Returns:
            List containing one sequence, or empty list
        """
        max_depth = params.get("max_depth", 5)
        available_cash = params.get("available_cash_eur", 0.0)

        # Combine all sell opportunities
        all_sells = opportunities.get("profit_taking", []) + opportunities.get(
            "rebalance_sells", []
        )

        if not all_sells:
            return []

        # Take up to max_depth sells (prioritize profit-taking, then rebalance)
        sequence: List[ActionCandidate] = []
        for candidate in all_sells[:max_depth]:
            sequence.append(candidate)
            if len(sequence) >= max_depth:
                break

        # Calculate cash from sells
        cash_from_sells = sum(c.value_eur for c in sequence)
        total_cash = available_cash + cash_from_sells

        # Add buys with remaining steps
        all_buys = (
            opportunities.get("averaging_down", [])
            + opportunities.get("rebalance_buys", [])
            + opportunities.get("opportunity_buys", [])
        )

        for candidate in all_buys:
            if candidate.value_eur <= total_cash and len(sequence) < max_depth:
                sequence.append(candidate)
                total_cash -= candidate.value_eur

        return [sequence] if sequence else []


# Auto-register this pattern
_multi_sell_pattern = MultiSellPattern()
pattern_generator_registry.register(_multi_sell_pattern.name, _multi_sell_pattern)
