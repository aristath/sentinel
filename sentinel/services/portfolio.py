"""Portfolio service for portfolio-related business operations."""

from __future__ import annotations

from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.portfolio import Portfolio
from sentinel.utils.positions import PositionCalculator


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
            dict with positions, values, cash, and allocations
        """
        positions = await self._portfolio.positions()
        total = await self._portfolio.total_value()
        allocations = await self._portfolio.get_allocations()

        # Enrich positions with calculated values
        pos_calc = PositionCalculator(currency_converter=self._currency)

        # Batch-fetch all securities for name lookups
        all_securities = await self._db.get_all_securities(active_only=False)
        securities_map = {s["symbol"]: s for s in all_securities}

        for pos in positions:
            symbol = pos["symbol"]
            price = pos.get("current_price", 0)
            qty = pos.get("quantity", 0)
            avg_cost = pos.get("avg_cost", 0)
            pos_currency = pos.get("currency", "EUR")

            pos["value_local"] = await pos_calc.calculate_value_local(qty, price)
            pos["value_eur"] = await pos_calc.calculate_value_eur(qty, price, pos_currency)

            profit_pct, _ = pos_calc.calculate_profit(qty, price, avg_cost)
            pos["profit_pct"] = profit_pct

            # Get security name
            sec = securities_map.get(symbol)
            if sec:
                pos["name"] = sec.get("name", symbol)

        # Get cash balances
        cash = await self._portfolio.get_cash_balances()
        total_cash_eur = await self._portfolio.total_cash_eur()
        total_eur = total + total_cash_eur

        return {
            "positions": positions,
            "total_value": total,
            "total_value_eur": total_eur,
            "cash": cash,
            "total_cash_eur": total_cash_eur,
            "allocations": allocations,
        }

    async def get_allocation_comparison(self) -> dict:
        """Get current vs target allocations with deviations.

        Returns:
            dict with current, targets, and deviations
        """
        current = await self._portfolio.get_allocations()
        targets = await self._portfolio.get_target_allocations()
        deviations = await self._portfolio.deviation_from_targets()

        return {
            "current": current,
            "targets": targets,
            "deviations": deviations,
        }

    async def sync_portfolio(self) -> dict:
        """Sync portfolio from broker.

        Returns:
            dict with status
        """
        await self._portfolio.sync()
        return {"status": "ok"}
