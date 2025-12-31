"""Backward compatibility re-export (temporary - will be removed in Phase 5)."""

from app.modules.universe.domain.priority_calculator import (
    PriorityCalculator,
    PriorityInput,
)

__all__ = ["PriorityCalculator", "PriorityInput"]

