"""Portfolio analysis component for current state queries."""

from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone

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

    def _is_simulation_context(self) -> bool:
        """Return True when running against the in-memory backtest database."""
        return self._db.__class__.__name__ == "SimulationDatabase"

    async def get_current_allocations(self, as_of_date: str | None = None) -> dict[str, float]:
        """Get current portfolio allocations by symbol (percentages).

        Returns:
            dict: symbol -> allocation percentage (0-1)
        """
        # Cache only live calculations.
        if as_of_date is None:
            cache_getter = getattr(self._db, "cache_get", None)
            if callable(cache_getter):
                maybe_cached = cache_getter("planner:current_allocations")
                if inspect.isawaitable(maybe_cached):
                    maybe_cached = await maybe_cached
                if isinstance(maybe_cached, (str, bytes, bytearray)):
                    return json.loads(maybe_cached)

        positions = (
            await self.get_positions_as_of(as_of_date) if as_of_date is not None else await self._portfolio.positions()
        )
        total_value = await self.get_total_value(as_of_date=as_of_date)

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

        if as_of_date is None:
            cache_setter = getattr(self._db, "cache_set", None)
            if callable(cache_setter):
                maybe_set = cache_setter(
                    "planner:current_allocations",
                    json.dumps(allocations),
                    ttl_seconds=300,
                )
                if inspect.isawaitable(maybe_set):
                    await maybe_set

        return allocations

    async def get_total_value(self, as_of_date: str | None = None) -> float:
        """Get total portfolio value in EUR, optionally valued at an as-of date."""
        if as_of_date is None:
            return await self._portfolio.total_value()

        snapshot = await self._get_snapshot_as_of(as_of_date)
        if not snapshot and self._is_simulation_context():
            return await self._portfolio.total_value()
        cash_eur = float(snapshot["data"].get("cash_eur", 0.0)) if snapshot else 0.0
        positions = await self.get_positions_as_of(as_of_date)
        positions_eur = 0.0
        for pos in positions:
            positions_eur += await self._currency.to_eur(
                float(pos.get("quantity", 0)) * float(pos.get("current_price", 0)),
                pos.get("currency", "EUR"),
            )
        return positions_eur + cash_eur

    async def get_positions_as_of(self, as_of_date: str) -> list[dict]:
        """Get position list (symbol/quantity/currency/current_price) at a historical date."""
        snapshot = await self._get_snapshot_as_of(as_of_date)
        if not snapshot and self._is_simulation_context():
            return await self._portfolio.positions()
        if not snapshot:
            return []

        positions_blob = snapshot["data"].get("positions", {}) or {}
        if not positions_blob:
            return []

        securities = await self._db.get_all_securities(active_only=False)
        currencies = {s["symbol"]: s.get("currency", "EUR") for s in securities}

        result = []
        for symbol, payload in positions_blob.items():
            quantity = float((payload or {}).get("quantity", 0) or 0)
            if quantity <= 0:
                continue
            hist = await self._db.get_prices(symbol, days=1, end_date=as_of_date)
            if not hist:
                continue
            close = hist[0].get("close")
            if close is None:
                continue
            try:
                price = float(close)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue

            result.append(
                {
                    "symbol": symbol,
                    "quantity": quantity,
                    "currency": currencies.get(symbol, "EUR"),
                    "current_price": price,
                    "avg_cost": 0.0,
                }
            )
        return result

    async def get_cash_eur_as_of(self, as_of_date: str) -> float:
        """Get cash balance in EUR from snapshot at or before a date."""
        snapshot = await self._get_snapshot_as_of(as_of_date)
        if not snapshot and self._is_simulation_context():
            return await self._portfolio.total_cash_eur()
        if not snapshot:
            return 0.0
        return float(snapshot["data"].get("cash_eur", 0.0) or 0.0)

    async def _get_snapshot_as_of(self, as_of_date: str) -> dict | None:
        """Return latest portfolio snapshot at or before the as-of date."""
        as_of_ts = int(datetime.strptime(as_of_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        get_snapshot = getattr(self._db, "get_portfolio_snapshot_as_of", None)
        if get_snapshot is None:
            return None
        maybe_snapshot = get_snapshot(as_of_ts)
        if not inspect.isawaitable(maybe_snapshot):
            return None
        snapshot = await maybe_snapshot
        return snapshot

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
