"""Profit taking pattern generator.

Sell windfalls and reinvest proceeds into quality opportunities.
"""

from typing import Any, Dict, List

from app.modules.planning.domain.calculations.patterns.base import (
    PatternGenerator,
    pattern_generator_registry,
)
from app.modules.planning.domain.models import ActionCandidate


class ProfitTakingPattern(PatternGenerator):
    """Profit-taking + reinvest in quality opportunities."""

    @property
    def name(self) -> str:
        return "profit_taking"

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
        Generate profit-taking pattern: Sell windfalls, reinvest in buys.

        Args:
            opportunities: Dict of categorized opportunities
            params: Pattern parameters

        Returns:
            List containing one sequence (sells followed by buys), or empty list
        """
        profit_taking = opportunities.get("profit_taking", [])
        if not profit_taking:
            return []

        max_depth = params.get("max_depth", 5)
        available_cash = params.get("available_cash_eur", 0.0)

        # Take top profit-taking sells
        sequence: List[ActionCandidate] = profit_taking[
            : min(len(profit_taking), max_depth)
        ]

        # Calculate cash from sells
        cash_from_sells = sum(c.value_eur for c in sequence)
        total_cash = available_cash + cash_from_sells

        # Reinvest in quality buys
        quality_buys = opportunities.get("averaging_down", []) + opportunities.get(
            "rebalance_buys", []
        )
        quality_buys.sort(key=lambda x: x.priority, reverse=True)

        for candidate in quality_buys:
            if candidate.value_eur <= total_cash and len(sequence) < max_depth:
                sequence.append(candidate)
                total_cash -= candidate.value_eur

        return [sequence] if sequence else []


# Auto-register this pattern
_profit_taking_pattern = ProfitTakingPattern()
pattern_generator_registry.register(_profit_taking_pattern.name, _profit_taking_pattern)
