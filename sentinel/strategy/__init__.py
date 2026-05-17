"""Deterministic strategy primitives for portfolio construction and execution."""

from .contrarian import (
    classify_lot_size,
    compute_contrarian_signal,
    effective_opportunity_score,
    recent_dd252_min,
)

__all__ = [
    "classify_lot_size",
    "compute_contrarian_signal",
    "effective_opportunity_score",
    "recent_dd252_min",
]
