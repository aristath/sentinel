"""Sequence generator modules.

Auto-imports all generators to trigger registration.
"""

# Import all generators to trigger auto-registration
from app.modules.planning.domain.calculations.sequences import (  # noqa: F401
    combinatorial,
    constraint_relaxation,
    enhanced_combinatorial,
    partial_execution,
)

__all__ = [
    "combinatorial",
    "constraint_relaxation",
    "enhanced_combinatorial",
    "partial_execution",
]
