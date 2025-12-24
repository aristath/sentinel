"""SQLite implementation of StockRepository."""

import aiosqlite
from typing import Optional, List
from datetime import datetime

from app.domain.repositories.stock_repository import StockRepository, Stock


class SQLiteStockRepository(StockRepository):
    """SQLite implementation of StockRepository."""

    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def get_by_symbol(self, symbol: str) -> Optional[Stock]:
        """Get stock by symbol."""
        cursor = await self.db.execute(
            "SELECT * FROM stocks WHERE symbol = ?",
            (symbol.upper(),)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return Stock(
            symbol=row["symbol"],
            yahoo_symbol=row["yahoo_symbol"],
            name=row["name"],
            industry=row["industry"],
            geography=row["geography"],
            priority_multiplier=row["priority_multiplier"] or 1.0,
            min_lot=row["min_lot"] or 1,
            active=bool(row["active"]),
            allow_buy=bool(row["allow_buy"]) if row["allow_buy"] is not None else True,
            allow_sell=bool(row["allow_sell"]) if row["allow_sell"] is not None else False,
        )

    async def get_all_active(self) -> List[Stock]:
        """Get all active stocks."""
        cursor = await self.db.execute(
            "SELECT * FROM stocks WHERE active = 1"
        )
        rows = await cursor.fetchall()
        return [
            Stock(
                symbol=row["symbol"],
                yahoo_symbol=row["yahoo_symbol"],
                name=row["name"],
                industry=row["industry"],
                geography=row["geography"],
                priority_multiplier=row["priority_multiplier"] or 1.0,
                min_lot=row["min_lot"] or 1,
                active=bool(row["active"]),
                allow_buy=bool(row["allow_buy"]) if row["allow_buy"] is not None else True,
                allow_sell=bool(row["allow_sell"]) if row["allow_sell"] is not None else False,
            )
            for row in rows
        ]

    async def create(self, stock: Stock, auto_commit: bool = True) -> None:
        """
        Create a new stock.
        
        Args:
            stock: Stock to create
            auto_commit: If True, commit immediately. If False, caller manages transaction.
        """
        await self.db.execute(
            """
            INSERT INTO stocks (symbol, yahoo_symbol, name, geography, industry, min_lot, active, allow_buy, allow_sell)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stock.symbol.upper(),
                stock.yahoo_symbol,
                stock.name,
                stock.geography.upper(),
                stock.industry,
                stock.min_lot,
                1 if stock.active else 0,
                1 if stock.allow_buy else 0,
                1 if stock.allow_sell else 0,
            ),
        )
        if auto_commit:
            await self.db.commit()

    async def update(self, current_symbol: str, auto_commit: bool = True, **updates) -> None:
        """
        Update stock fields.

        Args:
            current_symbol: Current stock symbol to update (renamed to avoid conflict with symbol in updates)
            auto_commit: If True, commit immediately. If False, caller manages transaction.
            **updates: Field updates (name, industry, geography, symbol for rename, etc.)
        """
        if not updates:
            return

        old_symbol = current_symbol.upper()
        new_symbol = updates.pop("symbol", None)  # Extract symbol rename if present

        # Handle symbol rename with cascading updates
        if new_symbol and new_symbol.upper() != old_symbol:
            new_symbol = new_symbol.upper()

            # Update all related tables first (before changing the primary key)
            # Tables that reference symbol: scores, positions, trades, stock_price_history
            await self.db.execute(
                "UPDATE scores SET symbol = ? WHERE symbol = ?",
                (new_symbol, old_symbol)
            )
            await self.db.execute(
                "UPDATE positions SET symbol = ? WHERE symbol = ?",
                (new_symbol, old_symbol)
            )
            await self.db.execute(
                "UPDATE trades SET symbol = ? WHERE symbol = ?",
                (new_symbol, old_symbol)
            )
            await self.db.execute(
                "UPDATE stock_price_history SET symbol = ? WHERE symbol = ?",
                (new_symbol, old_symbol)
            )

            # Update the stock symbol itself
            await self.db.execute(
                "UPDATE stocks SET symbol = ? WHERE symbol = ?",
                (new_symbol, old_symbol)
            )

            # Use new symbol for remaining updates
            old_symbol = new_symbol

        # Apply remaining field updates
        if updates:
            updates_list = []
            values = []
            for key, value in updates.items():
                if key in ("active", "allow_buy", "allow_sell"):
                    value = 1 if value else 0
                updates_list.append(f"{key} = ?")
                values.append(value)

            values.append(old_symbol)
            await self.db.execute(
                f"UPDATE stocks SET {', '.join(updates_list)} WHERE symbol = ?",
                values
            )

        if auto_commit:
            await self.db.commit()

    async def delete(self, symbol: str, auto_commit: bool = True) -> None:
        """
        Soft delete a stock (set active=False).
        
        Args:
            symbol: Stock symbol to delete
            auto_commit: If True, commit immediately. If False, caller manages transaction.
        """
        await self.db.execute(
            "UPDATE stocks SET active = 0 WHERE symbol = ?",
            (symbol.upper(),)
        )
        if auto_commit:
            await self.db.commit()

    async def get_with_scores(self) -> List[dict]:
        """Get all active stocks with their scores and positions."""
        cursor = await self.db.execute("""
            SELECT s.*, sc.technical_score, sc.analyst_score,
                   sc.fundamental_score, sc.total_score, sc.volatility,
                   sc.calculated_at,
                   p.quantity as shares, p.current_price, p.avg_price,
                   p.market_value_eur as position_value, p.currency
            FROM stocks s
            LEFT JOIN scores sc ON s.symbol = sc.symbol
            LEFT JOIN positions p ON s.symbol = p.symbol
            WHERE s.active = 1
        """)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

