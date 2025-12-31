"""Backward compatibility re-export (temporary - will be removed in Phase 5)."""

from app.modules.system.jobs.sync_cycle import (
    _step_get_recommendation,
    _step_update_display,
    run_sync_cycle,
)

__all__ = ["run_sync_cycle", "_step_get_recommendation", "_step_update_display"]
