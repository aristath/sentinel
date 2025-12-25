"""Recommendation-related domain events."""

from dataclasses import dataclass, field
from datetime import datetime
from app.domain.events.base import DomainEvent
from app.domain.models import Recommendation
from app.domain.value_objects.trade_side import TradeSide


@dataclass(frozen=True)
class RecommendationCreatedEvent(DomainEvent):
    """Event raised when a trade recommendation is created.
    
    This event represents a business event: a new trade recommendation
    has been generated for rebalancing.
    """
    recommendation: Recommendation
    occurred_at: datetime = field(default_factory=datetime.now)
    
    @property
    def symbol(self) -> str:
        """Stock symbol for the recommendation."""
        return self.recommendation.symbol
    
    @property
    def side(self) -> TradeSide:
        """Trade side (BUY or SELL)."""
        return self.recommendation.side
    
    @property
    def quantity(self) -> float:
        """Recommended quantity."""
        return self.recommendation.quantity
    
    @property
    def estimated_value(self) -> float:
        """Estimated trade value."""
        return self.recommendation.estimated_value

