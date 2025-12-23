"""Repository interface for stock data access."""

from abc import ABC, abstractmethod
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class Stock:
    """Stock domain model."""
    symbol: str
    yahoo_symbol: Optional[str]
    name: str
    industry: Optional[str]
    geography: str
    priority_multiplier: float
    min_lot: int
    active: bool
    allow_buy: bool = True
    allow_sell: bool = False


class StockRepository(ABC):
    """Abstract repository for stock operations."""

    @abstractmethod
    async def get_by_symbol(self, symbol: str) -> Optional[Stock]:
        """Get stock by symbol."""
        pass

    @abstractmethod
    async def get_all_active(self) -> List[Stock]:
        """Get all active stocks."""
        pass

    @abstractmethod
    async def create(self, stock: Stock, auto_commit: bool = True) -> None:
        """
        Create a new stock.
        
        Args:
            stock: Stock to create
            auto_commit: If True, commit immediately. If False, caller manages transaction.
        """
        pass

    @abstractmethod
    async def update(self, current_symbol: str, auto_commit: bool = True, **updates) -> None:
        """
        Update stock fields.

        Args:
            current_symbol: Current stock symbol to update (renamed to avoid conflict with symbol in updates)
            auto_commit: If True, commit immediately. If False, caller manages transaction.
            **updates: Field updates (may include 'symbol' for renames)
        """
        pass

    @abstractmethod
    async def delete(self, symbol: str, auto_commit: bool = True) -> None:
        """
        Soft delete a stock (set active=False).
        
        Args:
            symbol: Stock symbol to delete
            auto_commit: If True, commit immediately. If False, caller manages transaction.
        """
        pass

    @abstractmethod
    async def get_with_scores(self) -> List[dict]:
        """Get all active stocks with their scores and positions."""
        pass
