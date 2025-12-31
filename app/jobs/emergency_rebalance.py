"""Backward compatibility re-export (temporary - will be removed in Phase 5)."""

from app.modules.rebalancing.jobs.emergency_rebalance import (
    check_and_rebalance_immediately,
)

__all__ = ["check_and_rebalance_immediately"]

