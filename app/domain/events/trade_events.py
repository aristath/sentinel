"""Trade-related domain events."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from app.domain.events.base import DomainEvent
from app.domain.models import Trade
from app.domain.value_objects.trade_side import TradeSide


@dataclass(frozen=True)
class TradeExecutedEvent(DomainEvent):
    """Event raised when a trade is executed.
    
    This event represents a business event that domain experts care about:
    a trade has been successfully executed and recorded.
    """
    trade: Trade
    
    @property
    def symbol(self) -> str:
        """Stock symbol for the trade."""
        return self.trade.symbol
    
    @property
    def side(self) -> TradeSide:
        """Trade side (BUY or SELL)."""
        return self.trade.side
    
    @property
    def quantity(self) -> float:
        """Trade quantity."""
        return self.trade.quantity
    
    @property
    def price(self) -> float:
        """Execution price."""
        return self.trade.price
    
    @property
    def order_id(self) -> Optional[str]:
        """Broker order ID."""
        return self.trade.order_id

