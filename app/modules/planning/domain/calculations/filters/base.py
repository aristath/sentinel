"""Base class for sequence filters.

Filters process and refine action sequences based on various criteria:
- Correlation awareness
- Diversity constraints
- Risk limits
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from app.modules.planning.domain.models import ActionCandidate


class SequenceFilter(ABC):
    """Base class for all sequence filters.

    Each filter implements a specific filtering strategy to refine
    action sequences (e.g., remove correlated positions, enforce diversity).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this filter."""
        pass

    @abstractmethod
    def default_params(self) -> Dict[str, Any]:
        """Default parameters for this filter."""
        pass

    @abstractmethod
    async def filter(
        self,
        sequences: List[List[ActionCandidate]],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]:
        """
        Filter action sequences based on criteria.

        Args:
            sequences: List of candidate sequences to filter
            params: Filter-specific parameters

        Returns:
            Filtered list of action sequences
        """
        pass


# Registry instance
from app.modules.planning.domain.calculations.base import Registry  # noqa: E402

sequence_filter_registry = Registry[SequenceFilter]()
