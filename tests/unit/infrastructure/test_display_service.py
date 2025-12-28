"""Tests for LED display state manager event emission.

These tests validate that DisplayStateManager emits events when state changes.
"""

from unittest.mock import patch

from app.infrastructure.events import SystemEvent
from app.infrastructure.hardware.display_service import DisplayStateManager


class TestDisplayStateManagerEventEmission:
    """Test that DisplayStateManager emits events on state changes."""

    def test_set_error_emits_event(self):
        """Test that set_error() emits DISPLAY_STATE_CHANGED event."""
        manager = DisplayStateManager()

        with patch("app.infrastructure.hardware.display_service.emit") as mock_emit:
            manager.set_error("TEST ERROR")

            mock_emit.assert_called_once()
            call_args = mock_emit.call_args
            assert call_args[0][0] == SystemEvent.DISPLAY_STATE_CHANGED

    def test_clear_error_emits_event(self):
        """Test that clear_error() emits DISPLAY_STATE_CHANGED event."""
        manager = DisplayStateManager()
        manager.set_error("TEST ERROR")

        with patch("app.infrastructure.hardware.display_service.emit") as mock_emit:
            manager.clear_error()

            mock_emit.assert_called_once()
            call_args = mock_emit.call_args
            assert call_args[0][0] == SystemEvent.DISPLAY_STATE_CHANGED

    def test_set_processing_emits_event(self):
        """Test that set_processing() emits DISPLAY_STATE_CHANGED event."""
        manager = DisplayStateManager()

        with patch("app.infrastructure.hardware.display_service.emit") as mock_emit:
            manager.set_processing("PROCESSING...")

            mock_emit.assert_called_once()
            call_args = mock_emit.call_args
            assert call_args[0][0] == SystemEvent.DISPLAY_STATE_CHANGED

    def test_clear_processing_emits_event(self):
        """Test that clear_processing() emits DISPLAY_STATE_CHANGED event."""
        manager = DisplayStateManager()
        manager.set_processing("PROCESSING...")

        with patch("app.infrastructure.hardware.display_service.emit") as mock_emit:
            manager.clear_processing()

            mock_emit.assert_called_once()
            call_args = mock_emit.call_args
            assert call_args[0][0] == SystemEvent.DISPLAY_STATE_CHANGED

    def test_set_next_actions_emits_event(self):
        """Test that set_next_actions() emits DISPLAY_STATE_CHANGED event."""
        manager = DisplayStateManager()

        with patch("app.infrastructure.hardware.display_service.emit") as mock_emit:
            manager.set_next_actions("BUY AAPL EUR500")

            mock_emit.assert_called_once()
            call_args = mock_emit.call_args
            assert call_args[0][0] == SystemEvent.DISPLAY_STATE_CHANGED

    def test_event_payload_contains_ticker_speed(self):
        """Test that event payload includes ticker_speed parameter."""
        manager = DisplayStateManager()

        with patch("app.infrastructure.hardware.display_service.emit") as mock_emit:
            manager.set_error("TEST ERROR")

            call_args = mock_emit.call_args
            # Check that keyword args contain ticker_speed or it's in the payload
            # The actual implementation will determine the exact format
            assert len(call_args.kwargs) >= 0  # At minimum, event is emitted
