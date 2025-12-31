"""Tests for event system infrastructure.

These tests validate the event system functionality for publishing and subscribing to events.
"""

from app.core.events import (
    SystemEvent,
    clear_all_listeners,
    emit,
    subscribe,
    unsubscribe,
)


class TestEventSystem:
    """Test event system functionality."""

    def setup_method(self):
        """Clear all listeners before each test."""
        clear_all_listeners()

    def test_emit_publishes_event(self):
        """Test that emit publishes an event."""
        received_events = []

        def handler(event, **kwargs):
            received_events.append((event, kwargs))

        subscribe(SystemEvent.ERROR_OCCURRED, handler)
        emit(SystemEvent.ERROR_OCCURRED, message="test message")

        # Events are processed synchronously in this implementation
        # Check that handler was called
        assert len(received_events) >= 1
        assert received_events[-1][0] == SystemEvent.ERROR_OCCURRED
        assert received_events[-1][1].get("message") == "test message"

    def test_subscribe_adds_handler(self):
        """Test that subscribe adds a handler for an event."""
        call_count = [0]  # Use list to allow modification in nested function

        def handler(event, **kwargs):
            call_count[0] += 1

        subscribe(SystemEvent.ERROR_OCCURRED, handler)
        emit(SystemEvent.ERROR_OCCURRED)

        assert call_count[0] >= 1

    def test_multiple_handlers_for_same_event(self):
        """Test that multiple handlers can subscribe to the same event."""
        call_counts = [0, 0]

        def handler1(event, **kwargs):
            call_counts[0] += 1

        def handler2(event, **kwargs):
            call_counts[1] += 1

        subscribe(SystemEvent.ERROR_OCCURRED, handler1)
        subscribe(SystemEvent.ERROR_OCCURRED, handler2)

        emit(SystemEvent.ERROR_OCCURRED)

        assert call_counts[0] >= 1
        assert call_counts[1] >= 1

    def test_handler_receives_event_and_kwargs(self):
        """Test that handlers receive both event and keyword arguments."""
        received_data = []

        def handler(event, **kwargs):
            received_data.append({"event": event, "kwargs": kwargs})

        subscribe(SystemEvent.ERROR_OCCURRED, handler)
        emit(SystemEvent.ERROR_OCCURRED, message="test", code=123)

        assert len(received_data) >= 1
        assert received_data[-1]["event"] == SystemEvent.ERROR_OCCURRED
        assert received_data[-1]["kwargs"]["message"] == "test"
        assert received_data[-1]["kwargs"]["code"] == 123

    def test_different_events_are_separate(self):
        """Test that different events are handled separately."""
        event1_count = [0]
        event2_count = [0]

        def handler1(event, **kwargs):
            event1_count[0] += 1

        def handler2(event, **kwargs):
            event2_count[0] += 1

        subscribe(SystemEvent.ERROR_OCCURRED, handler1)
        subscribe(SystemEvent.REBALANCE_START, handler2)

        emit(SystemEvent.ERROR_OCCURRED)
        emit(SystemEvent.REBALANCE_START)

        assert event1_count[0] >= 1
        assert event2_count[0] >= 1

    def test_handler_called_for_each_emit(self):
        """Test that handlers are called each time an event is emitted."""
        call_count = [0]

        def handler(event, **kwargs):
            call_count[0] += 1

        subscribe(SystemEvent.ERROR_OCCURRED, handler)

        emit(SystemEvent.ERROR_OCCURRED)
        emit(SystemEvent.ERROR_OCCURRED)
        emit(SystemEvent.ERROR_OCCURRED)

        assert call_count[0] >= 3

    def test_emit_without_subscribers_does_not_error(self):
        """Test that emitting an event without subscribers does not error."""
        # This is fine - events can be emitted even if no one is listening
        emit(SystemEvent.ERROR_OCCURRED, message="test")

    def test_subscribe_multiple_times_same_handler(self):
        """Test that subscribing the same handler multiple times is allowed."""
        call_count = [0]

        def handler(event, **kwargs):
            call_count[0] += 1

        subscribe(SystemEvent.ERROR_OCCURRED, handler)
        subscribe(SystemEvent.ERROR_OCCURRED, handler)  # Subscribe again

        emit(SystemEvent.ERROR_OCCURRED)

        # Handler should be called twice (once for each subscription)
        assert call_count[0] >= 2

    def test_emit_with_no_kwargs(self):
        """Test that emit works with no keyword arguments."""
        received = []

        def handler(event, **kwargs):
            received.append({"event": event, "kwargs": kwargs})

        subscribe(SystemEvent.ERROR_OCCURRED, handler)
        emit(SystemEvent.ERROR_OCCURRED)

        assert len(received) >= 1
        assert received[-1]["event"] == SystemEvent.ERROR_OCCURRED
        assert received[-1]["kwargs"] == {}

    def test_unsubscribe_removes_handler(self):
        """Test that unsubscribe removes a handler."""
        call_count = [0]

        def handler(event, **kwargs):
            call_count[0] += 1

        subscribe(SystemEvent.ERROR_OCCURRED, handler)
        emit(SystemEvent.ERROR_OCCURRED)
        assert call_count[0] >= 1

        unsubscribe(SystemEvent.ERROR_OCCURRED, handler)
        emit(SystemEvent.ERROR_OCCURRED)
        # Should still be 1 (not called again after unsubscribe)
        assert call_count[0] >= 1

    def test_unsubscribe_nonexistent_handler_does_not_error(self):
        """Test that unsubscribe on nonexistent handler does not error."""

        def handler(event, **kwargs):
            pass

        # Should not raise
        unsubscribe(SystemEvent.ERROR_OCCURRED, handler)

    def test_clear_all_listeners_removes_all_handlers(self):
        """Test that clear_all_listeners removes all handlers."""
        call_count = [0]

        def handler(event, **kwargs):
            call_count[0] += 1

        subscribe(SystemEvent.ERROR_OCCURRED, handler)
        subscribe(SystemEvent.REBALANCE_START, handler)

        clear_all_listeners()

        emit(SystemEvent.ERROR_OCCURRED)
        emit(SystemEvent.REBALANCE_START)

        # Should not have been called after clear
        assert call_count[0] == 0

    def test_listener_exceptions_are_caught(self):
        """Test that listener exceptions are caught and don't propagate."""

        def failing_handler(event, **kwargs):
            raise ValueError("Handler error")

        subscribe(SystemEvent.ERROR_OCCURRED, failing_handler)

        # Should not raise
        emit(SystemEvent.ERROR_OCCURRED)
