"""Planner - Generate trade recommendations based on expected returns.

This is a facade that delegates to specialized components:
- AllocationCalculator: ideal portfolio computation
- PortfolioAnalyzer: current state queries
- RebalanceEngine: trade recommendation generation
"""

from __future__ import annotations

from typing import Optional

from sentinel.broker import Broker
from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.portfolio import Portfolio
from sentinel.settings import Settings

from .allocation import AllocationCalculator
from .analyzer import PortfolioAnalyzer
from .models import TradeRecommendation
from .rebalance import RebalanceEngine


class Planner:
    """Generates trade recommendations based on expected returns.

    This class acts as a facade over specialized planner components,
    maintaining backward compatibility with existing code.
    """

    def __init__(
        self,
        db: Database | None = None,
        broker: Broker | None = None,
        portfolio: Portfolio | None = None,
    ):
        """Initialize planner with optional dependency injection.

        Args:
            db: Database instance (uses singleton if None)
            broker: Broker instance (uses singleton if None)
            portfolio: Portfolio instance (uses singleton if None)
        """
        self._db = db or Database()
        self._broker = broker or Broker()
        self._portfolio = portfolio or Portfolio()
        self._currency = Currency()
        self._settings = Settings()

        # Initialize specialized components
        self._allocation_calculator = AllocationCalculator(
            db=self._db,
            portfolio=self._portfolio,
            currency=self._currency,
            settings=self._settings,
        )
        self._portfolio_analyzer = PortfolioAnalyzer(
            db=self._db,
            portfolio=self._portfolio,
            currency=self._currency,
        )
        self._rebalance_engine = RebalanceEngine(
            db=self._db,
            broker=self._broker,
            portfolio=self._portfolio,
            settings=self._settings,
            currency=self._currency,
        )

    async def calculate_ideal_portfolio(self) -> dict[str, float]:
        """Calculate ideal portfolio allocations.

        Returns:
            dict: symbol -> target allocation percentage (0-1)
        """
        return await self._allocation_calculator.calculate_ideal_portfolio()

    async def get_current_allocations(self) -> dict[str, float]:
        """Get current portfolio allocations by symbol.

        Returns:
            dict: symbol -> allocation percentage (0-1)
        """
        return await self._portfolio_analyzer.get_current_allocations()

    async def get_recommendations(
        self,
        min_trade_value: Optional[float] = None,
        as_of_date: Optional[str] = None,
    ) -> list[TradeRecommendation]:
        """Generate trade recommendations to move toward ideal portfolio.

        Args:
            min_trade_value: Minimum trade value in EUR (uses setting if None)
            as_of_date: Optional date (YYYY-MM-DD). When set (e.g. backtest),
                prices and "today" are scoped to this date.

        Returns:
            List of TradeRecommendation, sorted by priority
        """
        ideal = await self.calculate_ideal_portfolio()
        current = await self.get_current_allocations()
        total_value = await self._portfolio.total_value()

        return await self._rebalance_engine.get_recommendations(
            ideal=ideal,
            current=current,
            total_value=total_value,
            min_trade_value=min_trade_value,
            as_of_date=as_of_date,
        )

    async def get_rebalance_summary(self) -> dict:
        """Get summary of portfolio alignment with ideal allocations.

        Returns:
            dict with alignment metrics and status
        """
        return await self._portfolio_analyzer.get_rebalance_summary()
