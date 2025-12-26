"""Standard response types for domain operations.

These types provide consistent interfaces for function returns across the codebase,
making it easier to handle results uniformly and enabling better refactoring.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List, Generic, TypeVar

T = TypeVar('T')


@dataclass
class ScoreResult:
    """Standard result for scoring functions.

    Replaces the tuple[float, Dict[str, float]] pattern used by scoring functions.

    Example:
        # Before
        return (0.85, {"cagr": 0.8, "sharpe": 0.7})

        # After
        return ScoreResult(
            score=0.85,
            sub_scores={"cagr": 0.8, "sharpe": 0.7}
        )
    """
    score: float  # Main score (0-1)
    sub_scores: Dict[str, float] = field(default_factory=dict)  # Component scores
    confidence: Optional[float] = None  # How confident we are in this score (0-1)
    metadata: Optional[Dict[str, Any]] = None  # Additional context

    def to_tuple(self) -> tuple:
        """Convert to legacy tuple format for backward compatibility."""
        return (self.score, self.sub_scores)

    @classmethod
    def from_tuple(cls, t: tuple) -> "ScoreResult":
        """Create from legacy tuple format."""
        return cls(score=t[0], sub_scores=t[1] if len(t) > 1 else {})


@dataclass
class CalculationResult:
    """Standard result for calculation functions.

    Replaces Optional[float] pattern with richer information about the calculation.

    Example:
        # Before
        if insufficient_data:
            return None
        return 0.11

        # After
        if insufficient_data:
            return CalculationResult(
                value=0.0,
                success=False,
                error="insufficient_data"
            )
        return CalculationResult(
            value=0.11,
            sub_components={"5y": 0.11, "10y": 0.10}
        )
    """
    value: float  # The calculated value
    success: bool = True  # Whether calculation succeeded
    sub_components: Dict[str, float] = field(default_factory=dict)  # Breakdown
    error: Optional[str] = None  # Error message if failed
    metadata: Optional[Dict[str, Any]] = None  # Additional context (e.g., months_used)


@dataclass
class ServiceResult(Generic[T]):
    """Generic service result with success/error handling.

    Example:
        # Before
        async def get_recommendations(...) -> List[Recommendation]:
            if error:
                return []  # or raise exception
            return recommendations

        # After
        async def get_recommendations(...) -> ServiceResult[List[Recommendation]]:
            if error:
                return ServiceResult(
                    success=False,
                    error="Failed to fetch recommendations"
                )
            return ServiceResult(
                success=True,
                data=recommendations
            )
    """
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ListResult(Generic[T]):
    """Standard result for list operations.

    Example:
        return ListResult(
            items=stocks,
            total=len(stocks),
            metadata={"filtered": 5}
        )
    """
    items: List[T]
    total: int
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.total == 0 and self.items:
            self.total = len(self.items)
