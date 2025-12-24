"""Trade repository - operations for trades table (ledger)."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Set

from app.domain.models import Trade
from app.infrastructure.database import get_db_manager

logger = logging.getLogger(__name__)


class TradeRepository:
    """Repository for trade history operations (append-only ledger)."""

    def __init__(self):
        self._db = get_db_manager().ledger

    async def create(self, trade: Trade) -> None:
        """Create a new trade record."""
        now = datetime.now().isoformat()
        executed_at = (
            trade.executed_at.isoformat()
            if isinstance(trade.executed_at, datetime)
            else str(trade.executed_at)
        )

        async with self._db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO trades
                (symbol, side, quantity, price, executed_at, order_id,
                 currency, currency_rate, value_eur, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade.symbol.upper(),
                    trade.side.upper(),
                    trade.quantity,
                    trade.price,
                    executed_at,
                    trade.order_id,
                    trade.currency,
                    trade.currency_rate,
                    trade.value_eur,
                    trade.source,
                    now,
                )
            )

    async def get_by_order_id(self, order_id: str) -> Optional[Trade]:
        """Get trade by broker order ID."""
        row = await self._db.fetchone(
            "SELECT * FROM trades WHERE order_id = ?",
            (order_id,)
        )
        if not row:
            return None
        return self._row_to_trade(row)

    async def exists(self, order_id: str) -> bool:
        """Check if trade with order_id already exists."""
        row = await self._db.fetchone(
            "SELECT 1 FROM trades WHERE order_id = ?",
            (order_id,)
        )
        return row is not None

    async def get_history(self, limit: int = 50) -> List[Trade]:
        """Get trade history, most recent first."""
        rows = await self._db.fetchall(
            """
            SELECT * FROM trades
            ORDER BY executed_at DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [self._row_to_trade(row) for row in rows]

    async def get_all_in_range(self, start_date: str, end_date: str) -> List[Trade]:
        """Get all trades within a date range, ordered by date."""
        rows = await self._db.fetchall(
            """
            SELECT * FROM trades
            WHERE executed_at >= ? AND executed_at <= ?
            ORDER BY executed_at ASC
            """,
            (start_date, end_date)
        )
        return [self._row_to_trade(row) for row in rows]

    async def get_by_symbol(self, symbol: str, limit: int = 100) -> List[Trade]:
        """Get trades for a specific symbol."""
        rows = await self._db.fetchall(
            """
            SELECT * FROM trades
            WHERE symbol = ?
            ORDER BY executed_at DESC
            LIMIT ?
            """,
            (symbol.upper(), limit)
        )
        return [self._row_to_trade(row) for row in rows]

    async def get_recently_bought_symbols(self, days: int = 30) -> Set[str]:
        """Get symbols that were bought in the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = await self._db.fetchall(
            """
            SELECT DISTINCT symbol FROM trades
            WHERE UPPER(side) = 'BUY' AND executed_at >= ?
            """,
            (cutoff,)
        )
        return {row["symbol"] for row in rows}

    async def get_recently_sold_symbols(self, days: int = 30) -> Set[str]:
        """Get symbols that were sold in the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = await self._db.fetchall(
            """
            SELECT DISTINCT symbol FROM trades
            WHERE UPPER(side) = 'SELL' AND executed_at >= ?
            """,
            (cutoff,)
        )
        return {row["symbol"] for row in rows}

    async def get_first_buy_date(self, symbol: str) -> Optional[str]:
        """Get the date of first buy for a symbol."""
        row = await self._db.fetchone(
            """
            SELECT MIN(executed_at) as first_buy FROM trades
            WHERE symbol = ? AND UPPER(side) = 'BUY'
            """,
            (symbol.upper(),)
        )
        return row["first_buy"] if row else None

    async def get_last_sell_date(self, symbol: str) -> Optional[str]:
        """Get the date of last sell for a symbol."""
        row = await self._db.fetchone(
            """
            SELECT MAX(executed_at) as last_sell FROM trades
            WHERE symbol = ? AND UPPER(side) = 'SELL'
            """,
            (symbol.upper(),)
        )
        return row["last_sell"] if row else None

    async def get_trade_dates(self) -> dict[str, dict]:
        """Get first_buy and last_sell dates for all symbols."""
        rows = await self._db.fetchall(
            """
            SELECT
                symbol,
                MIN(CASE WHEN UPPER(side) = 'BUY' THEN executed_at END) as first_buy,
                MAX(CASE WHEN UPPER(side) = 'SELL' THEN executed_at END) as last_sell
            FROM trades
            GROUP BY symbol
            """
        )
        return {
            row["symbol"]: {
                "first_bought_at": row["first_buy"],
                "last_sold_at": row["last_sell"]
            }
            for row in rows
        }

    async def get_position_history(self, start_date: str, end_date: str) -> List[dict]:
        """
        Get historical position quantities by date for portfolio reconstruction.
        
        Returns list of dicts with keys: date, symbol, quantity
        where quantity is cumulative (sum of BUY - sum of SELL up to that date).
        """
        # Get all trades in date range, ordered by date
        rows = await self._db.fetchall(
            """
            SELECT symbol, side, quantity, executed_at
            FROM trades
            WHERE executed_at >= ? AND executed_at <= ?
            ORDER BY executed_at ASC
            """,
            (start_date, end_date)
        )
        
        # Group by date and symbol, calculate cumulative quantities
        positions_by_date = {}  # {date: {symbol: quantity}}
        
        for row in rows:
            date = row["executed_at"][:10]  # Extract YYYY-MM-DD
            symbol = row["symbol"]
            side = row["side"].upper()
            quantity = row["quantity"]
            
            if date not in positions_by_date:
                positions_by_date[date] = {}
            
            if symbol not in positions_by_date[date]:
                positions_by_date[date][symbol] = 0.0
            
            if side == "BUY":
                positions_by_date[date][symbol] += quantity
            elif side == "SELL":
                positions_by_date[date][symbol] -= quantity
        
        # Convert to list format and ensure cumulative quantities
        result = []
        cumulative_positions = {}  # {symbol: cumulative_quantity}
        
        # Get all unique dates sorted
        all_dates = sorted(positions_by_date.keys())
        
        for date in all_dates:
            # Update cumulative positions for this date
            for symbol, delta in positions_by_date[date].items():
                if symbol not in cumulative_positions:
                    cumulative_positions[symbol] = 0.0
                cumulative_positions[symbol] += delta
                # Don't allow negative positions (shouldn't happen, but safety check)
                if cumulative_positions[symbol] < 0:
                    cumulative_positions[symbol] = 0.0
            
            # Add entry for each symbol with position on this date
            for symbol, quantity in cumulative_positions.items():
                if quantity > 0:
                    result.append({
                        "date": date,
                        "symbol": symbol,
                        "quantity": quantity
                    })
        
        return result

    def _row_to_trade(self, row) -> Trade:
        """Convert database row to Trade model."""
        executed_at = None
        if row["executed_at"]:
            try:
                executed_at = datetime.fromisoformat(str(row["executed_at"]))
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse executed_at: {e}")
                executed_at = datetime.now()

        return Trade(
            id=row["id"],
            symbol=row["symbol"],
            side=row["side"],
            quantity=row["quantity"],
            price=row["price"],
            executed_at=executed_at,
            order_id=row["order_id"],
            currency=row["currency"] if "currency" in row.keys() else None,
            currency_rate=row["currency_rate"] if "currency_rate" in row.keys() else None,
            value_eur=row["value_eur"] if "value_eur" in row.keys() else None,
            source=row["source"] if "source" in row.keys() else "tradernet",
        )
