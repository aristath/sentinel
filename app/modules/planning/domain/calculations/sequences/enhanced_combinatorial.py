"""Enhanced combinatorial sequence generator.

Uses priority-based weighted sampling and diversity constraints.
"""

import random
from typing import Any, Dict, List, Optional

from app.domain.models import Security
from app.modules.planning.domain.calculations.sequences.base import (
    SequenceGenerator,
    sequence_generator_registry,
)
from app.modules.planning.domain.models import ActionCandidate


class EnhancedCombinatorialGenerator(SequenceGenerator):
    """Enhanced combinatorial: weighted sampling with diversity."""

    @property
    def name(self) -> str:
        return "enhanced_combinatorial"

    def default_params(self) -> Dict[str, Any]:
        return {
            "max_sells": 3,
            "max_buys": 3,
            "priority_threshold": 0.3,
            "max_steps": 5,
            "max_combinations": 50,
            "max_candidates": 12,
            "securities_by_symbol": None,  # Optional[Dict[str, Security]]
        }

    def generate(
        self,
        opportunities: List[ActionCandidate],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]:
        """
        Generate combinations with priority-based sampling and diversity constraints.

        Uses weighted sampling based on priority and ensures diversity across
        countries/industries to avoid over-concentration.

        Args:
            opportunities: Combined list of sell and buy opportunities
            params: Generator parameters (must include securities_by_symbol for diversity)

        Returns:
            List of action sequences (sells first, then buys)
        """
        max_sells = params.get("max_sells", 3)
        max_buys = params.get("max_buys", 3)
        priority_threshold = params.get("priority_threshold", 0.3)
        max_steps = params.get("max_steps", 5)
        max_combinations = params.get("max_combinations", 50)
        max_candidates = params.get("max_candidates", 12)
        securities_by_symbol: Optional[Dict[str, Security]] = params.get(
            "securities_by_symbol"
        )

        # Separate sells and buys
        from app.domain.value_objects.trade_side import TradeSide

        sells = [opp for opp in opportunities if opp.side == TradeSide.SELL]
        buys = [opp for opp in opportunities if opp.side == TradeSide.BUY]

        sequences: List[List[ActionCandidate]] = []

        # Filter by priority threshold
        filtered_sells = [s for s in sells if s.priority >= priority_threshold]
        filtered_buys = [b for b in buys if b.priority >= priority_threshold]

        # Limit candidates but prioritize by score
        filtered_sells.sort(key=lambda x: x.priority, reverse=True)
        filtered_buys.sort(key=lambda x: x.priority, reverse=True)
        filtered_sells = filtered_sells[:max_candidates]
        filtered_buys = filtered_buys[:max_candidates]

        # Calculate priority weights for sampling
        def _get_priority_weights(candidates: List[ActionCandidate]) -> List[float]:
            """Get normalized priority weights for weighted sampling."""
            if not candidates:
                return []
            priorities = [c.priority for c in candidates]
            min_priority = min(priorities)
            max_priority = max(priorities)
            if max_priority == min_priority:
                return [1.0] * len(candidates)
            # Normalize to 0-1, then square to emphasize high priorities
            weights = [
                ((p - min_priority) / (max_priority - min_priority)) ** 2
                for p in priorities
            ]
            # Add small base weight to ensure all candidates have some chance
            weights = [w + 0.1 for w in weights]
            total = sum(weights)
            return [w / total for w in weights]

        def _is_diverse_sequence(
            sequence: List[ActionCandidate],
            existing_sequences: List[List[ActionCandidate]],
        ) -> bool:
            """Check if sequence adds diversity to existing sequences."""
            if not securities_by_symbol or not existing_sequences:
                return True

            # Get countries/industries in new sequence
            new_countries = set()
            new_industries = set()
            for action in sequence:
                security = securities_by_symbol.get(action.symbol)
                if security:
                    if security.country:
                        new_countries.add(security.country)
                    if security.industry:
                        industries = [i.strip() for i in security.industry.split(",")]
                        new_industries.update(industries)

            # Check if this adds new diversity
            for existing_seq in existing_sequences[-10:]:  # Check last 10 sequences
                existing_countries = set()
                existing_industries = set()
                for action in existing_seq:
                    security = securities_by_symbol.get(action.symbol)
                    if security:
                        if security.country:
                            existing_countries.add(security.country)
                        if security.industry:
                            industries = [
                                i.strip() for i in security.industry.split(",")
                            ]
                            existing_industries.update(industries)

                # If too similar, not diverse
                country_overlap = len(new_countries & existing_countries) / max(
                    len(new_countries | existing_countries), 1
                )
                industry_overlap = len(new_industries & existing_industries) / max(
                    len(new_industries | existing_industries), 1
                )
                if country_overlap > 0.8 and industry_overlap > 0.8:
                    return False

            return True

        # Generate combinations with priority-based sampling
        sell_weights = _get_priority_weights(filtered_sells)
        buy_weights = _get_priority_weights(filtered_buys)

        attempts = 0
        max_attempts = max_combinations * 3  # Allow more attempts for diverse sequences

        # Early return if no opportunities
        if not filtered_sells and not filtered_buys:
            return sequences

        while len(sequences) < max_combinations and attempts < max_attempts:
            attempts += 1

            # Sample number of sells and buys
            num_sells = 0
            if filtered_sells and len(filtered_sells) > 0 and max_sells > 0:
                max_sells_for_rand = min(max_sells, len(filtered_sells))
                if max_sells_for_rand > 0:
                    num_sells = random.randint(1, max_sells_for_rand)

            num_buys = 0
            if filtered_buys and len(filtered_buys) > 0 and max_buys > 0:
                max_buys_for_rand = min(max_buys, len(filtered_buys))
                if max_buys_for_rand > 0:
                    num_buys = random.randint(1, max_buys_for_rand)

            if num_sells + num_buys > max_steps or (num_sells == 0 and num_buys == 0):
                continue

            # Weighted sampling of sells
            sell_combo = (
                random.choices(filtered_sells, weights=sell_weights, k=num_sells)
                if num_sells > 0
                else []
            )
            # Remove duplicates by symbol
            seen_symbols = set()
            unique_sell_combo = []
            for s in sell_combo:
                if s.symbol not in seen_symbols:
                    seen_symbols.add(s.symbol)
                    unique_sell_combo.append(s)
            sell_combo = unique_sell_combo

            # Weighted sampling of buys
            buy_combo = (
                random.choices(filtered_buys, weights=buy_weights, k=num_buys)
                if num_buys > 0
                else []
            )
            # Remove duplicates by symbol
            seen_symbols = set()
            unique_buy_combo = []
            for b in buy_combo:
                if b.symbol not in seen_symbols:
                    seen_symbols.add(b.symbol)
                    unique_buy_combo.append(b)
            buy_combo = unique_buy_combo

            # Create sequence: sells first, then buys
            sequence = sell_combo + buy_combo

            # Check diversity constraint
            if not _is_diverse_sequence(sequence, sequences):
                continue

            sequences.append(sequence)

        return sequences


# Auto-register
_enhanced_combinatorial_generator = EnhancedCombinatorialGenerator()
sequence_generator_registry.register(
    _enhanced_combinatorial_generator.name, _enhanced_combinatorial_generator
)
