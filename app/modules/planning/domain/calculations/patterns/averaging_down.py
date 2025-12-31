"""Averaging down pattern generator.

Focus on buying quality dips, selling if needed to generate cash.
"""

from typing import Any, Dict, List

from app.modules.planning.domain.calculations.patterns.base import (
    PatternGenerator,
    pattern_generator_registry,
)
from app.modules.planning.domain.holistic_planner import ActionCandidate


class AveragingDownPattern(PatternGenerator):
    """Averaging down focus: Buy quality dips, sell if cash needed."""

    @property
    def name(self) -> str:
        return "averaging_down"

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
        Generate averaging down pattern: Buy quality dips, sell if cash needed.

        Args:
            opportunities: Dict of categorized opportunities
            params: Pattern parameters

        Returns:
            List containing one sequence, or empty list
        """
        averaging_down = opportunities.get("averaging_down", [])
        if not averaging_down:
            return []

        max_depth = params.get("max_depth", 5)
        available_cash = params.get("available_cash_eur", 0.0)

        sequence: List[ActionCandidate] = []
        total_cash = available_cash

        # If not enough cash for first averaging down, sell one windfall
        profit_taking = opportunities.get("profit_taking", [])
        if total_cash < averaging_down[0].value_eur and profit_taking:
            sequence.append(profit_taking[0])
            total_cash += profit_taking[0].value_eur

        # Buy quality dips
        for candidate in averaging_down:
            if candidate.value_eur <= total_cash and len(sequence) < max_depth:
                sequence.append(candidate)
                total_cash -= candidate.value_eur

        return [sequence] if sequence else []


# Auto-register this pattern
_averaging_down_pattern = AveragingDownPattern()
pattern_generator_registry.register(
    _averaging_down_pattern.name, _averaging_down_pattern
)
