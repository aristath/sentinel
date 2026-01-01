"""Opportunity-first pattern generator.

Focus on high-quality opportunity buys.
"""

from typing import Any, Dict, List

from app.modules.planning.domain.calculations.patterns.base import (
    PatternGenerator,
    pattern_generator_registry,
)
from app.modules.planning.domain.models import ActionCandidate


class OpportunityFirstPattern(PatternGenerator):
    """Opportunity-first: Prioritize high-quality opportunities."""

    @property
    def name(self) -> str:
        return "opportunity_first"

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
        Generate opportunity-first pattern: Focus on quality opportunities.

        Args:
            opportunities: Dict of categorized opportunities
            params: Pattern parameters

        Returns:
            List containing one sequence, or empty list
        """
        opportunity_buys = opportunities.get("opportunity_buys", [])
        if not opportunity_buys:
            return []

        max_depth = params.get("max_depth", 5)
        available_cash = params.get("available_cash_eur", 0.0)

        sequence: List[ActionCandidate] = []
        remaining_cash = available_cash

        # Prioritize opportunity buys
        for candidate in opportunity_buys:
            if candidate.value_eur <= remaining_cash and len(sequence) < max_depth:
                sequence.append(candidate)
                remaining_cash -= candidate.value_eur

        # Fill remaining with averaging down or rebalance buys
        other_buys = opportunities.get("averaging_down", []) + opportunities.get(
            "rebalance_buys", []
        )
        for candidate in other_buys:
            if candidate.value_eur <= remaining_cash and len(sequence) < max_depth:
                sequence.append(candidate)
                remaining_cash -= candidate.value_eur

        return [sequence] if sequence else []


# Auto-register this pattern
_opportunity_first_pattern = OpportunityFirstPattern()
pattern_generator_registry.register(
    _opportunity_first_pattern.name, _opportunity_first_pattern
)
