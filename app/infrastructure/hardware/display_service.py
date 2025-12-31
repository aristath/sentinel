"""LED Matrix Display Service - Single message system.

DEPRECATED: This module is kept for backward compatibility during migration.
Import from app.modules.display.services.display_service instead.
"""

# Backward compatibility re-exports (temporary - will be removed in Phase 5)
from app.modules.display.services.display_service import (
    DisplayStateManager,
    _display_state_manager,
    get_current_text,
    set_led3,
    set_led4,
    set_text,
)

__all__ = [
    "DisplayStateManager",
    "_display_state_manager",
    "set_text",
    "get_current_text",
    "set_led3",
    "set_led4",
]
