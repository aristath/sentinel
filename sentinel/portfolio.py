"""
Portfolio - Single source of truth for portfolio-level operations.

Usage:
    portfolio = Portfolio()
    await portfolio.sync()  # Sync with broker
    value = await portfolio.total_value()
    positions = await portfolio.positions()
"""

from typing import Optional

from sentinel.broker import Broker
from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.security import Security
from sentinel.settings import Settings
from sentinel.universe import BROKER_POSITION_UNIVERSE_SOURCE, import_security_from_broker
from sentinel.utils.positions import PositionCalculator


class Portfolio:
    """Represents the entire portfolio with all operations."""

    def __init__(self, db=None, broker=None, settings=None, currency=None):
        """
        Initialize portfolio with optional dependency injection.

        Args:
            db: Database instance (uses singleton if None)
            broker: Broker instance (uses singleton if None)
            settings: Settings instance (uses singleton if None)
            currency: Currency instance (uses singleton if None)
        """
        self._db = db or Database()
        self._broker = broker or Broker()
        self._settings = settings or Settings()
        self._currency = currency or Currency()
        self._cash: dict[str, float] = {}

    async def sync(self) -> "Portfolio":
        """Sync portfolio state from broker to database."""
        data = await self._broker.get_portfolio()

        # Update positions and securities
        for pos in data.get("positions", []):
            symbol = pos["symbol"]

            # Ensure security exists in database
            existing = await self._db.get_security(symbol)
            if not existing or int(existing.get("active", 0) or 0) == 0:
                await import_security_from_broker(
                    self._db,
                    self._broker,
                    symbol,
                    fallback_info=pos,
                    universe_source=BROKER_POSITION_UNIVERSE_SOURCE,
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

        # Zero out positions that no longer exist in the broker account
        broker_symbols = {pos["symbol"] for pos in data.get("positions", [])}
        db_positions = await self._db.get_all_positions()
        for pos in db_positions:
            if pos["symbol"] not in broker_symbols:
                await self._db.upsert_position(pos["symbol"], quantity=0, updated_at="now")

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

        # Sum cash in all currencies, converted to EUR
        total = await self.total_cash_eur()

        # Sum position values, converted to EUR
        pos_calc = PositionCalculator(currency_converter=self._currency)
        for pos in positions:
            value_eur = await pos_calc.calculate_value_eur(
                pos.get("quantity", 0), pos.get("current_price", 0), pos.get("currency", "EUR")
            )
            total += value_eur

        return total

    async def cash(self, currency: str = "EUR") -> float:
        """Get available cash in specified currency."""
        cash_balances = await self.get_cash_balances()
        return cash_balances.get(currency, 0)

    async def _get_simulated_cash(self) -> float | None:
        """Return simulated cash if in research mode and setting is set, else None."""
        mode = await self._settings.get("trading_mode")
        if mode != "research":
            return None
        value = await self._settings.get("simulated_cash_eur")
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    async def get_cash_balances(self) -> dict[str, float]:
        """Get all cash balances per currency."""
        simulated = await self._get_simulated_cash()
        if simulated is not None:
            return {"EUR": simulated}
        # Use memory cache if available, otherwise load from DB
        if self._cash:
            return self._cash
        return await self._db.get_cash_balances()

    async def total_cash_eur(self) -> float:
        """Get total cash value converted to EUR."""
        simulated = await self._get_simulated_cash()
        if simulated is not None:
            return simulated
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
