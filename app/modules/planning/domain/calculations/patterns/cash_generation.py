"""Cash generation pattern generator.

Multiple sells to generate cash, followed by strategic buys.
"""

from typing import Any, Dict, List

from app.modules.planning.domain.calculations.patterns.base import (
    PatternGenerator,
    pattern_generator_registry,
)
from app.modules.planning.domain.models import ActionCandidate


class CashGenerationPattern(PatternGenerator):
    """Cash generation: Multiple sells followed by strategic buys."""

    @property
    def name(self) -> str:
        return "cash_generation"

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
        Generate cash generation pattern: Multiple sells, strategic buys.

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

        sequence: List[ActionCandidate] = []
        total_cash = available_cash

        # Generate cash from multiple sells
        for candidate in all_sells[:max_depth]:
            sequence.append(candidate)
            total_cash += candidate.value_eur
            if len(sequence) >= max_depth:
                break

        # Strategic buys: prioritize opportunity, then averaging, then rebalance
        strategic_buys = (
            opportunities.get("opportunity_buys", [])
            + opportunities.get("averaging_down", [])
            + opportunities.get("rebalance_buys", [])
        )

        for candidate in strategic_buys:
            if candidate.value_eur <= total_cash and len(sequence) < max_depth:
                sequence.append(candidate)
                total_cash -= candidate.value_eur

        return [sequence] if sequence else []


# Auto-register this pattern
_cash_generation_pattern = CashGenerationPattern()
pattern_generator_registry.register(
    _cash_generation_pattern.name, _cash_generation_pattern
)
