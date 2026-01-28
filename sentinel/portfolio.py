"""
Portfolio - Single source of truth for portfolio-level operations.

Usage:
    portfolio = Portfolio()
    await portfolio.sync()  # Sync with broker
    value = await portfolio.total_value()
    positions = await portfolio.positions()
    allocations = await portfolio.get_allocations()
"""

from typing import Optional

from sentinel.broker import Broker
from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.security import Security
from sentinel.settings import Settings


class Portfolio:
    """Represents the entire portfolio with all operations."""

    def __init__(self, db=None, broker=None):
        """
        Initialize portfolio with optional dependency injection.

        Args:
            db: Database instance (uses singleton if None)
            broker: Broker instance (uses singleton if None)
        """
        self._db = db or Database()
        self._broker = broker or Broker()
        self._settings = Settings()
        self._currency = Currency()
        self._cash: dict[str, float] = {}

    async def sync(self) -> "Portfolio":
        """Sync portfolio state from broker to database."""
        data = await self._broker.get_portfolio()

        # Update positions and securities
        for pos in data.get("positions", []):
            symbol = pos["symbol"]

            # Ensure security exists in database
            existing = await self._db.get_security(symbol)
            if not existing:
                await self._db.upsert_security(
                    symbol, name=pos.get("name", symbol), currency=pos.get("currency", "EUR"), active=1
                )

            # Update position
            await self._db.upsert_position(
                symbol,
                quantity=pos["quantity"],
                avg_cost=pos.get("avg_cost"),
                current_price=pos.get("current_price"),
                currency=pos.get("currency", "EUR"),
                updated_at="now",
            )

        # Store cash balances in memory and database
        self._cash = data.get("cash", {})
        await self._db.set_cash_balances(self._cash)
        return self

    # -------------------------------------------------------------------------
    # Value Calculations
    # -------------------------------------------------------------------------

    async def total_value(self, currency: str = "EUR") -> float:
        """Get total portfolio value in specified currency (default EUR)."""
        positions = await self._db.get_all_positions()

        # Get cash balances (from memory or DB)
        cash_balances = await self.get_cash_balances()

        # Sum cash in all currencies, converted to EUR
        total = 0.0
        for curr, amount in cash_balances.items():
            total += await self._currency.to_eur(amount, curr)

        # Sum position values, converted to EUR
        for pos in positions:
            price = pos.get("current_price", 0)
            qty = pos.get("quantity", 0)
            pos_currency = pos.get("currency", "EUR")
            value_in_local = price * qty
            value_in_eur = await self._currency.to_eur(value_in_local, pos_currency)
            total += value_in_eur

        return total

    async def cash(self, currency: str = "EUR") -> float:
        """Get available cash in specified currency."""
        cash_balances = await self.get_cash_balances()
        return cash_balances.get(currency, 0)

    async def get_cash_balances(self) -> dict[str, float]:
        """Get all cash balances per currency."""
        # Use memory cache if available, otherwise load from DB
        if self._cash:
            return self._cash
        return await self._db.get_cash_balances()

    async def total_cash_eur(self) -> float:
        """Get total cash value converted to EUR."""
        cash_balances = await self.get_cash_balances()
        total = 0.0
        for curr, amount in cash_balances.items():
            total += await self._currency.to_eur(amount, curr)
        return total

    # -------------------------------------------------------------------------
    # Positions
    # -------------------------------------------------------------------------

    async def positions(self) -> list[dict]:
        """Get all current positions."""
        return await self._db.get_all_positions()

    async def position(self, symbol: str) -> Optional[dict]:
        """Get a specific position."""
        return await self._db.get_position(symbol)

    async def securities(self, active_only: bool = True) -> list[Security]:
        """Get all securities as Security objects."""
        rows = await self._db.get_all_securities(active_only)
        result = []
        for row in rows:
            sec = Security(row["symbol"])
            await sec.load()
            result.append(sec)
        return result

    # -------------------------------------------------------------------------
    # Allocations
    # -------------------------------------------------------------------------

    async def get_allocations(self) -> dict:
        """
        Get current allocation percentages (all values converted to EUR).
        Returns: {'by_security': {...}, 'by_geography': {...}, 'by_industry': {...}}
        """
        positions = await self._db.get_all_positions()
        total = await self.total_value()

        if total == 0:
            return {"by_security": {}, "by_geography": {}, "by_industry": {}}

        by_security = {}
        by_geography = {}
        by_industry = {}

        for pos in positions:
            symbol = pos["symbol"]
            price = pos.get("current_price", 0)
            qty = pos.get("quantity", 0)
            pos_currency = pos.get("currency", "EUR")

            # Convert to EUR
            value_local = price * qty
            value_eur = await self._currency.to_eur(value_local, pos_currency)
            pct = value_eur / total

            by_security[symbol] = pct

            # Get security metadata
            sec_data = await self._db.get_security(symbol)
            if sec_data:
                # Handle comma-separated geographies (split equally)
                geo_str = sec_data.get("geography", "") or ""
                geos = [g.strip() for g in geo_str.split(",") if g.strip()]
                if not geos:
                    geos = ["Unknown"]
                geo_weight = pct / len(geos)
                for geo in geos:
                    by_geography[geo] = by_geography.get(geo, 0) + geo_weight

                # Handle comma-separated industries (split equally)
                ind_str = sec_data.get("industry", "") or ""
                inds = [i.strip() for i in ind_str.split(",") if i.strip()]
                if not inds:
                    inds = ["Unknown"]
                ind_weight = pct / len(inds)
                for ind in inds:
                    by_industry[ind] = by_industry.get(ind, 0) + ind_weight

        return {
            "by_security": by_security,
            "by_geography": by_geography,
            "by_industry": by_industry,
        }

    async def get_target_allocations(self) -> dict:
        """
        Get target allocation percentages (from weights).
        Returns: {'geography': {...}, 'industry': {...}}
        """
        targets = await self._db.get_allocation_targets()

        # Group by type
        geo_weights = {}
        ind_weights = {}
        for t in targets:
            if t["type"] == "geography":
                geo_weights[t["name"]] = t["weight"]
            elif t["type"] == "industry":
                ind_weights[t["name"]] = t["weight"]

        # Normalize to percentages
        def normalize(weights: dict) -> dict:
            total = sum(weights.values())
            if total == 0:
                return {}
            return {k: v / total for k, v in weights.items()}

        return {
            "geography": normalize(geo_weights),
            "industry": normalize(ind_weights),
        }

    # -------------------------------------------------------------------------
    # Analysis
    # -------------------------------------------------------------------------

    async def deviation_from_targets(self) -> dict:
        """
        Calculate how much current allocation deviates from targets.
        Positive = overweight, Negative = underweight.
        """
        current = await self.get_allocations()
        targets = await self.get_target_allocations()

        geo_dev = {}
        for name, target_pct in targets["geography"].items():
            current_pct = current["by_geography"].get(name, 0)
            geo_dev[name] = current_pct - target_pct

        ind_dev = {}
        for name, target_pct in targets["industry"].items():
            current_pct = current["by_industry"].get(name, 0)
            ind_dev[name] = current_pct - target_pct

        return {
            "geography": geo_dev,
            "industry": ind_dev,
        }

    async def needs_rebalance(self) -> bool:
        """Check if portfolio needs rebalancing based on threshold."""
        threshold = await self._settings.get("rebalance_threshold", 0.05)
        deviations = await self.deviation_from_targets()

        for dev in deviations["geography"].values():
            if abs(dev) > threshold:
                return True

        for dev in deviations["industry"].values():
            if abs(dev) > threshold:
                return True

        return False
