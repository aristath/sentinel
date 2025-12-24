"""Repository interface for position data access."""

from abc import ABC, abstractmethod
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class Position:
    """Position domain model."""
    symbol: str
    quantity: float
    avg_price: float
    current_price: Optional[float]
    currency: str
    currency_rate: float
    market_value_eur: Optional[float]
    last_updated: Optional[str]
    first_bought_at: Optional[str] = None  # When position was first opened
    last_sold_at: Optional[str] = None     # Last sell date for cooldown


class PositionRepository(ABC):
    """Abstract repository for position operations."""

    @abstractmethod
    async def get_by_symbol(self, symbol: str) -> Optional[Position]:
        """Get position by symbol."""
        pass

    @abstractmethod
    async def get_all(self) -> List[Position]:
        """Get all positions."""
        pass

    @abstractmethod
    async def upsert(self, position: Position, auto_commit: bool = True) -> None:
        """
        Insert or update a position.
        
        Args:
            position: Position to upsert
            auto_commit: If True, commit immediately. If False, caller manages transaction.
        """
        pass

    @abstractmethod
    async def delete_all(self, auto_commit: bool = True) -> None:
        """
        Delete all positions (used during sync).
        
        Args:
            auto_commit: If True, commit immediately. If False, caller manages transaction.
        """
        pass

    @abstractmethod
    async def get_with_stock_info(self) -> List[dict]:
        """Get all positions with stock information."""
        pass

    @abstractmethod
    async def update_last_sold_at(self, symbol: str, auto_commit: bool = True) -> None:
        """
        Update the last_sold_at timestamp for a position after a sell.

        Args:
            symbol: Stock symbol
            auto_commit: If True, commit immediately. If False, caller manages transaction.
        """
        pass

