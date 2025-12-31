"""Allocation repository - operations for allocation_targets table.

DEPRECATED: This module is kept for backward compatibility during migration.
Import from app.modules.allocation.database.allocation_repository instead.
"""

# Backward compatibility re-export (temporary - will be removed in Phase 5)
from app.modules.allocation.database.allocation_repository import AllocationRepository

__all__ = ["AllocationRepository"]
