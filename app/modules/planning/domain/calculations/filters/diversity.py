"""Diversity selection filter.

Balances priority with diversity to avoid concentration in similar securities.
Uses clustering by country/industry to ensure portfolio breadth.
"""

from collections import defaultdict
from typing import Any, Dict, List, Set

from app.modules.planning.domain.calculations.filters.base import (
    SequenceFilter,
    sequence_filter_registry,
)
from app.modules.planning.domain.models import ActionCandidate


class DiversitySelectionFilter(SequenceFilter):
    """
    Selects diverse opportunities using clustering.

    Balances pure priority-based selection with diversity across:
    - Geographic regions (countries)
    - Industry sectors
    - Individual securities

    This prevents the planner from over-concentrating in a few
    high-priority securities while ignoring important diversification.

    Algorithm:
    1. Group opportunities by country/industry
    2. Calculate diversity score for each sequence
    3. Combine priority and diversity scores based on weight
    4. Select top sequences by combined score
    """

    @property
    def name(self) -> str:
        return "diversity"

    def default_params(self) -> Dict[str, Any]:
        return {
            "diversity_weight": 0.3,  # Balance: 0.0=pure priority, 1.0=pure diversity
            "max_sequences": 50,  # Maximum sequences to keep after filtering
            "min_diversity_score": 0.0,  # Minimum diversity score to include
        }

    async def filter(
        self,
        sequences: List[List[ActionCandidate]],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]:
        """
        Filter sequences to balance priority and diversity.

        Args:
            sequences: List of candidate sequences
            params: Filter parameters

        Returns:
            Filtered list emphasizing diverse sequences
        """
        diversity_weight = params.get("diversity_weight", 0.3)
        max_sequences = params.get("max_sequences", 50)
        min_diversity_score = params.get("min_diversity_score", 0.0)

        if not sequences:
            return []

        # Calculate combined scores for each sequence
        scored_sequences: List[tuple[float, List[ActionCandidate]]] = []

        for sequence in sequences:
            priority_score = self._calculate_priority_score(sequence)
            diversity_score = self._calculate_diversity_score(sequence)

            # Combined score: weighted average of priority and diversity
            combined_score = (
                1.0 - diversity_weight
            ) * priority_score + diversity_weight * diversity_score

            # Filter by minimum diversity
            if diversity_score >= min_diversity_score:
                scored_sequences.append((combined_score, sequence))

        # Sort by combined score (descending)
        scored_sequences.sort(key=lambda x: x[0], reverse=True)

        # Return top N sequences
        filtered = [seq for score, seq in scored_sequences[:max_sequences]]

        return filtered

    def _calculate_priority_score(self, sequence: List[ActionCandidate]) -> float:
        """Calculate average priority score for a sequence."""
        if not sequence:
            return 0.0
        return sum(action.priority for action in sequence) / len(sequence)

    def _calculate_diversity_score(self, sequence: List[ActionCandidate]) -> float:
        """
        Calculate diversity score for a sequence.

        Measures how well-distributed the sequence is across:
        - Different symbols
        - Different countries (if available)
        - Different categories

        Returns:
            Diversity score (0.0 to 1.0)
        """
        if not sequence:
            return 0.0

        # Count unique elements
        unique_symbols: Set[str] = set()
        unique_tags: Set[str] = set()
        country_counts: Dict[str, int] = defaultdict(int)

        for action in sequence:
            unique_symbols.add(action.symbol)
            for tag in action.tags:
                unique_tags.add(tag)

            # Try to get country from action if available
            # (This would require ActionCandidate to have country info)
            # For now, we'll use symbol prefix as a proxy
            # In production, this should use actual security metadata
            country_prefix = action.symbol[:2] if len(action.symbol) >= 2 else "XX"
            country_counts[country_prefix] += 1

        # Calculate diversity components
        symbol_diversity = len(unique_symbols) / len(sequence)  # Max 1.0
        tag_diversity = len(unique_tags) / min(
            len(sequence), 5
        )  # Normalized by expected max tags

        # Country diversity: Penalize concentration
        max_country_concentration = (
            max(country_counts.values()) / len(sequence) if country_counts else 1.0
        )
        country_diversity = 1.0 - max_country_concentration

        # Combined diversity score (weighted average)
        diversity_score = (
            0.4 * symbol_diversity  # Most important: different securities
            + 0.3 * country_diversity  # Geographic spread
            + 0.3 * tag_diversity  # Strategy diversity (via tags)
        )

        return min(1.0, diversity_score)  # Cap at 1.0


# Auto-register
_diversity_filter = DiversitySelectionFilter()
sequence_filter_registry.register(_diversity_filter.name, _diversity_filter)
