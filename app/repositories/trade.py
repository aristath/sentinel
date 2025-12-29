"""Trade repository - operations for trades table (ledger)."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Set

from app.domain.models import Trade
from app.infrastructure.database import get_db_manager
from app.repositories.base import safe_get_datetime, transaction_context

logger = logging.getLogger(__name__)


def _process_pre_start_trades(
    pre_start_trades: list, cumulative_positions: dict
) -> None:
    """Process trades before start_date to build initial positions."""
    for row in pre_start_trades:
        symbol = row["symbol"]
        side = row["side"].upper()
        quantity = row["quantity"]

        if symbol not in cumulative_positions:
            cumulative_positions[symbol] = 0.0

        if side == "BUY":
            cumulative_positions[symbol] += quantity
        elif side == "SELL":
            cumulative_positions[symbol] -= quantity
            if cumulative_positions[symbol] < 0:
                cumulative_positions[symbol] = 0.0


def _build_initial_positions(cumulative_positions: dict, start_date: str) -> list:
    """Build initial position entries at start_date."""
    result = []
    for symbol, quantity in cumulative_positions.items():
        if quantity > 0:
            result.append({"date": start_date, "symbol": symbol, "quantity": quantity})
    return result


def _build_positions_by_date(in_range_trades: list) -> dict:
    """Build positions_by_date dictionary from in-range trades."""
    positions_by_date: dict[str, dict[str, float]] = {}
    for row in in_range_trades:
        date = row["executed_at"][:10]
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

    return positions_by_date


def _update_positions_for_date(
    date: str, positions_by_date: dict, cumulative_positions: dict, result: list
) -> None:
    """Update cumulative positions for a date and add to result."""
    for symbol, delta in positions_by_date[date].items():
        if symbol not in cumulative_positions:
            cumulative_positions[symbol] = 0.0
        cumulative_positions[symbol] += delta
        if cumulative_positions[symbol] < 0:
            cumulative_positions[symbol] = 0.0

    for symbol, quantity in cumulative_positions.items():
        if quantity > 0:
            result.append({"date": date, "symbol": symbol, "quantity": quantity})


def _process_in_range_trades(
    in_range_trades: list, cumulative_positions: dict, result: list
) -> None:
    """Process trades in date range and update result."""
    positions_by_date = _build_positions_by_date(in_range_trades)

    for date in sorted(positions_by_date.keys()):
        _update_positions_for_date(
            date, positions_by_date, cumulative_positions, result
        )


class TradeRepository:
    """Repository for trade history operations (append-only ledger)."""

    def __init__(self, db=None):
        """Initialize repository.

        Args:
            db: Optional database connection for testing. If None, uses get_db_manager().ledger
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
            self._db = get_db_manager().ledger

    async def create(self, trade: Trade) -> None:
        """Create a new trade record."""
        now = datetime.now().isoformat()
        executed_at = (
            trade.executed_at.isoformat()
            if isinstance(trade.executed_at, datetime)
            else str(trade.executed_at)
        )

        async with transaction_context(self._db) as conn:
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
                ),
            )

    async def get_by_order_id(self, order_id: str) -> Optional[Trade]:
        """Get trade by broker order ID."""
        row = await self._db.fetchone(
            "SELECT * FROM trades WHERE order_id = ?", (order_id,)
        )
        if not row:
            return None
        return self._row_to_trade(row)

    async def exists(self, order_id: str) -> bool:
        """Check if trade with order_id already exists."""
        row = await self._db.fetchone(
            "SELECT 1 FROM trades WHERE order_id = ?", (order_id,)
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
            (limit,),
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
            (start_date, end_date),
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
            (symbol.upper(), limit),
        )
        return [self._row_to_trade(row) for row in rows]

    async def get_by_isin(self, isin: str, limit: int = 100) -> List[Trade]:
        """Get trades for a specific ISIN."""
        rows = await self._db.fetchall(
            """
            SELECT * FROM trades
            WHERE isin = ?
            ORDER BY executed_at DESC
            LIMIT ?
            """,
            (isin.upper(), limit),
        )
        return [self._row_to_trade(row) for row in rows]

    async def get_by_identifier(self, identifier: str, limit: int = 100) -> List[Trade]:
        """Get trades by symbol or ISIN."""
        identifier = identifier.strip().upper()

        # Check if it looks like an ISIN (12 chars, country code + alphanumeric)
        if len(identifier) == 12 and identifier[:2].isalpha():
            trades = await self.get_by_isin(identifier, limit)
            if trades:
                return trades

        # Try symbol lookup
        return await self.get_by_symbol(identifier, limit)

    async def get_recently_bought_symbols(self, days: int = 30) -> Set[str]:
        """Get symbols that were bought in the last N days (excluding RESEARCH trades and failed orders)."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = await self._db.fetchall(
            """
            SELECT DISTINCT symbol FROM trades
            WHERE UPPER(side) = 'BUY'
              AND executed_at >= ?
              AND order_id IS NOT NULL
              AND order_id != ''
              AND order_id NOT LIKE 'RESEARCH_%'
            """,
            (cutoff,),
        )
        return {row["symbol"] for row in rows}

    async def get_recently_sold_symbols(self, days: int = 30) -> Set[str]:
        """Get symbols that were sold in the last N days (excluding RESEARCH trades)."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = await self._db.fetchall(
            """
            SELECT DISTINCT symbol FROM trades
            WHERE UPPER(side) = 'SELL'
              AND executed_at >= ?
              AND (order_id IS NULL OR order_id NOT LIKE 'RESEARCH_%')
            """,
            (cutoff,),
        )
        return {row["symbol"] for row in rows}

    async def has_recent_sell_order(self, symbol: str, hours: int = 2) -> bool:
        """
        Check if there's a recent SELL order for the given symbol (excluding RESEARCH trades).

        Args:
            symbol: Stock symbol to check (e.g., "AAPL.US")
            hours: Number of hours to look back (default: 2)

        Returns:
            True if a SELL order exists for this symbol within the time window
        """
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        row = await self._db.fetchone(
            """
            SELECT 1 FROM trades
            WHERE symbol = ?
              AND UPPER(side) = 'SELL'
              AND executed_at >= ?
              AND (order_id IS NULL OR order_id NOT LIKE 'RESEARCH_%')
            LIMIT 1
            """,
            (symbol.upper(), cutoff),
        )
        return row is not None

    async def get_first_buy_date(self, symbol: str) -> Optional[str]:
        """Get the date of first buy for a symbol."""
        row = await self._db.fetchone(
            """
            SELECT MIN(executed_at) as first_buy FROM trades
            WHERE symbol = ? AND UPPER(side) = 'BUY'
            """,
            (symbol.upper(),),
        )
        return row["first_buy"] if row else None

    async def get_last_buy_date(self, symbol: str) -> Optional[str]:
        """Get the date of the most recent buy for a symbol (when current position was last established)."""
        row = await self._db.fetchone(
            """
            SELECT MAX(executed_at) as last_buy FROM trades
            WHERE symbol = ? AND UPPER(side) = 'BUY'
            """,
            (symbol.upper(),),
        )
        return row["last_buy"] if row else None

    async def get_last_sell_date(self, symbol: str) -> Optional[str]:
        """Get the date of last sell for a symbol."""
        row = await self._db.fetchone(
            """
            SELECT MAX(executed_at) as last_sell FROM trades
            WHERE symbol = ? AND UPPER(side) = 'SELL'
            """,
            (symbol.upper(),),
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
                "last_sold_at": row["last_sell"],
            }
            for row in rows
        }

    async def get_recent_trades(self, symbol: str, days: int = 30) -> List[Trade]:
        """Get recent trades for a symbol within N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = await self._db.fetchall(
            """
            SELECT * FROM trades
            WHERE symbol = ? AND executed_at >= ?
            ORDER BY executed_at DESC
            """,
            (symbol.upper(), cutoff),
        )
        return [self._row_to_trade(row) for row in rows]

    async def get_position_history(self, start_date: str, end_date: str) -> List[dict]:
        """
        Get historical position quantities by date for portfolio reconstruction.

        Includes positions held before start_date (carried forward).
        Returns list of dicts with keys: date, symbol, quantity
        where quantity is cumulative (sum of BUY - sum of SELL up to that date).
        """
        # Get all trades up to end_date to build complete position history
        rows = await self._db.fetchall(
            """
            SELECT symbol, side, quantity, executed_at
            FROM trades
            WHERE executed_at <= ?
            ORDER BY executed_at ASC
            """,
            (end_date,),
        )

        # Build position state up to start_date
        cumulative_positions: dict[str, float] = {}  # {symbol: quantity}
        pre_start_trades = []
        in_range_trades = []

        for row in rows:
            date = row["executed_at"][:10]  # Extract YYYY-MM-DD
            if date < start_date:
                pre_start_trades.append(row)
            else:
                in_range_trades.append(row)

        _process_pre_start_trades(pre_start_trades, cumulative_positions)
        result = _build_initial_positions(cumulative_positions, start_date)
        _process_in_range_trades(in_range_trades, cumulative_positions, result)

        return result

    def _row_to_trade(self, row) -> Trade:
        """Convert database row to Trade model."""
        executed_at: datetime
        if row["executed_at"]:
            parsed = safe_get_datetime(row, "executed_at")
            executed_at = parsed if parsed else datetime.now()
        else:
            executed_at = datetime.now()

        keys = row.keys()
        return Trade(
            id=row["id"],
            symbol=row["symbol"],
            side=row["side"],
            quantity=row["quantity"],
            price=row["price"],
            executed_at=executed_at,
            isin=row["isin"] if "isin" in keys else None,
            order_id=row["order_id"],
            currency=row["currency"] if "currency" in keys else None,
            currency_rate=row["currency_rate"] if "currency_rate" in keys else None,
            value_eur=row["value_eur"] if "value_eur" in keys else None,
            source=row["source"] if "source" in keys else "tradernet",
        )
