"""LED Matrix Display Service - Single message system.

Latest message wins - always shows the most recent text that was set.
"""

from threading import Lock

from app.infrastructure.events import SystemEvent, emit


class DisplayStateManager:
    """Thread-safe display state manager with single message system.

    Manages display text and RGB LED states. Latest message always wins.
    Thread-safe operations ensure concurrent access from multiple jobs/API endpoints.
    """

    def __init__(self) -> None:
        """Initialize display state manager."""
        self._lock = Lock()
        self._current_text: str = ""  # Latest message (latest wins)
        self._led3: list[int] = [0, 0, 0]  # RGB LED 3 (sync indicator)
        self._led4: list[int] = [0, 0, 0]  # RGB LED 4 (processing indicator)

    def set_text(self, text: str) -> None:
        """Set display text (latest message wins).

        Args:
            text: Text to display
        """
        with self._lock:
            self._current_text = text
        emit(SystemEvent.DISPLAY_STATE_CHANGED)

    def get_current_text(self) -> str:
        """Get current display text.

        Returns:
            Current text to display
        """
        with self._lock:
            return self._current_text

    def set_led3(self, r: int, g: int, b: int) -> None:
        """Set RGB LED 3 color (sync indicator).

        Args:
            r: Red value (0-255)
            g: Green value (0-255)
            b: Blue value (0-255)
        """
        with self._lock:
            self._led3 = [r, g, b]
        emit(SystemEvent.DISPLAY_STATE_CHANGED)

    def get_led3(self) -> list[int]:
        """Get RGB LED 3 color.

        Returns:
            [r, g, b] values
        """
        with self._lock:
            return self._led3.copy()

    def set_led4(self, r: int, g: int, b: int) -> None:
        """Set RGB LED 4 color (processing indicator).

        Args:
            r: Red value (0-255)
            g: Green value (0-255)
            b: Blue value (0-255)
        """
        with self._lock:
            self._led4 = [r, g, b]
        emit(SystemEvent.DISPLAY_STATE_CHANGED)

    def get_led4(self) -> list[int]:
        """Get RGB LED 4 color.

        Returns:
            [r, g, b] values
        """
        with self._lock:
            return self._led4.copy()


# Singleton instance for dependency injection
_display_state_manager = DisplayStateManager()


# Module-level functions for backward compatibility
def set_text(text: str) -> None:
    """Set display text (latest message wins).

    Args:
        text: Text to display
    """
    _display_state_manager.set_text(text)


def get_current_text() -> str:
    """Get current display text.

    Returns:
        Current text to display
    """
    return _display_state_manager.get_current_text()


def set_led3(r: int, g: int, b: int) -> None:
    """Set RGB LED 3 color (sync indicator).

    Args:
        r: Red value (0-255)
        g: Green value (0-255)
        b: Blue value (0-255)
    """
    _display_state_manager.set_led3(r, g, b)


def set_led4(r: int, g: int, b: int) -> None:
    """Set RGB LED 4 color (processing indicator).

    Args:
        r: Red value (0-255)
        g: Green value (0-255)
        b: Blue value (0-255)
    """
    _display_state_manager.set_led4(r, g, b)
