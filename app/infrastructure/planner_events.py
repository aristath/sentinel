"""SSE Event Manager for Planner Status Updates.

Manages Server-Sent Events (SSE) subscriptions and broadcasting for real-time
planner status updates when planner batches complete or sequences are generated.
"""

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, Optional

from app.infrastructure.events import SystemEvent, subscribe

logger = logging.getLogger(__name__)

# Global set of subscriber queues
_subscribers: set[asyncio.Queue] = set()
_subscribers_lock = asyncio.Lock()

# Cache for current planner status to send on subscription
_current_status: Optional[Dict[str, Any]] = None
_current_status_lock = asyncio.Lock()


async def get_current_status() -> Optional[Dict[str, Any]]:
    """Get cached current planner status."""
    async with _current_status_lock:
        return _current_status


async def set_current_status(status: Dict[str, Any]) -> None:
    """Update cached current planner status."""
    async with _current_status_lock:
        global _current_status
        _current_status = status


def _broadcast_to_queues(status_data: Dict[str, Any]) -> None:
    """
    Broadcast status update to all subscriber queues.

    This is called from the synchronous event handler context.
    Uses asyncio.run_coroutine_threadsafe to safely queue items.
    """

    async def _do_broadcast():
        async with _subscribers_lock:
            for queue in list(_subscribers):
                try:
                    queue.put_nowait(status_data)
                except asyncio.QueueFull:
                    logger.debug("Queue full, dropping subscriber")
                    _subscribers.discard(queue)
                except Exception as e:
                    logger.debug(f"Error broadcasting to queue: {e}")
                    # Note: Can't safely remove from sync context, will be cleaned up on next iteration

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_do_broadcast())
        else:
            asyncio.run(_do_broadcast())
    except RuntimeError:
        # No event loop, skip broadcast
        pass


async def subscribe_planner_events() -> AsyncGenerator[Dict[str, Any], None]:
    """Subscribe to planner status update events via SSE.

    Yields planner status dictionaries whenever status changes.
    Initial status is sent immediately on subscription.

    Yields:
        Dictionary containing planner status (has_sequences, total_sequences, etc.)
    """
    # Create a queue for this subscriber
    queue: asyncio.Queue = asyncio.Queue()

    # Add to subscribers set (thread-safe)
    async with _subscribers_lock:
        _subscribers.add(queue)

    try:
        # Get initial state and send it
        initial_status = await get_current_status()
        if initial_status:
            yield initial_status

        # Listen for events
        heartbeat_counter = 0
        while True:
            try:
                # Wait for event with timeout to allow graceful shutdown
                status = await asyncio.wait_for(queue.get(), timeout=5.0)
                yield status
                heartbeat_counter = 0  # Reset on actual event
            except asyncio.TimeoutError:
                # Send heartbeat every 5 seconds to keep connection alive
                heartbeat_counter += 1
                # Re-send current status as heartbeat
                heartbeat_status = await get_current_status()
                if heartbeat_status:
                    heartbeat_status = heartbeat_status.copy()
                    heartbeat_status["heartbeat"] = heartbeat_counter
                    yield heartbeat_status
    finally:
        # Remove from subscribers on exit
        async with _subscribers_lock:
            _subscribers.discard(queue)


def _on_planner_batch_complete(event: SystemEvent, **data: Any) -> None:
    """Handle planner batch complete event - broadcast status update."""
    # Extract status from event data if provided
    if "status" in data:
        status = data["status"]
        # Update cache
        asyncio.create_task(set_current_status(status))
        # Broadcast to subscribers
        _broadcast_to_queues(status)


def _on_planner_sequences_generated(event: SystemEvent, **data: Any) -> None:
    """Handle planner sequences generated event - broadcast status update."""
    # Extract status from event data if provided
    if "status" in data:
        status = data["status"]
        # Update cache
        asyncio.create_task(set_current_status(status))
        # Broadcast to subscribers
        _broadcast_to_queues(status)


# Subscribe to planner events
subscribe(SystemEvent.PLANNER_BATCH_COMPLETE, _on_planner_batch_complete)
subscribe(SystemEvent.PLANNER_SEQUENCES_GENERATED, _on_planner_sequences_generated)
