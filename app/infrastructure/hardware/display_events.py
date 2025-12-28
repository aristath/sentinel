"""SSE Event Manager for LED Display State Changes.

Manages Server-Sent Events (SSE) subscriptions and broadcasting for real-time
LED display updates when DisplayStateManager state changes.
"""

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict

from app.infrastructure.events import SystemEvent, subscribe
from app.infrastructure.hardware.display_service import _display_state_manager

logger = logging.getLogger(__name__)

# Global set of subscriber queues
_subscribers: set[asyncio.Queue] = set()
_subscribers_lock = asyncio.Lock()


def _get_display_state_data(display_manager, ticker_speed: int = 50) -> Dict[str, Any]:
    """Get current display state as dictionary for SSE event.

    Args:
        display_manager: DisplayStateManager instance
        ticker_speed: Ticker speed in ms (default 50)

    Returns:
        Dictionary with display state fields
    """
    error_text = display_manager.get_error_text()
    processing_text = display_manager.get_processing_text()
    next_actions_text = display_manager.get_next_actions_text()

    # Determine mode based on current state
    if error_text:
        mode = "error"
    elif processing_text:
        mode = "activity"
    else:
        mode = "normal"

    return {
        "mode": mode,
        "error_message": error_text if error_text else None,
        "activity_message": processing_text if processing_text else None,
        "ticker_text": next_actions_text,
        "ticker_speed": ticker_speed,
        "led3": [0, 0, 0],
        "led4": [0, 0, 0],
    }


def _broadcast_to_queues(state_data: Dict[str, Any]) -> None:
    """Broadcast state data to all subscriber queues (thread-safe).

    This function can be called from sync context (event handlers).
    Uses put_nowait which is thread-safe for asyncio.Queue.

    Args:
        state_data: Display state dictionary to broadcast
    """
    # Get all current subscribers
    # Note: We can't use async lock from sync context, so we access directly
    # This is safe because we're only reading and put_nowait is thread-safe
    queues = list(_subscribers)

    # Put data in all queues (put_nowait is thread-safe)
    for queue in queues:
        try:
            queue.put_nowait(state_data)
        except asyncio.QueueFull:
            logger.warning("Subscriber queue full, dropping event")
        except Exception as e:
            logger.debug(f"Failed to send event to subscriber: {e}")
            # Note: Can't safely remove from sync context, will be cleaned up on next iteration


async def subscribe_display_events(
    ticker_speed: int = 50,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Subscribe to display state change events via SSE.

    Yields display state dictionaries whenever the state changes.
    Initial state is sent immediately on subscription.

    Args:
        ticker_speed: Initial ticker speed value

    Yields:
        Dictionary containing display state (mode, ticker_text, etc.)
    """
    # Create a queue for this subscriber
    queue: asyncio.Queue = asyncio.Queue()

    # Add to subscribers set (thread-safe)
    async with _subscribers_lock:
        _subscribers.add(queue)

    try:
        # Get initial state and send it
        initial_state = _get_display_state_data(_display_state_manager, ticker_speed)
        yield initial_state

        # Listen for events
        while True:
            try:
                # Wait for event with timeout to allow graceful shutdown
                state = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield state
            except asyncio.TimeoutError:
                # Timeout is normal, continue listening
                continue
    finally:
        # Remove from subscribers on exit
        async with _subscribers_lock:
            _subscribers.discard(queue)


def _on_display_state_changed(event: SystemEvent, **data: Any) -> None:
    """Event handler for DISPLAY_STATE_CHANGED events.

    This is called when DisplayStateManager emits a state change event.
    It broadcasts the current state to all SSE subscribers.

    Args:
        event: SystemEvent.DISPLAY_STATE_CHANGED
        **data: Event data (may contain ticker_speed)
    """
    ticker_speed = data.get("ticker_speed", 50)
    state_data = _get_display_state_data(_display_state_manager, ticker_speed)
    _broadcast_to_queues(state_data)


# Subscribe to display state changed events
subscribe(SystemEvent.DISPLAY_STATE_CHANGED, _on_display_state_changed)

