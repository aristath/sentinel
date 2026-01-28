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
            await self.conn.execute(
                """INSERT INTO cash_balances (currency, amount, updated_at)
                   VALUES (?, ?, datetime('now'))""",
                (currency, amount),
            )
        await self.conn.commit()

    # -------------------------------------------------------------------------
    # Allocation Targets
    # -------------------------------------------------------------------------

    async def get_allocation_targets(self, target_type: str | None = None) -> list[dict]:
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

    async def upsert_trade(
        self,
        broker_trade_id: str,
        symbol: str,
        side: str,
        executed_at: str,
        raw_data: dict,
    ) -> int:
        """
        Insert a trade or ignore if broker_trade_id already exists.

        Args:
            broker_trade_id: Unique trade ID from the broker
            symbol: Security symbol
            side: 'BUY' or 'SELL'
            executed_at: ISO format datetime string
            raw_data: Full trade data from broker API

        Returns:
            Row ID of the inserted trade, or 0 if ignored
        """
        import json

        cursor = await self.conn.execute(
            """INSERT OR IGNORE INTO trades (broker_trade_id, symbol, side, executed_at, raw_data)
               VALUES (?, ?, ?, ?, ?)""",
            (broker_trade_id, symbol, side, executed_at, json.dumps(raw_data)),
        )
        await self.conn.commit()
        return cursor.lastrowid or 0

    async def get_trades(
        self,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """
        Get trade history with optional filters.

        Args:
            symbol: Filter by security symbol
            side: Filter by 'BUY' or 'SELL'
            start_date: Filter trades on or after this date (YYYY-MM-DD)
            end_date: Filter trades on or before this date (YYYY-MM-DD)
            limit: Maximum number of trades to return
            offset: Number of trades to skip (for pagination)

        Returns:
            List of trade dicts with parsed raw_data
        """
        import json

        query = "SELECT * FROM trades WHERE 1=1"
        params = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        if side:
            query += " AND side = ?"
            params.append(side)

        if start_date:
            query += " AND executed_at >= ?"
            params.append(start_date)

        if end_date:
            query += " AND executed_at <= ?"
            params.append(end_date + "T23:59:59")  # Include full end date

        query += " ORDER BY executed_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()

        # Parse raw_data JSON for each trade
        result = []
        for row in rows:
            trade = dict(row)
            if trade.get("raw_data"):
                try:
                    trade["raw_data"] = json.loads(trade["raw_data"])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(trade)

        return result

    async def get_trades_count(
        self,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> int:
        """
        Get total count of trades matching filters (for pagination).

        Args:
            symbol: Filter by security symbol
            side: Filter by 'BUY' or 'SELL'
            start_date: Filter trades on or after this date (YYYY-MM-DD)
            end_date: Filter trades on or before this date (YYYY-MM-DD)

        Returns:
            Total count of matching trades
        """
        query = "SELECT COUNT(*) FROM trades WHERE 1=1"
        params = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        if side:
            query += " AND side = ?"
            params.append(side)

        if start_date:
            query += " AND executed_at >= ?"
            params.append(start_date)

        if end_date:
            query += " AND executed_at <= ?"
            params.append(end_date + "T23:59:59")

        cursor = await self.conn.execute(query, params)
        row = await cursor.fetchone()
        return row[0] if row else 0

    # -------------------------------------------------------------------------
    # Prices (base implementation, can be overridden)
    # -------------------------------------------------------------------------

    async def get_prices(self, symbol: str, days: int | None = None) -> list[dict]:
        """Get historical prices for a security."""
        query = "SELECT * FROM prices WHERE symbol = ? ORDER BY date DESC"
        params: list[str | int] = [symbol]
        if days:
            query += " LIMIT ?"
            params.append(days)
        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
