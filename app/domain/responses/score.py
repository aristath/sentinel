"""Standard score result types.

Provides consistent return types for all scoring functions.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Any


@dataclass
class ScoreResult:
    """Standard result for scoring functions.
    
    Use this for all scoring functions that compute a score,
    replacing tuple[float, Dict[str, float]] return types.
    
    Attributes:
        score: Main score value (0-1 range, typically)
        sub_scores: Component scores (e.g., {"cagr": 0.8, "sharpe": 0.7})
        confidence: How confident we are in this score (0-1, optional)
        metadata: Additional context (calculation details, warnings)
    """
    score: float
    sub_scores: Dict[str, float]
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Ensure score is always a float."""
        if self.sub_scores is None:
            self.sub_scores = {}
        if not isinstance(self.score, (int, float)):
            raise ValueError(f"score must be numeric, got {type(self.score)}")
        if self.confidence is not None and not (0 <= self.confidence <= 1):
            raise ValueError(f"confidence must be between 0 and 1, got {self.confidence}")

