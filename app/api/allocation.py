"""Allocation target management API endpoints.

DEPRECATED: This module is kept for backward compatibility during migration.
Import from app.modules.allocation.api.allocation instead.
"""

# Backward compatibility re-export (temporary - will be removed in Phase 5)
from app.modules.allocation.api.allocation import router

__all__ = ["router"]
