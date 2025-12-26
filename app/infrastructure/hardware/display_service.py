"""LED Matrix Display Service - 3-pool priority system for text display.

Priority ordering:
- error_text: Error messages (highest priority)
- processing_text: Processing/activity messages (medium priority)
- next_actions_text: Recommendations/next actions (lowest priority, default)

No queue = no stale messages. Highest priority text always shows immediately.
"""

from threading import Lock

_lock = Lock()
_error_text: str = ""  # Error messages (highest priority)
_processing_text: str = ""  # Processing/activity messages (medium priority)
_next_actions_text: str = ""  # Recommendations/next actions (lowest priority)


def set_error(text: str) -> None:
    """Set error message (highest priority, persists until cleared)."""
    global _error_text
    with _lock:
        _error_text = text


def clear_error() -> None:
    """Clear error message (falls back to processing or next_actions)."""
    global _error_text
    with _lock:
        _error_text = ""


def set_processing(text: str) -> None:
    """Set processing/activity message (medium priority)."""
    global _processing_text
    with _lock:
        _processing_text = text


def clear_processing() -> None:
    """Clear processing message (falls back to next_actions)."""
    global _processing_text
    with _lock:
        _processing_text = ""


def set_next_actions(text: str) -> None:
    """Set next actions/recommendations text (lowest priority, default)."""
    global _next_actions_text
    with _lock:
        _next_actions_text = text


def get_current_text() -> str:
    """Get text to display (error > processing > next_actions)."""
    with _lock:
        if _error_text:
            return _error_text
        elif _processing_text:
            return _processing_text
        else:
            return _next_actions_text
