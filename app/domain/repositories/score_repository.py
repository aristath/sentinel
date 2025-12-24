"""Repository interface for stock score data access."""

from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class StockScore:
    """Stock score domain model for long-term value investing."""
    symbol: str
    # New primary scores
    quality_score: Optional[float] = None
    opportunity_score: Optional[float] = None
    analyst_score: Optional[float] = None
    allocation_fit_score: Optional[float] = None
    # Quality breakdown
    cagr_score: Optional[float] = None
    consistency_score: Optional[float] = None
    history_years: Optional[float] = None
    # Legacy fields (for backwards compatibility)
    technical_score: Optional[float] = None
    fundamental_score: Optional[float] = None
    # Common fields
    total_score: Optional[float] = None
    volatility: Optional[float] = None
    calculated_at: Optional[datetime] = None


class ScoreRepository(ABC):
    """Abstract repository for score operations."""

    @abstractmethod
    async def get_by_symbol(self, symbol: str) -> Optional[StockScore]:
        """Get score by symbol."""
        pass

    @abstractmethod
    async def upsert(self, score: StockScore, auto_commit: bool = True) -> None:
        """
        Insert or update a score.
        
        Args:
            score: Stock score to upsert
            auto_commit: If True, commit immediately. If False, caller manages transaction.
        """
        pass

    @abstractmethod
    async def get_all(self) -> List[StockScore]:
        """Get all scores."""
        pass

