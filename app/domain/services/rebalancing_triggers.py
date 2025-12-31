"""Backward compatibility re-export (temporary - will be removed in Phase 5)."""

from app.modules.rebalancing.domain.rebalancing_triggers import (
    check_rebalance_triggers,
)

__all__ = ["check_rebalance_triggers"]

