"""Domain events for decoupled business logic.

Domain events represent something that happened in the domain that domain
experts care about. They are separate from infrastructure events (LED, etc.)
and represent business events like "Trade Executed", "Position Updated", etc.
"""

from app.domain.events.base import DomainEvent, DomainEventBus, get_event_bus
from app.domain.events.position_events import PositionUpdatedEvent
from app.domain.events.recommendation_events import RecommendationCreatedEvent
from app.domain.events.stock_events import StockAddedEvent
from app.domain.events.trade_events import TradeExecutedEvent

__all__ = [
    "DomainEvent",
    "DomainEventBus",
    "get_event_bus",
    "TradeExecutedEvent",
    "PositionUpdatedEvent",
    "RecommendationCreatedEvent",
    "StockAddedEvent",
]
