"""Position repository - CRUD operations for positions table."""

from datetime import datetime
from typing import Dict, List, Optional

from app.domain.models import Position
from app.domain.value_objects.currency import Currency
from app.infrastructure.database import get_db_manager
from app.repositories.base import transaction_context


class PositionRepository:
    """Repository for current position operations."""

    def __init__(self, db=None):
        """Initialize repository.

        Args:
            db: Optional database connection for testing. If None, uses get_db_manager().state
                Can be a Database instance or raw aiosqlite.Connection (will be wrapped)
        """
        if db is not None:
            # If it's a raw connection without fetchone/fetchall, wrap it
            if not hasattr(db, "fetchone") and hasattr(db, "execute"):
                from app.repositories.base import DatabaseAdapter

                self._db = DatabaseAdapter(db)
            else:
                self._db = db
        else:
            self._manager = get_db_manager()
            self._db = self._manager.state

    async def get_by_symbol(self, symbol: str) -> Optional[Position]:
        """Get position by symbol."""
        row = await self._db.fetchone(
            "SELECT * FROM positions WHERE symbol = ?", (symbol.upper(),)
        )
        if not row:
            return None
        return self._row_to_position(row)

    async def get_all(self) -> List[Position]:
        """Get all positions."""
        rows = await self._db.fetchall("SELECT * FROM positions")
        return [self._row_to_position(row) for row in rows]

    async def upsert(self, position: Position) -> None:
        """Insert or update a position."""
        now = datetime.now().isoformat()

        async with transaction_context(self._db) as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO positions
                (symbol, quantity, avg_price, current_price, currency,
                 currency_rate, market_value_eur, cost_basis_eur,
                 unrealized_pnl, unrealized_pnl_pct, last_updated,
                 first_bought_at, last_sold_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    position.symbol.upper(),
                    position.quantity,
                    position.avg_price,
                    position.current_price,
                    position.currency,
                    position.currency_rate,
                    position.market_value_eur,
                    position.cost_basis_eur,
                    position.unrealized_pnl,
                    position.unrealized_pnl_pct,
                    position.last_updated or now,
                    position.first_bought_at,
                    position.last_sold_at,
                ),
            )

    async def delete_all(self) -> None:
        """Delete all positions (used during sync)."""
        async with transaction_context(self._db) as conn:
            await conn.execute("DELETE FROM positions")

    async def delete(self, symbol: str) -> None:
        """Delete a specific position."""
        async with transaction_context(self._db) as conn:
            await conn.execute(
                "DELETE FROM positions WHERE symbol = ?", (symbol.upper(),)
            )

    async def update_price(
        self, symbol: str, price: float, currency_rate: float = 1.0
    ) -> None:
        """Update current price and recalculate market value."""
        now = datetime.now().isoformat()

        async with transaction_context(self._db) as conn:
            await conn.execute(
                """
                UPDATE positions SET
                    current_price = ?,
                    market_value_eur = quantity * ? / ?,
                    unrealized_pnl = (? - avg_price) * quantity / ?,
                    unrealized_pnl_pct = CASE
                        WHEN avg_price > 0 THEN ((? / avg_price) - 1) * 100
                        ELSE 0
                    END,
                    last_updated = ?
                WHERE symbol = ?
                """,
                (
                    price,
                    price,
                    currency_rate,
                    price,
                    currency_rate,
                    price,
                    now,
                    symbol.upper(),
                ),
            )

    async def update_last_sold_at(self, symbol: str) -> None:
        """Update the last_sold_at timestamp after a sell."""
        now = datetime.now().isoformat()

        async with transaction_context(self._db) as conn:
            await conn.execute(
                "UPDATE positions SET last_sold_at = ? WHERE symbol = ?",
                (now, symbol.upper()),
            )

    async def get_total_value(self) -> float:
        """Get total portfolio value in EUR."""
        row = await self._db.fetchone(
            "SELECT COALESCE(SUM(market_value_eur), 0) as total FROM positions"
        )
        return row["total"] if row else 0.0

    async def get_with_stock_info(self) -> List[Dict]:
        """
        Get all positions with stock info joined from config database.

        Returns list of dicts with position and stock fields merged.
        """
        # Get positions from state.db
        position_rows = await self._db.fetchall("SELECT * FROM positions")
        if not position_rows:
            return []

        # Get stocks from config.db
        stock_rows = await self._manager.config.fetchall(
            "SELECT symbol, name, geography, industry, min_lot, allow_sell, currency "
            "FROM stocks WHERE active = 1"
        )
        stocks_by_symbol = {row["symbol"]: dict(row) for row in stock_rows}

        # Merge position and stock data
        result = []
        for pos in position_rows:
            pos_dict = dict(pos)
            stock = stocks_by_symbol.get(pos["symbol"], {})
            # Merge stock fields into position
            pos_dict["name"] = stock.get("name", pos["symbol"])
            pos_dict["geography"] = stock.get("geography", "")
            pos_dict["industry"] = stock.get("industry")
            pos_dict["min_lot"] = stock.get("min_lot", 1)
            pos_dict["allow_sell"] = bool(stock.get("allow_sell", False))
            # Use stock currency if position doesn't have one
            if not pos_dict.get("currency"):
                from app.domain.value_objects.currency import Currency

                pos_dict["currency"] = stock.get("currency") or Currency.EUR
            result.append(pos_dict)

        return result

    def _row_to_position(self, row) -> Position:
        """Convert database row to Position model."""
        return Position(
            symbol=row["symbol"],
            quantity=row["quantity"],
            avg_price=row["avg_price"],
            current_price=row["current_price"],
            currency=row["currency"] or Currency.EUR,
            currency_rate=row["currency_rate"] or 1.0,
            market_value_eur=row["market_value_eur"],
            cost_basis_eur=(
                row["cost_basis_eur"] if "cost_basis_eur" in row.keys() else None
            ),
            unrealized_pnl=(
                row["unrealized_pnl"] if "unrealized_pnl" in row.keys() else None
            ),
            unrealized_pnl_pct=(
                row["unrealized_pnl_pct"]
                if "unrealized_pnl_pct" in row.keys()
                else None
            ),
            last_updated=row["last_updated"],
            first_bought_at=(
                row["first_bought_at"] if "first_bought_at" in row.keys() else None
            ),
            last_sold_at=row["last_sold_at"] if "last_sold_at" in row.keys() else None,
        )
