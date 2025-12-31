"""Partial execution scenario generator.

Generates variations of sequences with different fill percentages.
This helps test robustness against incomplete trade execution.
"""

from typing import Any, Dict, List

from app.modules.planning.domain.calculations.sequences.base import (
    SequenceGenerator,
    sequence_generator_registry,
)
from app.modules.planning.domain.holistic_planner import ActionCandidate


class PartialExecutionGenerator(SequenceGenerator):
    """
    Generates partial execution scenarios (50%, 75%, 100% fills).

    Takes existing sequences and creates variations where each action
    is executed at different fill percentages. This helps evaluate
    plan robustness when trades don't fully execute.

    Example:
        Original: [Buy 100 shares AAPL, Sell 50 shares GOOGL]
        Variations:
        - 50% fill: [Buy 50 shares AAPL, Sell 25 shares GOOGL]
        - 75% fill: [Buy 75 shares AAPL, Sell 37.5 shares GOOGL]
        - 100% fill: [Buy 100 shares AAPL, Sell 50 shares GOOGL]
    """

    @property
    def name(self) -> str:
        return "partial_execution"

    def default_params(self) -> Dict[str, Any]:
        return {
            "fill_percentages": [0.5, 0.75, 1.0],
            "min_shares": 1,  # Minimum shares for partial fill to be valid
        }

    def generate(
        self,
        opportunities: List[ActionCandidate],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]:
        """
        Generate partial execution variations of sequences.

        Note: This generator is typically applied AFTER pattern generators
        have created base sequences. It takes those sequences and creates
        variations with different fill percentages.

        Since this method receives flat opportunities, we treat each
        opportunity as a potential single-action sequence and create
        partial fills of it.

        Args:
            opportunities: List of candidate actions
            params: Generator parameters

        Returns:
            List of action sequences with partial fills
        """
        fill_percentages = params.get("fill_percentages", [0.5, 0.75, 1.0])
        min_shares = params.get("min_shares", 1)

        sequences: List[List[ActionCandidate]] = []

        # For each opportunity, create partial fill variations
        for opp in opportunities:
            for fill_pct in fill_percentages:
                # Skip 100% fill if it's the same as original
                if fill_pct == 1.0:
                    sequences.append([opp])
                    continue

                # Calculate partial quantity
                partial_quantity = int(opp.quantity * fill_pct)

                # Skip if partial fill results in less than minimum
                if partial_quantity < min_shares:
                    continue

                # Create partial fill candidate
                # We create a new ActionCandidate with adjusted quantity
                partial_candidate = ActionCandidate(
                    side=opp.side,
                    symbol=opp.symbol,
                    name=opp.name,
                    quantity=partial_quantity,
                    price=opp.price,
                    value_eur=opp.value_eur * fill_pct,
                    currency=opp.currency,
                    priority=opp.priority,
                    reason=f"{opp.reason} ({int(fill_pct * 100)}% fill)",
                    tags=opp.tags,
                )

                # Add as single-action sequence
                sequences.append([partial_candidate])

        return sequences


# Auto-register
_partial_execution_generator = PartialExecutionGenerator()
sequence_generator_registry.register(
    _partial_execution_generator.name, _partial_execution_generator
)
