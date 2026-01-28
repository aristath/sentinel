"""
Base Database - Shared database operations.

Contains methods that are identical between Database and SimulationDatabase.
"""

from typing import Optional

import aiosqlite


class BaseDatabase:
    """Base class with shared database operations."""

    _connection: Optional[aiosqlite.Connection] = None

    @property
    def conn(self) -> aiosqlite.Connection:
        """Get database connection."""
        if not self._connection:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection

    # -------------------------------------------------------------------------
    # Securities
    # -------------------------------------------------------------------------

    async def get_security(self, symbol: str) -> Optional[dict]:
        """Get a security by symbol."""
        cursor = await self.conn.execute("SELECT * FROM securities WHERE symbol = ?", (symbol,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_all_securities(self, active_only: bool = True) -> list[dict]:
        """Get all securities."""
        query = "SELECT * FROM securities"
        if active_only:
            query += " WHERE active = 1"
        cursor = await self.conn.execute(query)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def upsert_security(self, symbol: str, **data) -> None:
        """Insert or update a security."""
        existing = await self.get_security(symbol)
        if existing:
            sets = ", ".join(f"{k} = ?" for k in data.keys())
            await self.conn.execute(
                f"UPDATE securities SET {sets} WHERE symbol = ?",  # noqa: S608
                (*data.values(), symbol),
            )
        else:
            data["symbol"] = symbol
            cols = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))
            await self.conn.execute(
                f"INSERT INTO securities ({cols}) VALUES ({placeholders})",  # noqa: S608
                tuple(data.values()),
            )
        await self.conn.commit()

    # -------------------------------------------------------------------------
    # Positions
    # -------------------------------------------------------------------------

    async def get_position(self, symbol: str) -> Optional[dict]:
        """Get a position by symbol."""
        cursor = await self.conn.execute("SELECT * FROM positions WHERE symbol = ?", (symbol,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_all_positions(self) -> list[dict]:
        """Get all positions."""
        cursor = await self.conn.execute("SELECT * FROM positions WHERE quantity > 0")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def upsert_position(self, symbol: str, **data) -> None:
        """Insert or update a position."""
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
        await self.conn.commit()

    # -------------------------------------------------------------------------
    # Cash Balances
    # -------------------------------------------------------------------------

    async def get_cash_balances(self) -> dict[str, float]:
        """Get all cash balances as a dictionary of currency -> amount."""
        cursor = await self.conn.execute("SELECT currency, amount FROM cash_balances")
        rows = await cursor.fetchall()
        return {row["currency"]: row["amount"] for row in rows}

    async def set_cash_balance(self, currency: str, amount: float) -> None:
        """Set cash balance for a currency."""
        await self.conn.execute(
            """INSERT OR REPLACE INTO cash_balances (currency, amount, updated_at)
               VALUES (?, ?, datetime('now'))""",
            (currency, amount),
        )
        await self.conn.commit()

    async def set_cash_balances(self, balances: dict[str, float]) -> None:
        """Set multiple cash balances at once. Clears existing balances."""
        await self.conn.execute("DELETE FROM cash_balances")
        for currency, amount in balances.items():
            if amount > 0:  # Only store non-zero balances
                await self.conn.execute(
                    """INSERT INTO cash_balances (currency, amount, updated_at)
                       VALUES (?, ?, datetime('now'))""",
                    (currency, amount),
                )
        await self.conn.commit()

    # -------------------------------------------------------------------------
    # Allocation Targets
    # -------------------------------------------------------------------------

    async def get_allocation_targets(self, target_type: str = None) -> list[dict]:
        """Get allocation targets (geography or industry weights)."""
        query = "SELECT * FROM allocation_targets"
        params = []
        if target_type:
            query += " WHERE type = ?"
            params.append(target_type)
        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # -------------------------------------------------------------------------
    # Trades
    # -------------------------------------------------------------------------

    async def get_trades(self, symbol: str = None, limit: int = 100) -> list[dict]:
        """Get trade history."""
        query = "SELECT * FROM trades"
        params = []
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol)
        query += " ORDER BY executed_at DESC LIMIT ?"
        params.append(limit)
        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # -------------------------------------------------------------------------
    # Prices (base implementation, can be overridden)
    # -------------------------------------------------------------------------

    async def get_prices(self, symbol: str, days: int = None) -> list[dict]:
        """Get historical prices for a security."""
        query = "SELECT * FROM prices WHERE symbol = ? ORDER BY date DESC"
        params = [symbol]
        if days:
            query += " LIMIT ?"
            params.append(days)
        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
