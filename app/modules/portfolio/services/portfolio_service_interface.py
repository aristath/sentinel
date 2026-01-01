"""Portfolio service interface."""

from dataclasses import dataclass
from typing import List, Protocol


@dataclass
class PortfolioPosition:
    """Portfolio position data class."""

    symbol: str
    isin: str
    quantity: float
    average_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float


@dataclass
class PortfolioSummary:
    """Portfolio summary data class."""

    portfolio_hash: str
    total_value: float
    cash_balance: float
    position_count: int
    total_pnl: float


class PortfolioServiceInterface(Protocol):
    """Portfolio service interface."""

    async def get_positions(self, account_id: str) -> List[PortfolioPosition]:
        """
        Get current portfolio positions.

        Args:
            account_id: Account identifier

        Returns:
            List of positions
        """
        ...

    async def get_summary(self, account_id: str) -> PortfolioSummary:
        """
        Get portfolio summary.

        Args:
            account_id: Account identifier

        Returns:
            Portfolio summary
        """
        ...

    async def get_cash_balance(self, account_id: str) -> float:
        """
        Get cash balance.

        Args:
            account_id: Account identifier

        Returns:
            Cash balance
        """
        ...
