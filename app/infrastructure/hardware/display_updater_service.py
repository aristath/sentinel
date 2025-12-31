"""Centralized display update service.

DEPRECATED: This module is kept for backward compatibility during migration.
Import from app.modules.display.services.display_updater_service instead.
"""

# Backward compatibility re-export (temporary - will be removed in Phase 5)
from app.modules.display.services.display_updater_service import update_display_ticker

__all__ = ["update_display_ticker"]
