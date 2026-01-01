"""Combinatorial sequence generator.

Generates all valid combinations of sells and buys with smart pruning.
"""

from itertools import combinations
from typing import Any, Dict, List

from app.modules.planning.domain.calculations.sequences.base import (
    SequenceGenerator,
    sequence_generator_registry,
)
from app.modules.planning.domain.models import ActionCandidate


class CombinatorialGenerator(SequenceGenerator):
    """Basic combinatorial generator: all valid combinations."""

    @property
    def name(self) -> str:
        return "combinatorial"

    def default_params(self) -> Dict[str, Any]:
        return {
            "max_sells": 3,
            "max_buys": 3,
            "priority_threshold": 0.3,
            "max_steps": 5,
            "max_combinations": 50,
            "max_candidates": 12,
        }

    def generate(
        self,
        opportunities: List[ActionCandidate],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]:
        """
        Generate valid combinations with smart pruning.

        IMPORTANT: All sequences have sells first, then buys (rigid ordering).

        Args:
            opportunities: Combined list of sell and buy opportunities
            params: Generator parameters

        Returns:
            List of action sequences (sells first, then buys)
        """
        max_sells = params.get("max_sells", 3)
        max_buys = params.get("max_buys", 3)
        priority_threshold = params.get("priority_threshold", 0.3)
        max_steps = params.get("max_steps", 5)
        max_combinations = params.get("max_combinations", 50)
        max_candidates = params.get("max_candidates", 12)

        # Separate sells and buys
        from app.domain.value_objects.trade_side import TradeSide

        sells = [opp for opp in opportunities if opp.side == TradeSide.SELL]
        buys = [opp for opp in opportunities if opp.side == TradeSide.BUY]

        sequences: List[List[ActionCandidate]] = []

        # Filter by priority threshold
        filtered_sells = [s for s in sells if s.priority >= priority_threshold]
        filtered_buys = [b for b in buys if b.priority >= priority_threshold]

        # Limit candidates to avoid combinatorial explosion
        filtered_sells = filtered_sells[:max_candidates]
        filtered_buys = filtered_buys[:max_candidates]

        # Generate combinations of sells (1 to max_sells)
        for num_sells in range(1, min(max_sells + 1, len(filtered_sells) + 1)):
            if len(sequences) >= max_combinations:
                break
            for sell_combo in combinations(filtered_sells, num_sells):
                if len(sequences) >= max_combinations:
                    break
                remaining_steps = max_steps - len(sell_combo)
                if remaining_steps <= 0:
                    continue

                # Generate combinations of buys (1 to min(max_buys, remaining_steps))
                max_buys_for_combo = min(max_buys, remaining_steps, len(filtered_buys))
                for num_buys in range(1, max_buys_for_combo + 1):
                    if len(sequences) >= max_combinations:
                        break
                    for buy_combo in combinations(filtered_buys, num_buys):
                        if len(sequences) >= max_combinations:
                            break
                        # Create sequence: sells first, then buys (rigid ordering)
                        sequence = list(sell_combo) + list(buy_combo)
                        if len(sequence) <= max_steps:
                            sequences.append(sequence)

        return sequences


# Auto-register
_combinatorial_generator = CombinatorialGenerator()
sequence_generator_registry.register(
    _combinatorial_generator.name, _combinatorial_generator
)
