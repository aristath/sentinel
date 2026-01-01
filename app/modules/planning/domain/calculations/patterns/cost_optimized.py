"""Cost-optimized pattern generator.

Minimize number of trades while maximizing impact by priority.
"""

from typing import Any, Dict, List

from app.domain.models import TradeSide
from app.modules.planning.domain.calculations.patterns.base import (
    PatternGenerator,
    pattern_generator_registry,
)
from app.modules.planning.domain.models import ActionCandidate


class CostOptimizedPattern(PatternGenerator):
    """Cost-optimized: Minimize trades, maximize impact."""

    @property
    def name(self) -> str:
        return "cost_optimized"

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
        Generate cost-optimized pattern: Minimize trades, maximize impact.

        Args:
            opportunities: Dict of categorized opportunities
            params: Pattern parameters

        Returns:
            List containing one sequence, or empty list
        """
        max_depth = params.get("max_depth", 5)
        if max_depth < 1:
            return []

        available_cash = params.get("available_cash_eur", 0.0)

        # Combine all opportunities and sort by priority
        all_opportunities = (
            opportunities.get("profit_taking", [])
            + opportunities.get("rebalance_sells", [])
            + opportunities.get("averaging_down", [])
            + opportunities.get("rebalance_buys", [])
            + opportunities.get("opportunity_buys", [])
        )

        if not all_opportunities:
            return []

        # Sort by priority (highest first) to get best impact per trade
        all_opportunities.sort(key=lambda x: x.priority, reverse=True)

        sequence: List[ActionCandidate] = []
        running_cash = available_cash

        # Add sells first (they generate cash)
        all_sells = opportunities.get("profit_taking", []) + opportunities.get(
            "rebalance_sells", []
        )
        for candidate in all_sells:
            if len(sequence) >= max_depth:
                break
            if candidate.side == TradeSide.SELL:
                sequence.append(candidate)
                running_cash += candidate.value_eur

        # Add highest priority buys (minimize number of trades)
        for candidate in all_opportunities:
            if len(sequence) >= max_depth:
                break
            if candidate.side == TradeSide.BUY and candidate.value_eur <= running_cash:
                # Avoid duplicates
                if candidate not in sequence:
                    sequence.append(candidate)
                    running_cash -= candidate.value_eur

        return [sequence] if sequence else []


# Auto-register this pattern
_cost_optimized_pattern = CostOptimizedPattern()
pattern_generator_registry.register(
    _cost_optimized_pattern.name, _cost_optimized_pattern
)
