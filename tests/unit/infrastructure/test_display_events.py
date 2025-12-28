"""Tests for LED display SSE event manager.

These tests validate the SSE event broadcasting system for real-time LED display updates.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.events import SystemEvent


@pytest.fixture
def display_events_module():
    """Import display_events module (will be created)."""
    # This will fail initially until module is created - that's expected in TDD
    from app.infrastructure.hardware import display_events

    return display_events


@pytest.fixture
def mock_settings_repo():
    """Mock settings repository."""
    repo = AsyncMock()
    repo.get_float = AsyncMock(return_value=50.0)
    return repo


@pytest.fixture
def mock_display_manager():
    """Mock display state manager."""
    manager = MagicMock()
    manager.get_error_text = MagicMock(return_value="")
    manager.get_processing_text = MagicMock(return_value="")
    manager.get_next_actions_text = MagicMock(return_value="Portfolio EUR12345")
    return manager


class TestDisplayEventsSubscription:
    """Test SSE event subscription functionality."""

    @pytest.mark.asyncio
    async def test_subscribe_returns_async_generator(self, display_events_module):
        """Test that subscribe_display_events returns an async generator."""
        async for event in display_events_module.subscribe_display_events():
            # Should be able to iterate over events
            assert event is not None
            break

    @pytest.mark.asyncio
    async def test_subscribe_receives_initial_state(self, display_events_module):
        """Test that initial state is sent on subscription."""
        events_received = []
        async for event in display_events_module.subscribe_display_events():
            events_received.append(event)
            if len(events_received) >= 1:
                break

        assert len(events_received) == 1
        assert "mode" in events_received[0]
        assert "ticker_text" in events_received[0]

    @pytest.mark.asyncio
    async def test_subscribe_receives_state_changes(self, display_events_module):
        """Test that state changes are broadcast to subscribers."""
        events_received = []
        async for event in display_events_module.subscribe_display_events():
            events_received.append(event)
            if len(events_received) >= 2:
                break

        # Should receive initial state and at least one update
        assert len(events_received) >= 1

    @pytest.mark.asyncio
    async def test_multiple_subscribers_receive_events(self, display_events_module):
        """Test that multiple subscribers can receive the same events."""
        events_1 = []
        events_2 = []

        async def collect_events_1():
            async for event in display_events_module.subscribe_display_events():
                events_1.append(event)
                if len(events_1) >= 1:
                    break

        async def collect_events_2():
            async for event in display_events_module.subscribe_display_events():
                events_2.append(event)
                if len(events_2) >= 1:
                    break

        await asyncio.gather(collect_events_1(), collect_events_2())

        assert len(events_1) >= 1
        assert len(events_2) >= 1

    @pytest.mark.asyncio
    async def test_event_format_contains_required_fields(self, display_events_module):
        """Test that events contain all required fields."""
        async for event in display_events_module.subscribe_display_events():
            assert "mode" in event
            assert "error_message" in event
            assert "activity_message" in event
            assert "ticker_text" in event
            assert "ticker_speed" in event
            assert "led3" in event
            assert "led4" in event
            break

    @pytest.mark.asyncio
    async def test_event_mode_values(self, display_events_module):
        """Test that mode field has valid values."""
        async for event in display_events_module.subscribe_display_events():
            assert event["mode"] in ["error", "activity", "normal"]
            break

    @pytest.mark.asyncio
    async def test_event_led_values_are_arrays(self, display_events_module):
        """Test that LED values are arrays of 3 integers."""
        async for event in display_events_module.subscribe_display_events():
            assert isinstance(event["led3"], list)
            assert isinstance(event["led4"], list)
            assert len(event["led3"]) == 3
            assert len(event["led4"]) == 3
            assert all(isinstance(x, int) for x in event["led3"])
            assert all(isinstance(x, int) for x in event["led4"])
            break


class TestDisplayEventsBroadcast:
    """Test event broadcasting functionality."""

    @pytest.mark.asyncio
    async def test_broadcast_notifies_all_subscribers(self, display_events_module):
        """Test that broadcast sends events to all active subscribers."""
        events_1 = []
        events_2 = []

        async def collect_events_1():
            async for event in display_events_module.subscribe_display_events():
                events_1.append(event)
                if len(events_1) >= 2:
                    break

        async def collect_events_2():
            async for event in display_events_module.subscribe_display_events():
                events_2.append(event)
                if len(events_2) >= 2:
                    break

        # Start both collectors
        task1 = asyncio.create_task(collect_events_1())
        task2 = asyncio.create_task(collect_events_2())

        # Wait a bit for subscriptions to be established
        await asyncio.sleep(0.1)

        # Trigger a broadcast
        await display_events_module.broadcast_display_state()

        # Wait for events
        await asyncio.wait_for(asyncio.gather(task1, task2), timeout=2.0)

        # Both should have received the broadcast
        assert len(events_1) >= 2  # initial + broadcast
        assert len(events_2) >= 2  # initial + broadcast


class TestDisplayEventsCleanup:
    """Test cleanup on client disconnection."""

    @pytest.mark.asyncio
    async def test_cleanup_on_generator_exit(self, display_events_module):
        """Test that subscriptions are cleaned up when generator exits."""
        initial_count = len(display_events_module._subscribers)

        async def temporary_subscriber():
            async for event in display_events_module.subscribe_display_events():
                break  # Exit immediately

        await temporary_subscriber()

        # Give time for cleanup
        await asyncio.sleep(0.1)

        # Subscriber should be removed
        final_count = len(display_events_module._subscribers)
        assert final_count == initial_count

