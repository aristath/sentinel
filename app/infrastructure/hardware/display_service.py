"""LED Matrix Display Service - 3-pool priority system for text display.

Priority ordering:
- error_text: Error messages (highest priority)
- processing_text: Processing/activity messages (medium priority)
- next_actions_text: Recommendations/next actions (lowest priority, default)

No queue = no stale messages. Highest priority text always shows immediately.
"""

from threading import Lock

from app.infrastructure.events import SystemEvent, emit


class DisplayStateManager:
    """Thread-safe display state manager with 3-pool priority system.

    Manages three priority levels of display text:
    - Error messages (highest priority)
    - Processing/activity messages (medium priority)
    - Next actions/recommendations (lowest priority, default)

    Thread-safe operations ensure concurrent access from multiple jobs/API endpoints.
    """

    def __init__(self) -> None:
        """Initialize display state manager."""
        self._lock = Lock()
        self._error_text: str = ""  # Error messages (highest priority)
        self._processing_text: str = (
            ""  # Processing/activity messages (medium priority)
        )
        self._next_actions_text: str = (
            ""  # Recommendations/next actions (lowest priority)
        )

    def set_error(self, text: str) -> None:
        """Set error message (highest priority, persists until cleared)."""
        with self._lock:
            self._error_text = text
        emit(SystemEvent.DISPLAY_STATE_CHANGED)

    def clear_error(self) -> None:
        """Clear error message (falls back to processing or next_actions)."""
        with self._lock:
            self._error_text = ""
        emit(SystemEvent.DISPLAY_STATE_CHANGED)

    def set_processing(self, text: str) -> None:
        """Set processing/activity message (medium priority)."""
        with self._lock:
            self._processing_text = text
        emit(SystemEvent.DISPLAY_STATE_CHANGED)

    def clear_processing(self) -> None:
        """Clear processing message (falls back to next_actions)."""
        with self._lock:
            self._processing_text = ""
        emit(SystemEvent.DISPLAY_STATE_CHANGED)

    def set_next_actions(self, text: str) -> None:
        """Set next actions/recommendations text (lowest priority, default)."""
        with self._lock:
            self._next_actions_text = text
        emit(SystemEvent.DISPLAY_STATE_CHANGED)

    def get_current_text(self) -> str:
        """Get text to display (error > processing > next_actions)."""
        with self._lock:
            if self._error_text:
                return self._error_text
            elif self._processing_text:
                return self._processing_text
            else:
                return self._next_actions_text

    def get_error_text(self) -> str:
        """Get current error text (for API endpoints)."""
        with self._lock:
            return self._error_text

    def get_processing_text(self) -> str:
        """Get current processing text (for API endpoints)."""
        with self._lock:
            return self._processing_text

    def get_next_actions_text(self) -> str:
        """Get current next actions text (for API endpoints)."""
        with self._lock:
            return self._next_actions_text


# Singleton instance for dependency injection
_display_state_manager = DisplayStateManager()


# Backward compatibility: module-level variables for status.py
# These are kept in sync with the manager for backward compatibility
_error_text: str = ""
_processing_text: str = ""
_next_actions_text: str = ""


def _sync_module_vars() -> None:
    """Sync module-level variables with manager state (for backward compatibility)."""
    global _error_text, _processing_text, _next_actions_text
    _error_text = _display_state_manager.get_error_text()
    _processing_text = _display_state_manager.get_processing_text()
    _next_actions_text = _display_state_manager.get_next_actions_text()


# Initialize module-level variables
_sync_module_vars()


# Backward compatibility: module-level functions delegate to singleton and sync vars
# These will be deprecated in favor of using the DisplayStateManager directly
def set_error(text: str) -> None:
    """Set error message (highest priority, persists until cleared)."""
    _display_state_manager.set_error(text)
    _sync_module_vars()


def clear_error() -> None:
    """Clear error message (falls back to processing or next_actions)."""
    _display_state_manager.clear_error()
    _sync_module_vars()
    # Event already emitted by _display_state_manager.clear_error()


def set_processing(text: str) -> None:
    """Set processing/activity message (medium priority)."""
    _display_state_manager.set_processing(text)
    _sync_module_vars()
    # Event already emitted by _display_state_manager.set_processing()


def clear_processing() -> None:
    """Clear processing message (falls back to next_actions)."""
    _display_state_manager.clear_processing()
    _sync_module_vars()
    # Event already emitted by _display_state_manager.clear_processing()


def set_next_actions(text: str) -> None:
    """Set next actions/recommendations text (lowest priority, default)."""
    _display_state_manager.set_next_actions(text)
    _sync_module_vars()
    # Event already emitted by _display_state_manager.set_next_actions()


def get_current_text() -> str:
    """Get text to display (error > processing > next_actions)."""
    return _display_state_manager.get_current_text()
