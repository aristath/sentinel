"""Standard score result types.

Provides consistent return types for all scoring functions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


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
