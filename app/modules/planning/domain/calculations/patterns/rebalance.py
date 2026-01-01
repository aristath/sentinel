"""Rebalance pattern generator.

Sell overweight positions and buy underweight areas.
"""

from typing import Any, Dict, List

from app.modules.planning.domain.calculations.patterns.base import (
    PatternGenerator,
    pattern_generator_registry,
)
from app.modules.planning.domain.models import ActionCandidate


class RebalancePattern(PatternGenerator):
    """Rebalance: Sell overweight + buy underweight."""

    @property
    def name(self) -> str:
        return "rebalance"

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
        Generate rebalance pattern: Sell overweight, buy underweight.

        Args:
            opportunities: Dict of categorized opportunities
            params: Pattern parameters

        Returns:
            List containing one rebalancing sequence, or empty list
        """
        rebalance_sells = opportunities.get("rebalance_sells", [])
        if not rebalance_sells:
            return []

        max_depth = params.get("max_depth", 5)
        available_cash = params.get("available_cash_eur", 0.0)

        # Take top rebalance sells
        sequence: List[ActionCandidate] = rebalance_sells[
            : min(len(rebalance_sells), max_depth)
        ]

        # Calculate cash from sells
        cash_from_sells = sum(c.value_eur for c in sequence)
        total_cash = available_cash + cash_from_sells

        # Buy underweight areas
        rebalance_buys = opportunities.get("rebalance_buys", [])
        for candidate in rebalance_buys:
            if candidate.value_eur <= total_cash and len(sequence) < max_depth:
                sequence.append(candidate)
                total_cash -= candidate.value_eur

        return [sequence] if sequence else []


# Auto-register this pattern
_rebalance_pattern = RebalancePattern()
pattern_generator_registry.register(_rebalance_pattern.name, _rebalance_pattern)
