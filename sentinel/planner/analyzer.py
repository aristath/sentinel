"""Portfolio analysis component for current state queries."""

from __future__ import annotations

import json

from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.portfolio import Portfolio


class PortfolioAnalyzer:
    """Analyzes current portfolio state and allocations."""

    def __init__(
        self,
        db: Database | None = None,
        portfolio: Portfolio | None = None,
        currency: Currency | None = None,
    ):
        """Initialize analyzer with optional dependencies.

        Args:
            db: Database instance (uses singleton if None)
            portfolio: Portfolio instance (uses singleton if None)
            currency: Currency instance (uses singleton if None)
        """
        self._db = db or Database()
        self._portfolio = portfolio or Portfolio()
        self._currency = currency or Currency()

    async def get_current_allocations(self) -> dict[str, float]:
        """Get current portfolio allocations by symbol (percentages).

        Returns:
            dict: symbol -> allocation percentage (0-1)
        """
        # Check cache first (5 minute TTL)
        cached = await self._db.cache_get("planner:current_allocations")
        if cached is not None:
            return json.loads(cached)

        positions = await self._portfolio.positions()
        total_value = await self._portfolio.total_value()

        if total_value <= 0:
            return {}

        allocations = {}
        for pos in positions:
            symbol = pos["symbol"]
            quantity = pos.get("quantity", 0)
            price = pos.get("current_price", 0)
            pos_currency = pos.get("currency", "EUR")

            if quantity <= 0 or price <= 0:
                continue

            # Convert to EUR
            value_local = quantity * price
            rate = await self._currency.get_rate(pos_currency)
            value_eur = value_local * rate

            allocations[symbol] = value_eur / total_value

        # Cache for 5 minutes
        await self._db.cache_set(
            "planner:current_allocations",
            json.dumps(allocations),
            ttl_seconds=300,
        )

        return allocations

    async def get_rebalance_summary(self) -> dict:
        """Get summary of portfolio alignment with ideal allocations.

        Returns:
            dict with alignment metrics and status
        """
        from sentinel.planner.allocation import AllocationCalculator

        current = await self.get_current_allocations()

        calculator = AllocationCalculator(
            db=self._db,
            portfolio=self._portfolio,
            currency=self._currency,
        )
        ideal = await calculator.calculate_ideal_portfolio()

        if not current or not ideal:
            return {
                "total_securities": 0,
                "aligned_count": 0,
                "needs_adjustment_count": 0,
                "total_deviation": 0.0,
                "max_deviation": 0.0,
                "average_deviation": 0.0,
                "status": "aligned",
            }

        # Calculate deviations
        all_symbols = set(current.keys()) | set(ideal.keys())
        deviations = []

        for symbol in all_symbols:
            current_pct = current.get(symbol, 0)
            ideal_pct = ideal.get(symbol, 0)
            deviation = abs(current_pct - ideal_pct)
            deviations.append(deviation)

        if not deviations:
            return {
                "total_securities": 0,
                "aligned_count": 0,
                "needs_adjustment_count": 0,
                "total_deviation": 0.0,
                "max_deviation": 0.0,
                "average_deviation": 0.0,
                "status": "aligned",
            }

        total_deviation = sum(deviations)
        max_deviation = max(deviations) if deviations else 0
        avg_deviation = total_deviation / len(deviations)

        # Determine status
        threshold = 0.05  # 5%
        aligned_count = sum(1 for d in deviations if d < threshold)
        needs_adjustment = len(deviations) - aligned_count

        if max_deviation < threshold:
            status = "aligned"
        elif max_deviation < threshold * 2:
            status = "minor_drift"
        else:
            status = "needs_rebalance"

        return {
            "total_securities": len(all_symbols),
            "aligned_count": aligned_count,
            "needs_adjustment_count": needs_adjustment,
            "total_deviation": total_deviation,
            "max_deviation": max_deviation,
            "average_deviation": avg_deviation,
            "status": status,
        }

    async def get_position_details(self) -> list[dict]:
        """Get detailed position information with EUR values.

        Returns:
            List of position dicts with value_eur, value_local, etc.
        """
        positions = await self._portfolio.positions()
        result = []

        for pos in positions:
            symbol = pos["symbol"]
            quantity = pos.get("quantity", 0)
            price = pos.get("current_price", 0)
            avg_cost = pos.get("avg_cost", 0)
            pos_currency = pos.get("currency", "EUR")

            if quantity <= 0 or price <= 0:
                continue

            # Calculate values
            value_local = quantity * price
            rate = await self._currency.get_rate(pos_currency)
            value_eur = value_local * rate

            # Calculate profit
            if avg_cost > 0:
                profit_pct = ((price - avg_cost) / avg_cost) * 100
            else:
                profit_pct = 0.0

            result.append(
                {
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": price,
                    "currency": pos_currency,
                    "value_local": value_local,
                    "value_eur": value_eur,
                    "avg_cost": avg_cost,
                    "profit_pct": profit_pct,
                    "name": pos.get("name", symbol),
                }
            )

        return result
