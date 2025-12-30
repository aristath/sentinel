"""Tests for LED display state manager event emission.

These tests validate that DisplayStateManager emits events when state changes.
"""

from unittest.mock import patch

from app.infrastructure.events import SystemEvent
from app.infrastructure.hardware.display_service import DisplayStateManager


class TestDisplayStateManagerEventEmission:
    """Test that DisplayStateManager emits events on state changes."""

    def test_set_text_emits_event(self):
        """Test that set_text() emits DISPLAY_STATE_CHANGED event."""
        manager = DisplayStateManager()

        with patch("app.infrastructure.hardware.display_service.emit") as mock_emit:
            manager.set_text("TEST MESSAGE")

            mock_emit.assert_called_once()
            call_args = mock_emit.call_args
            assert call_args[0][0] == SystemEvent.DISPLAY_STATE_CHANGED

    def test_get_current_text_returns_latest(self):
        """Test that get_current_text() returns the latest message."""
        manager = DisplayStateManager()

        manager.set_text("FIRST MESSAGE")
        assert manager.get_current_text() == "FIRST MESSAGE"

        manager.set_text("SECOND MESSAGE")
        assert manager.get_current_text() == "SECOND MESSAGE"

    def test_set_led3_emits_event(self):
        """Test that set_led3() emits DISPLAY_STATE_CHANGED event."""
        manager = DisplayStateManager()

        with patch("app.infrastructure.hardware.display_service.emit") as mock_emit:
            manager.set_led3(0, 0, 255)

            mock_emit.assert_called_once()
            call_args = mock_emit.call_args
            assert call_args[0][0] == SystemEvent.DISPLAY_STATE_CHANGED

    def test_set_led4_emits_event(self):
        """Test that set_led4() emits DISPLAY_STATE_CHANGED event."""
        manager = DisplayStateManager()

        with patch("app.infrastructure.hardware.display_service.emit") as mock_emit:
            manager.set_led4(0, 255, 0)

            mock_emit.assert_called_once()
            call_args = mock_emit.call_args
            assert call_args[0][0] == SystemEvent.DISPLAY_STATE_CHANGED

    def test_get_led3_returns_value(self):
        """Test that get_led3() returns the LED color."""
        manager = DisplayStateManager()

        manager.set_led3(255, 0, 0)
        assert manager.get_led3() == [255, 0, 0]

    def test_get_led4_returns_value(self):
        """Test that get_led4() returns the LED color."""
        manager = DisplayStateManager()

        manager.set_led4(0, 255, 0)
        assert manager.get_led4() == [0, 255, 0]
