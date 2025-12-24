"""Repository interface for allocation target data access."""

from abc import ABC, abstractmethod
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class AllocationTarget:
    """Allocation target domain model."""
    type: str  # 'geography' or 'industry'
    name: str
    target_pct: float  # Weight from -1 to +1


class AllocationRepository(ABC):
    """Abstract repository for allocation target operations."""

    @abstractmethod
    async def get_all(self) -> Dict[str, float]:
        """Get all allocation targets as dict with key 'type:name'."""
        pass

    @abstractmethod
    async def get_by_type(self, target_type: str) -> List[AllocationTarget]:
        """Get allocation targets by type (geography or industry)."""
        pass

    @abstractmethod
    async def upsert(self, target: AllocationTarget, auto_commit: bool = True) -> None:
        """
        Insert or update an allocation target.
        
        Args:
            target: Allocation target to upsert
            auto_commit: If True, commit immediately. If False, caller manages transaction.
        """
        pass

