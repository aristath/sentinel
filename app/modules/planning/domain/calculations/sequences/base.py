"""Base class for sequence generators.

Sequence generators create action sequences through various strategies:
- Combinatorial combination of opportunities
- Diverse selection algorithms
- Enhanced combination strategies
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from app.modules.planning.domain.models import ActionCandidate


class SequenceGenerator(ABC):
    """Base class for all sequence generators.

    Each sequence generator implements a specific strategy for creating
    action sequences from opportunities (e.g., combinatorial, diverse selection).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this sequence generator."""
        pass

    @abstractmethod
    def default_params(self) -> Dict[str, Any]:
        """Default parameters for this sequence generator."""
        pass

    @abstractmethod
    def generate(
        self,
        opportunities: List[ActionCandidate],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]:
        """
        Generate action sequences from opportunities.

        Args:
            opportunities: List of candidate actions to combine
            params: Generator-specific parameters

        Returns:
            List of action sequences (each sequence is a list of ActionCandidates)
        """
        pass


# Registry instance
from app.modules.planning.domain.calculations.base import Registry  # noqa: E402

sequence_generator_registry = Registry[SequenceGenerator]()
