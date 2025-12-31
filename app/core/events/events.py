"""Event system for decoupled LED and system notifications.

This module provides a simple pub/sub event system that allows different
parts of the application to emit events without direct coupling to the
LED display or other listeners.

Example usage:
    from app.core.events import emit, subscribe, SystemEvent

    # Subscribe to events
    subscribe(SystemEvent.SYNC_START, lambda e, **d: print("Sync started"))

    # Emit events
    emit(SystemEvent.SYNC_START)
    emit(SystemEvent.TRADE_EXECUTED, is_buy=True, symbol="AAPL")
"""

import logging
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class SystemEvent(Enum):
    """System events that can trigger LED or other responses."""

    # Sync operations (LED 3 - Sync indicator)
    SYNC_START = "sync_start"
    SYNC_COMPLETE = "sync_complete"

    # External API calls (LED 1 - API indicator)
    API_CALL_START = "api_call_start"
    API_CALL_END = "api_call_end"

    # Data processing (LED 4 - Processing indicator)
    PROCESSING_START = "processing_start"
    PROCESSING_END = "processing_end"

    # Web requests (LED 2 - Web indicator)
    WEB_REQUEST = "web_request"

    # Trading events (Matrix - Trade animation)
    TRADE_EXECUTED = "trade_executed"

    # Error events (Matrix - Error scroll)
    ERROR_OCCURRED = "error_occurred"
    ERROR_CLEARED = "error_cleared"

    # Maintenance operations
    MAINTENANCE_START = "maintenance_start"
    MAINTENANCE_COMPLETE = "maintenance_complete"
    BACKUP_START = "backup_start"
    BACKUP_COMPLETE = "backup_complete"
    CLEANUP_START = "cleanup_start"
    CLEANUP_COMPLETE = "cleanup_complete"
    INTEGRITY_CHECK_START = "integrity_check_start"
    INTEGRITY_CHECK_COMPLETE = "integrity_check_complete"

    # Job lifecycle
    JOB_START = "job_start"
    JOB_COMPLETE = "job_complete"

    # Specific operations
    SCORE_REFRESH_START = "score_refresh_start"
    SCORE_REFRESH_COMPLETE = "score_refresh_complete"
    REBALANCE_START = "rebalance_start"
    REBALANCE_COMPLETE = "rebalance_complete"
    CASH_FLOW_SYNC_START = "cash_flow_sync_start"
    CASH_FLOW_SYNC_COMPLETE = "cash_flow_sync_complete"
    TRADE_SYNC_START = "trade_sync_start"
    TRADE_SYNC_COMPLETE = "trade_sync_complete"

    # Error categories
    API_ERROR = "api_error"
    DATABASE_ERROR = "database_error"
    BROKER_ERROR = "broker_error"

    # LED Display events
    DISPLAY_STATE_CHANGED = "display_state_changed"

    # Planner events
    PLANNER_BATCH_COMPLETE = "planner_batch_complete"
    PLANNER_SEQUENCES_GENERATED = "planner_sequences_generated"

    # Recommendation events
    RECOMMENDATIONS_INVALIDATED = "recommendations_invalidated"


# Event listeners storage
_listeners: dict[SystemEvent, list[Callable]] = {event: [] for event in SystemEvent}


def emit(event: SystemEvent, **data: Any) -> None:
    """Emit an event to all registered listeners.

    Events are fire-and-forget - listener exceptions are logged but never
    propagate to the caller. This ensures LED failures never affect
    business logic.

    Args:
        event: The event type to emit
        **data: Additional event data passed to listeners
    """
    for listener in _listeners[event]:
        try:
            listener(event, **data)
        except Exception as e:
            logger.debug(f"Event listener error for {event.value}: {e}")


def subscribe(event: SystemEvent, callback: Callable) -> None:
    """Subscribe a callback to an event.

    Args:
        event: The event type to subscribe to
        callback: Function to call when event is emitted.
                  Signature: callback(event: SystemEvent, **data)
    """
    _listeners[event].append(callback)


def unsubscribe(event: SystemEvent, callback: Callable) -> None:
    """Unsubscribe a callback from an event.

    Args:
        event: The event type to unsubscribe from
        callback: The callback to remove
    """
    try:
        _listeners[event].remove(callback)
    except ValueError:
        pass  # Callback wasn't subscribed


def clear_all_listeners() -> None:
    """Remove all event listeners. Useful for testing."""
    for event in SystemEvent:
        _listeners[event].clear()
