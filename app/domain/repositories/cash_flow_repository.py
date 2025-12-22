"""Repository interface for cash flow data access."""

from abc import ABC, abstractmethod
from typing import Optional, List

from app.domain.models.cash_flow import CashFlow


class CashFlowRepository(ABC):
    """Abstract repository for cash flow operations."""

    @abstractmethod
    async def create(self, cash_flow: CashFlow) -> CashFlow:
        """Create a new cash flow record."""
        pass

    @abstractmethod
    async def get_by_transaction_id(self, transaction_id: str) -> Optional[CashFlow]:
        """Get cash flow by transaction ID."""
        pass

    @abstractmethod
    async def get_all(self, limit: Optional[int] = None) -> List[CashFlow]:
        """Get all cash flows, optionally limited."""
        pass

    @abstractmethod
    async def get_by_date_range(self, start_date: str, end_date: str) -> List[CashFlow]:
        """Get cash flows within a date range."""
        pass

    @abstractmethod
    async def get_by_type(self, transaction_type: str) -> List[CashFlow]:
        """Get cash flows by transaction type."""
        pass

    @abstractmethod
    async def sync_from_api(self, transactions: List[dict]) -> int:
        """
        Sync transactions from API response.
        
        Upserts transactions (inserts new ones, updates existing ones based on transaction_id).
        
        Args:
            transactions: List of transaction dictionaries from API
            
        Returns:
            Number of transactions synced
        """
        pass
