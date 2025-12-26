"""LED Matrix Display Service - Priority slots for text display.

Simple architecture:
- activity_text: Current activity (SYNCING, BUY X, etc) - highest priority
- default_text: Default ticker (portfolio + recommendations) - shown when no activity

No queue = no stale messages. Latest activity always shows immediately.
"""

from threading import Lock

_lock = Lock()
_activity_text: str = ""  # Current activity (SYNCING, BUY X, etc)
_default_text: str = ""  # Default ticker (recommendations)


def set_activity(text: str) -> None:
    """Set activity message (replaces previous, highest priority)."""
    global _activity_text
    with _lock:
        _activity_text = text


def clear_activity() -> None:
    """Clear activity message (falls back to default)."""
    global _activity_text
    with _lock:
        _activity_text = ""


def set_default(text: str) -> None:
    """Set default ticker text (shown when no activity)."""
    global _default_text
    with _lock:
        _default_text = text


def get_current_text() -> str:
    """Get text to display (activity > default)."""
    with _lock:
        return _activity_text or _default_text
