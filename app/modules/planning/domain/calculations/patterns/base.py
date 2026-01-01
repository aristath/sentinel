"""Base class for pattern generators.

Pattern generators create action sequences from opportunities based on
different trading strategies and patterns.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from app.modules.planning.domain.models import ActionCandidate


class PatternGenerator(ABC):
    """Base class for all pattern generators.

    Each pattern generator creates specific types of action sequences
    from the pool of opportunities (e.g., direct buy, profit taking, rebalance).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this pattern generator."""
        pass

    @abstractmethod
    def default_params(self) -> Dict[str, Any]:
        """Default parameters for this pattern generator."""
        pass

    @abstractmethod
    def generate(
        self,
        opportunities: Dict[str, List[ActionCandidate]],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]:
        """
        Generate action sequences based on opportunities.

        Args:
            opportunities: Dict mapping category to list of candidates
                          (profit_taking, averaging_down, rebalance_sells, etc.)
            params: Generator-specific parameters

        Returns:
            List of action sequences (each sequence is a list of ActionCandidates)
        """
        pass


# Registry instance (initialized on first import)
from app.modules.planning.domain.calculations.base import Registry  # noqa: E402

pattern_generator_registry = Registry[PatternGenerator]()
