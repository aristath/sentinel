"""SSE Event Manager for Recommendation Updates.

Manages Server-Sent Events (SSE) subscriptions and broadcasting for real-time
recommendation updates when caches are invalidated.
"""

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, Optional

from app.infrastructure.events import SystemEvent, subscribe

logger = logging.getLogger(__name__)

# Global set of subscriber queues
_subscribers: set[asyncio.Queue] = set()
_subscribers_lock = asyncio.Lock()

# Cache for current invalidation timestamp to send on subscription
_current_invalidation: Optional[Dict[str, Any]] = None
_current_invalidation_lock = asyncio.Lock()


async def get_current_invalidation() -> Optional[Dict[str, Any]]:
    """Get cached current invalidation timestamp."""
    async with _current_invalidation_lock:
        return _current_invalidation


async def set_current_invalidation(invalidation: Dict[str, Any]) -> None:
    """Update cached current invalidation timestamp."""
    async with _current_invalidation_lock:
        global _current_invalidation
        _current_invalidation = invalidation


def _broadcast_to_queues(invalidation_data: Dict[str, Any]) -> None:
    """Broadcast invalidation data to all subscriber queues (thread-safe).

    This function can be called from sync context (event handlers).
    Uses put_nowait which is thread-safe for asyncio.Queue.

    Args:
        invalidation_data: Invalidation dictionary to broadcast
    """
    # Get all current subscribers
    # Note: We can't use async lock from sync context, so we access directly
    # This is safe because we're only reading and put_nowait is thread-safe
    queues = list(_subscribers)

    # Put data in all queues (put_nowait is thread-safe)
    for queue in queues:
        try:
            queue.put_nowait(invalidation_data)
        except asyncio.QueueFull:
            logger.warning("Subscriber queue full, dropping event")
        except Exception as e:
            logger.debug(f"Failed to send event to subscriber: {e}")
            # Note: Can't safely remove from sync context, will be cleaned up on next iteration


async def subscribe_recommendation_events() -> AsyncGenerator[Dict[str, Any], None]:
    """Subscribe to recommendation invalidation events via SSE.

    Yields invalidation dictionaries whenever recommendations are invalidated.
    Initial invalidation timestamp is sent immediately on subscription.

    Yields:
        Dictionary containing invalidation timestamp (timestamp, etc.)
    """
    # Create a queue for this subscriber
    queue: asyncio.Queue = asyncio.Queue()

    # Add to subscribers set (thread-safe)
    async with _subscribers_lock:
        _subscribers.add(queue)

    try:
        # Get initial state and send it
        import time

        initial_invalidation = await get_current_invalidation()
        if initial_invalidation:
            yield initial_invalidation
        else:
            # Send connection confirmation if no cached invalidation
            yield {"connected": True, "timestamp": time.time()}

        # Listen for events
        heartbeat_counter = 0
        while True:
            try:
                # Wait for event with timeout to allow graceful shutdown
                invalidation = await asyncio.wait_for(queue.get(), timeout=5.0)
                yield invalidation
                heartbeat_counter = 0  # Reset on actual event
            except asyncio.TimeoutError:
                # Send heartbeat every 5 seconds to keep connection alive
                import time

                heartbeat_counter += 1
                # Re-send current invalidation as heartbeat
                heartbeat_invalidation = await get_current_invalidation()
                if heartbeat_invalidation:
                    heartbeat_invalidation = heartbeat_invalidation.copy()
                    heartbeat_invalidation["heartbeat"] = heartbeat_counter
                    yield heartbeat_invalidation
                else:
                    # Send minimal heartbeat if no cached invalidation
                    yield {"heartbeat": heartbeat_counter, "timestamp": time.time()}
    finally:
        # Remove from subscribers on exit
        async with _subscribers_lock:
            _subscribers.discard(queue)


def _on_recommendations_invalidated(event: SystemEvent, **data: Any) -> None:
    """Handle recommendations invalidated event - broadcast invalidation update."""
    import time

    # Create invalidation data with timestamp
    invalidation_data = {
        "timestamp": time.time(),
        "invalidated": True,
    }

    # Update cache (async, but fire-and-forget from sync context)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(set_current_invalidation(invalidation_data))
    except RuntimeError:
        pass
    # Broadcast to subscribers (sync, thread-safe)
    _broadcast_to_queues(invalidation_data)


# Subscribe to recommendation invalidation events
subscribe(SystemEvent.RECOMMENDATIONS_INVALIDATED, _on_recommendations_invalidated)
