"""SQLite implementation of PositionRepository."""

import aiosqlite
from typing import Optional, List
from datetime import datetime

from app.domain.repositories.position_repository import PositionRepository, Position


class SQLitePositionRepository(PositionRepository):
    """SQLite implementation of PositionRepository."""

    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def get_by_symbol(self, symbol: str) -> Optional[Position]:
        """Get position by symbol."""
        cursor = await self.db.execute(
            "SELECT * FROM positions WHERE symbol = ?",
            (symbol.upper(),)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return Position(
            symbol=row["symbol"],
            quantity=row["quantity"],
            avg_price=row["avg_price"],
            current_price=row["current_price"],
            currency=row["currency"],
            currency_rate=row["currency_rate"],
            market_value_eur=row["market_value_eur"],
            last_updated=row["last_updated"],
            first_bought_at=row["first_bought_at"] if "first_bought_at" in row.keys() else None,
            last_sold_at=row["last_sold_at"] if "last_sold_at" in row.keys() else None,
        )

    async def get_all(self) -> List[Position]:
        """Get all positions."""
        cursor = await self.db.execute("SELECT * FROM positions")
        rows = await cursor.fetchall()
        return [
            Position(
                symbol=row["symbol"],
                quantity=row["quantity"],
                avg_price=row["avg_price"],
                current_price=row["current_price"],
                currency=row["currency"],
                currency_rate=row["currency_rate"],
                market_value_eur=row["market_value_eur"],
                last_updated=row["last_updated"],
                first_bought_at=row["first_bought_at"] if "first_bought_at" in row.keys() else None,
                last_sold_at=row["last_sold_at"] if "last_sold_at" in row.keys() else None,
            )
            for row in rows
        ]

    async def upsert(self, position: Position, auto_commit: bool = True) -> None:
        """
        Insert or update a position.

        Args:
            position: Position to upsert
            auto_commit: If True, commit immediately. If False, caller manages transaction.
        """
        # Check if position exists to preserve first_bought_at
        existing = await self.get_by_symbol(position.symbol)

        # Preserve first_bought_at if it exists, otherwise use provided or set new
        first_bought_at = position.first_bought_at
        last_sold_at = position.last_sold_at
        if existing:
            # Keep existing first_bought_at if not provided
            if first_bought_at is None and existing.first_bought_at:
                first_bought_at = existing.first_bought_at
            # Keep existing last_sold_at if not provided
            if last_sold_at is None and existing.last_sold_at:
                last_sold_at = existing.last_sold_at
        elif first_bought_at is None:
            # New position - set first_bought_at to now
            first_bought_at = datetime.now().isoformat()

        await self.db.execute(
            """
            INSERT OR REPLACE INTO positions
            (symbol, quantity, avg_price, current_price, currency, currency_rate, market_value_eur, last_updated, first_bought_at, last_sold_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                position.symbol,
                position.quantity,
                position.avg_price,
                position.current_price,
                position.currency,
                position.currency_rate,
                position.market_value_eur,
                position.last_updated or datetime.now().isoformat(),
                first_bought_at,
                last_sold_at,
            ),
        )
        if auto_commit:
            await self.db.commit()

    async def delete_all(self, auto_commit: bool = True) -> None:
        """
        Delete all positions (used during sync).
        
        Args:
            auto_commit: If True, commit immediately. If False, caller manages transaction.
        """
        await self.db.execute("DELETE FROM positions")
        if auto_commit:
            await self.db.commit()

    async def get_with_stock_info(self) -> List[dict]:
        """Get all positions with stock information including sell eligibility."""
        cursor = await self.db.execute("""
            SELECT p.symbol, p.quantity, p.current_price, p.avg_price,
                   p.market_value_eur, p.currency, p.first_bought_at, p.last_sold_at,
                   s.name, s.geography, s.industry, s.allow_buy, s.allow_sell, s.min_lot
            FROM positions p
            JOIN stocks s ON p.symbol = s.symbol
        """)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def update_last_sold_at(self, symbol: str, auto_commit: bool = True) -> None:
        """
        Update the last_sold_at timestamp for a position after a sell.

        Args:
            symbol: Stock symbol
            auto_commit: If True, commit immediately. If False, caller manages transaction.
        """
        await self.db.execute(
            "UPDATE positions SET last_sold_at = ? WHERE symbol = ?",
            (datetime.now().isoformat(), symbol.upper())
        )
        if auto_commit:
            await self.db.commit()

