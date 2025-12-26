"""Standard response types for domain operations.

These types provide consistent interfaces for function returns across the codebase,
making it easier to handle results uniformly and enabling better refactoring.
"""

from app.domain.responses.calculation import CalculationResult
from app.domain.responses.score import ScoreResult
from app.domain.responses.service import ServiceResult
from app.domain.responses.list import ListResult

__all__ = [
    "CalculationResult",
    "ScoreResult",
    "ServiceResult",
    "ListResult",
]
