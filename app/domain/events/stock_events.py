"""Stock-related domain events."""

from dataclasses import dataclass
from app.domain.events.base import DomainEvent
from app.domain.models import Stock


@dataclass(frozen=True)
class StockAddedEvent(DomainEvent):
    """Event raised when a stock is added to the universe.
    
    This event represents a business event: a new stock has been added
    to the investment universe.
    """
    stock: Stock
    
    @property
    def symbol(self) -> str:
        """Stock symbol."""
        return self.stock.symbol
    
    @property
    def name(self) -> str:
        """Stock name."""
        return self.stock.name
    
    @property
    def geography(self) -> str:
        """Stock geography."""
        return self.stock.geography

