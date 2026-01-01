"""Local (in-process) portfolio service implementation."""

from typing import List

from app.domain.portfolio_hash import generate_portfolio_hash
from app.modules.portfolio.database.portfolio_repository import PortfolioRepository
from app.modules.portfolio.database.position_repository import PositionRepository
from app.modules.portfolio.services.portfolio_service_interface import (
    PortfolioPosition,
    PortfolioSummary,
)


class LocalPortfolioService:
    """
    Local portfolio service implementation.

    Wraps existing domain logic for in-process execution.
    """

    def __init__(self):
        """Initialize local portfolio service."""
        self.portfolio_repo = PortfolioRepository()
        self.position_repo = PositionRepository()

    async def get_positions(self, account_id: str) -> List[PortfolioPosition]:
        """
        Get current portfolio positions.

        Args:
            account_id: Account identifier

        Returns:
            List of positions
        """
        # Get all positions from repository
        positions = self.position_repo.get_all()

        # Convert to PortfolioPosition interface
        result = []
        for pos in positions:
            result.append(
                PortfolioPosition(
                    symbol=pos.symbol,
                    isin=pos.isin or "",
                    quantity=pos.quantity,
                    average_price=pos.avg_price,
                    current_price=pos.current_price or 0.0,
                    market_value=pos.market_value_eur or 0.0,
                    unrealized_pnl=pos.unrealized_pnl or 0.0,
                )
            )

        return result

    async def get_summary(self, account_id: str) -> PortfolioSummary:
        """
        Get portfolio summary.

        Args:
            account_id: Account identifier

        Returns:
            Portfolio summary
        """
        # Get portfolio from repository
        portfolio = self.portfolio_repo.get()

        if not portfolio:
            return PortfolioSummary(
                portfolio_hash="",
                total_value=0.0,
                cash_balance=0.0,
                position_count=0,
                total_pnl=0.0,
            )

        # Get positions
        positions = self.position_repo.get_all()

        # Generate portfolio hash
        portfolio_hash = generate_portfolio_hash(portfolio, positions)

        # Calculate summary metrics
        total_pnl = sum(p.unrealized_pnl for p in positions)

        return PortfolioSummary(
            portfolio_hash=portfolio_hash,
            total_value=portfolio.total_value,
            cash_balance=portfolio.cash_balance,
            position_count=len(positions),
            total_pnl=total_pnl,
        )

    async def get_cash_balance(self, account_id: str) -> float:
        """
        Get cash balance.

        Args:
            account_id: Account identifier

        Returns:
            Cash balance
        """
        portfolio = self.portfolio_repo.get()
        return portfolio.cash_balance if portfolio else 0.0
