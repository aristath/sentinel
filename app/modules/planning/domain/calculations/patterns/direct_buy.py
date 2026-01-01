"""Direct buy pattern generator.

Simple buy-only pattern using available cash.
"""

from typing import Any, Dict, List

from app.modules.planning.domain.calculations.patterns.base import (
    PatternGenerator,
    pattern_generator_registry,
)
from app.modules.planning.domain.models import ActionCandidate


class DirectBuyPattern(PatternGenerator):
    """Direct buys only (if cash available)."""

    @property
    def name(self) -> str:
        return "direct_buy"

    def default_params(self) -> Dict[str, Any]:
        return {
            "max_depth": 5,  # Maximum actions in sequence
            "available_cash_eur": 0.0,  # Available cash (passed in)
        }

    def generate(
        self,
        opportunities: Dict[str, List[ActionCandidate]],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]:
        """
        Generate direct buy pattern: Buy highest priority opportunities with available cash.

        Args:
            opportunities: Dict of categorized opportunities
            params: Pattern parameters (max_depth, available_cash_eur)

        Returns:
            List containing one sequence of buy actions, or empty list if no cash
        """
        available_cash = params.get("available_cash_eur", 0.0)
        max_depth = params.get("max_depth", 5)

        if available_cash <= 0:
            return []

        # Combine all buy opportunities
        all_buys = (
            opportunities.get("averaging_down", [])
            + opportunities.get("rebalance_buys", [])
            + opportunities.get("opportunity_buys", [])
        )

        # Sort by priority
        all_buys.sort(key=lambda x: x.priority, reverse=True)

        # Select buys that fit within cash
        direct_buys: List[ActionCandidate] = []
        remaining_cash = available_cash

        for candidate in all_buys:
            if candidate.value_eur <= remaining_cash and len(direct_buys) < max_depth:
                direct_buys.append(candidate)
                remaining_cash -= candidate.value_eur

        return [direct_buys] if direct_buys else []


# Auto-register this pattern
_direct_buy_pattern = DirectBuyPattern()
pattern_generator_registry.register(_direct_buy_pattern.name, _direct_buy_pattern)
