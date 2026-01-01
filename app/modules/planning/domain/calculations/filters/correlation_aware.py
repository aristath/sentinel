"""Correlation-aware sequence filter.

Filters sequences to avoid highly correlated positions.
"""

import logging
from typing import Any, Dict, List

from app.domain.models import Security
from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.calculations.filters.base import (
    SequenceFilter,
    sequence_filter_registry,
)
from app.modules.planning.domain.models import ActionCandidate

logger = logging.getLogger(__name__)


class CorrelationAwareFilter(SequenceFilter):
    """Correlation-aware filter: Remove sequences with highly correlated buys."""

    @property
    def name(self) -> str:
        return "correlation_aware"

    def default_params(self) -> Dict[str, Any]:
        return {
            "correlation_threshold": 0.7,
            "securities": None,  # List[Security] for symbol lookup
            "correlation_matrix": None,  # Optional[Dict[str, float]]
        }

    async def filter(
        self,
        sequences: List[List[ActionCandidate]],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]:
        """
        Filter sequences to avoid highly correlated positions.

        Uses provided correlation data to identify and filter out
        sequences that would create highly correlated positions.

        Args:
            sequences: List of candidate sequences to filter
            params: Filter parameters including:
                - securities: List[Security] for symbol lookup
                - correlation_matrix: Optional[Dict[str, float]] with
                  keys in "symbol1:symbol2" format
                - correlation_threshold: float (default 0.7)

        Returns:
            Filtered list of sequences with reduced correlation

        Note:
            If correlation_matrix is not provided, all sequences are
            returned unfiltered. The caller (holistic_planner) is
            responsible for providing correlation data if available.
        """
        securities: List[Security] = params.get("securities", [])
        correlation_threshold = params.get("correlation_threshold", 0.7)
        correlations: Dict[str, float] = params.get("correlation_matrix") or {}

        if not sequences or not securities:
            return sequences

        # If no correlation data provided, return all sequences
        if not correlations:
            logger.debug(
                "Correlation filter: No correlation data provided, "
                "returning all sequences"
            )
            return sequences

        # Build symbol set from securities
        stock_symbols = {s.symbol for s in securities}

        filtered: List[List[ActionCandidate]] = []

        for sequence in sequences:
            # Get buy symbols from sequence
            buy_symbols = [
                action.symbol
                for action in sequence
                if action.side == TradeSide.BUY and action.symbol in stock_symbols
            ]

            # Check if any pair of buys is highly correlated
            has_high_correlation = False
            for i, symbol1 in enumerate(buy_symbols):
                for symbol2 in buy_symbols[i + 1 :]:
                    # Check correlation (both directions)
                    corr_key = f"{symbol1}:{symbol2}"
                    correlation = correlations.get(corr_key)
                    if correlation and abs(correlation) > correlation_threshold:
                        has_high_correlation = True
                        logger.debug(
                            f"Filtering sequence due to high correlation ({correlation:.2f}) "
                            f"between {symbol1} and {symbol2}"
                        )
                        break
                if has_high_correlation:
                    break

            if not has_high_correlation:
                filtered.append(sequence)

        if len(filtered) < len(sequences):
            logger.info(
                f"Correlation filtering: {len(sequences)} -> {len(filtered)} sequences "
                f"(removed {len(sequences) - len(filtered)} with high correlation)"
            )

        return filtered


# Auto-register
_correlation_aware_filter = CorrelationAwareFilter()
sequence_filter_registry.register(
    _correlation_aware_filter.name, _correlation_aware_filter
)
