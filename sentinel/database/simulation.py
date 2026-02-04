"""
Simulation Database - In-memory database for backtesting.

IMPORTANT: This NEVER touches the real database after initialization.
All writes go to the in-memory copy only.
"""

from typing import Optional

import aiosqlite

from sentinel.database.base import BaseDatabase


class SimulationDatabase(BaseDatabase):
    """
    In-memory database for backtesting that extends BaseDatabase.

    Adds simulation-specific functionality like date filtering for prices.
    """

    def __init__(self):
        self._connection: Optional[aiosqlite.Connection] = None
        self._path = ":memory:"
        self._simulation_date: str = ""  # Current simulation date for filtering

    def set_simulation_date(self, date_str: str):
        """Set the current simulation date for date-aware queries."""
        self._simulation_date = date_str

    async def initialize_from(self, source_db):
        """Create in-memory copy from real database (READ-ONLY from source)."""
        self._connection = await aiosqlite.connect(":memory:")
        self._connection.row_factory = aiosqlite.Row

        # Copy schema
        cursor = await source_db.conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
        for row in await cursor.fetchall():
            if row["sql"]:
                try:
                    await self._connection.execute(row["sql"])
                except aiosqlite.OperationalError:
                    pass

        # Copy read-only reference data only
        for table in ["settings", "securities", "prices", "scores", "allocation_targets"]:
            await self._copy_table(source_db, table)

        await self._connection.commit()

    async def _copy_table(self, source_db, table: str):
        """Copy table data from source (READ-ONLY operation on source)."""
        try:
            cursor = await source_db.conn.execute(f"SELECT * FROM {table}")  # noqa: S608
            rows = await cursor.fetchall()
            if not rows:
                return
            columns = [desc[0] for desc in cursor.description]
            placeholders = ",".join(["?" for _ in columns])
            cols_str = ",".join(columns)
            if self._connection is None:
                return
            for row in rows:
                await self._connection.execute(
                    f"INSERT OR REPLACE INTO {table} ({cols_str}) VALUES ({placeholders})",  # noqa: S608
                    tuple(row),
                )
        except Exception:  # noqa: S110
            pass

    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    # -------------------------------------------------------------------------
    # Override: Prices with simulation date filtering
    # -------------------------------------------------------------------------

    async def get_prices(
        self,
        symbol: str,
        days: int | None = None,
        end_date: str | None = None,
    ) -> list[dict]:
        """
        Get prices for a symbol, filtered by simulation date if set.

        This ensures that during backtesting, we only use price data
        up to the current simulation date (no "future" data).
        """
        effective_end = end_date or self._simulation_date
        if effective_end:
            query = "SELECT * FROM prices WHERE symbol = ? AND date <= ? ORDER BY date DESC"
            params: list[str | int] = [symbol, effective_end]
        else:
            query = "SELECT * FROM prices WHERE symbol = ? ORDER BY date DESC"
            params = [symbol]

        if days:
            query += " LIMIT ?"
            params.append(days)

        cursor = await self.conn.execute(query, params)
        return [dict(row) for row in await cursor.fetchall()]

    # -------------------------------------------------------------------------
    # Simulation-specific: set_cash_balance without datetime
    # -------------------------------------------------------------------------

    async def set_cash_balance(self, currency: str, amount: float) -> None:
        """Set cash balance for a currency (simulation version without timestamp)."""
        await self.conn.execute(
            "INSERT OR REPLACE INTO cash_balances (currency, amount) VALUES (?, ?)", (currency, amount)
        )
        await self.conn.commit()

    async def set_cash_balances(self, balances: dict[str, float]) -> None:
        """Set multiple cash balances at once (simulation version)."""
        await self.conn.execute("DELETE FROM cash_balances")
        for currency, amount in balances.items():
            if amount > 0:
                await self.conn.execute(
                    "INSERT INTO cash_balances (currency, amount) VALUES (?, ?)", (currency, amount)
                )
        await self.conn.commit()
