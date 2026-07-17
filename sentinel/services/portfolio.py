"""Portfolio service for portfolio-related business operations."""

from __future__ import annotations

from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.portfolio import Portfolio
from sentinel.services.valuation import PortfolioValuationService


class PortfolioService:
    """Service for portfolio business operations.

    This service handles complex portfolio operations that span multiple
    domain objects or require data transformation beyond simple CRUD.
    """

    def __init__(
        self,
        db: Database | None = None,
        portfolio: Portfolio | None = None,
        currency: Currency | None = None,
    ):
        """Initialize service with optional dependencies.

        Args:
            db: Database instance (uses singleton if None)
            portfolio: Portfolio instance (uses singleton if None)
            currency: Currency instance (uses singleton if None)
        """
        self._db = db or Database()
        self._portfolio = portfolio or Portfolio()
        self._currency = currency or Currency()

    async def get_portfolio_state(self) -> dict:
        """Get complete portfolio state with enriched position data.

        Returns:
            dict with positions, values, and cash
        """
        valuation = await PortfolioValuationService(
            db=self._db,
            currency=self._currency,
        ).current()

        return {
            "positions": valuation["positions"],
            "total_value": valuation["total_value_eur"],
            "total_value_eur": valuation["total_value_eur"],
            "portfolio_return_pct": valuation["portfolio_return_pct"],
            "cash": valuation["cash"],
            "total_cash_eur": valuation["total_cash_eur"],
        }

    async def sync_portfolio(self) -> dict:
        """Sync portfolio from broker.

        Returns:
            dict with status
        """
        await self._portfolio.sync()
        return {"status": "ok"}
