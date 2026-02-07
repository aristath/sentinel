"""
Simulation Database - In-memory database for backtesting.

IMPORTANT: This NEVER touches the real database after initialization.
All writes go to the in-memory copy only.
"""

import bisect
import json
from contextlib import asynccontextmanager
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
        self._defer_commits: bool = False
        self._txn_depth: int = 0
        self._prices_cache: dict[str, list[dict]] = {}
        self._price_dates_cache: dict[str, list[str]] = {}

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
        for table in ["settings", "securities", "prices", "allocation_targets"]:
            await self._copy_table(source_db, table)

        await self._connection.commit()
        await self._build_prices_cache()

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
        self._prices_cache.clear()
        self._price_dates_cache.clear()

    async def _build_prices_cache(self):
        """Build in-memory per-symbol price cache for fast as-of lookups."""
        cursor = await self.conn.execute("SELECT * FROM prices ORDER BY symbol ASC, date ASC")
        rows = await cursor.fetchall()
        cache: dict[str, list[dict]] = {}
        for row in rows:
            symbol = row["symbol"]
            cache.setdefault(symbol, []).append(dict(row))
        self._prices_cache = cache
        self._price_dates_cache = {symbol: [str(item["date"]) for item in items] for symbol, items in cache.items()}

    def _get_cached_prices(
        self,
        symbol: str,
        *,
        days: int | None,
        effective_end: str | None,
    ) -> list[dict]:
        """Return cached rows for symbol in newest-first order."""
        series = self._prices_cache.get(symbol, [])
        if not series:
            return []
        if effective_end:
            dates = self._price_dates_cache.get(symbol, [])
            idx = bisect.bisect_right(dates, effective_end)
            selected = series[:idx]
        else:
            selected = series
        if days and days > 0:
            selected = selected[-days:]
        # Return defensive copies in newest-first order.
        return [dict(row) for row in reversed(selected)]

    @asynccontextmanager
    async def deferred_writes(self):
        """Batch multiple writes into one transaction for backtest speed."""
        if self._connection is None:
            yield
            return

        self._txn_depth += 1
        is_outer = self._txn_depth == 1
        if is_outer:
            await self._connection.execute("BEGIN")
            self._defer_commits = True
        try:
            yield
            if is_outer:
                await self._connection.commit()
        except Exception:
            if is_outer:
                await self._connection.rollback()
            raise
        finally:
            self._txn_depth = max(0, self._txn_depth - 1)
            if is_outer:
                self._defer_commits = False

    async def _maybe_commit(self):
        if not self._defer_commits and self._connection:
            await self._connection.commit()

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
        if self._prices_cache:
            return self._get_cached_prices(symbol, days=days, effective_end=effective_end)

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

    async def get_prices_for_symbols(
        self,
        symbols: list[str],
        days: int | None = None,
        end_date: str | None = None,
    ) -> dict[str, list[dict]]:
        """Get prices for multiple symbols with simulation date filtering."""
        effective_end = end_date or self._simulation_date
        if self._prices_cache:
            return {
                symbol: self._get_cached_prices(symbol, days=days, effective_end=effective_end) for symbol in symbols
            }
        return await super().get_prices_for_symbols(symbols=symbols, days=days, end_date=effective_end)

    # -------------------------------------------------------------------------
    # Simulation-specific: set_cash_balance without datetime
    # -------------------------------------------------------------------------

    async def set_cash_balance(self, currency: str, amount: float) -> None:
        """Set cash balance for a currency (simulation version without timestamp)."""
        await self.conn.execute(
            "INSERT OR REPLACE INTO cash_balances (currency, amount) VALUES (?, ?)", (currency, amount)
        )
        await self._maybe_commit()

    async def set_cash_balances(self, balances: dict[str, float]) -> None:
        """Set multiple cash balances at once (simulation version)."""
        await self.conn.execute("DELETE FROM cash_balances")
        for currency, amount in balances.items():
            if amount > 0:
                await self.conn.execute(
                    "INSERT INTO cash_balances (currency, amount) VALUES (?, ?)", (currency, amount)
                )
        await self._maybe_commit()

    async def upsert_position(self, symbol: str, **data) -> None:
        """Insert or update a position (deferred-commit aware)."""
        existing = await self.get_position(symbol)
        if existing:
            sets = ", ".join(f"{k} = ?" for k in data.keys())
            await self.conn.execute(
                f"UPDATE positions SET {sets} WHERE symbol = ?",  # noqa: S608
                (*data.values(), symbol),
            )
        else:
            data["symbol"] = symbol
            cols = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))
            await self.conn.execute(
                f"INSERT INTO positions ({cols}) VALUES ({placeholders})",  # noqa: S608
                tuple(data.values()),
            )
        await self._maybe_commit()

    async def upsert_trade(
        self,
        broker_trade_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        executed_at: int,
        raw_data: dict,
        commission: float = 0,
        commission_currency: str = "EUR",
    ) -> int:
        """Insert a trade or ignore if broker_trade_id exists (deferred-commit aware)."""
        cursor = await self.conn.execute(
            """INSERT OR IGNORE INTO trades
               (broker_trade_id, symbol, side, quantity, price, commission, commission_currency, executed_at, raw_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                broker_trade_id,
                symbol,
                side,
                quantity,
                price,
                commission,
                commission_currency,
                executed_at,
                json.dumps(raw_data),
            ),
        )
        await self._maybe_commit()
        return cursor.lastrowid or 0
