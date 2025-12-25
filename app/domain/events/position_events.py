"""Position-related domain events."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from app.domain.events.base import DomainEvent
from app.domain.models import Position


@dataclass(frozen=True)
class PositionUpdatedEvent(DomainEvent):
    """Event raised when a position is updated.
    
    This event represents a business event: a position has been updated
    (quantity, price, etc. changed).
    """
    position: Position
    occurred_at: datetime = field(default_factory=datetime.now)
    
    @property
    def symbol(self) -> str:
        """Stock symbol for the position."""
        return self.position.symbol
    
    @property
    def quantity(self) -> float:
        """Position quantity."""
        return self.position.quantity
    
    @property
    def market_value_eur(self) -> Optional[float]:
        """Market value in EUR."""
        return self.position.market_value_eur

