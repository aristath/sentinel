"""Base domain event classes."""

import logging
from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="DomainEvent")


@dataclass(frozen=True)
class DomainEvent(ABC):
    """Base class for all domain events.

    Domain events represent something that happened in the domain that
    domain experts care about. They are immutable and contain all the
    information needed to understand what happened.
    """

    # occurred_at is defined in each subclass to avoid dataclass field ordering issues


class DomainEventBus:
    """Event bus for publishing and subscribing to domain events.

    Provides a simple pub/sub mechanism for domain events. Handlers are
    fire-and-forget - exceptions are logged but don't propagate.
    """

    def __init__(self):
        """Initialize event bus."""
        self._handlers: Dict[Type[DomainEvent], List[Callable[[DomainEvent], None]]] = (
            {}
        )

    def subscribe(self, event_type: Type[T], handler: Callable[[T], None]) -> None:
        """Subscribe a handler to an event type.

        Args:
            event_type: The domain event class to subscribe to
            handler: Function to call when event is published
                    Signature: handler(event: DomainEvent) -> None
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: Type[T], handler: Callable[[T], None]) -> None:
        """Unsubscribe a handler from an event type.

        Args:
            event_type: The domain event class to unsubscribe from
            handler: The handler function to remove
        """
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass  # Handler wasn't subscribed

    def publish(self, event: DomainEvent) -> None:
        """Publish a domain event to all subscribed handlers.

        Events are fire-and-forget - handler exceptions are logged but
        never propagate to the caller. This ensures event handler failures
        never affect business logic.

        Args:
            event: The domain event to publish
        """
        event_type = type(event)

        # Get handlers for this exact event type
        handlers = self._handlers.get(event_type, [])

        # Also get handlers for base DomainEvent (catch-all)
        base_handlers = self._handlers.get(DomainEvent, [])

        all_handlers = handlers + base_handlers

        for handler in all_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.warning(
                    f"Domain event handler error for {event_type.__name__}: {e}",
                    exc_info=True,
                )

    def clear(self) -> None:
        """Clear all event handlers. Useful for testing."""
        self._handlers.clear()


# Global event bus instance
_global_event_bus: Optional[DomainEventBus] = None


def get_event_bus() -> DomainEventBus:
    """Get the global domain event bus instance.

    Returns:
        Global DomainEventBus instance
    """
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = DomainEventBus()
    return _global_event_bus


def set_event_bus(bus: DomainEventBus) -> None:
    """Set the global domain event bus instance.

    Useful for testing or dependency injection.

    Args:
        bus: DomainEventBus instance to use globally
    """
    global _global_event_bus
    _global_event_bus = bus
