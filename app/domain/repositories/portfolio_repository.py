"""Repository interface for portfolio snapshot data access."""

from abc import ABC, abstractmethod
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class PortfolioSnapshot:
    """Portfolio snapshot domain model."""
    date: str
    total_value: float
    cash_balance: float
    geo_eu_pct: Optional[float]
    geo_asia_pct: Optional[float]
    geo_us_pct: Optional[float]


class PortfolioRepository(ABC):
    """Abstract repository for portfolio snapshot operations."""

    @abstractmethod
    async def get_latest(self) -> Optional[PortfolioSnapshot]:
        """Get the latest portfolio snapshot."""
        pass

    @abstractmethod
    async def get_history(self, limit: int = 90) -> List[PortfolioSnapshot]:
        """Get portfolio history."""
        pass

    @abstractmethod
    async def create(self, snapshot: PortfolioSnapshot, auto_commit: bool = True) -> None:
        """
        Create a new portfolio snapshot.
        
        Args:
            snapshot: Portfolio snapshot to create
            auto_commit: If True, commit immediately. If False, caller manages transaction.
        """
        pass

    @abstractmethod
    async def get_latest_cash_balance(self) -> float:
        """Get cash balance from latest snapshot."""
        pass

