"""History repository - operations for per-symbol price databases."""

from datetime import datetime
from typing import List, Optional

from app.core.database.manager import get_db_manager
from app.modules.portfolio.database.schemas import init_history_schema
from app.modules.portfolio.domain.models import DailyPrice, MonthlyPrice


class HistoryRepository:
    """Repository for per-symbol historical price data."""

    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self._db_manager = get_db_manager()
        self._db = None  # Lazy loaded

    async def _get_db(self):
        """Get or initialize the symbol's database."""
        if self._db is None:
            self._db = await self._db_manager.history(self.symbol)
            await init_history_schema(self._db)
        return self._db

    async def get_daily_prices(self, limit: int = 365) -> List[DailyPrice]:
        """Get daily prices, most recent first."""
        db = await self._get_db()
        rows = await db.fetchall(
            """
            SELECT * FROM daily_prices
            ORDER BY date DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [self._row_to_daily(row) for row in rows]

    async def get_daily_range(self, start_date: str, end_date: str) -> List[DailyPrice]:
        """Get daily prices within a date range."""
        db = await self._get_db()
        rows = await db.fetchall(
            """
            SELECT * FROM daily_prices
            WHERE date >= ? AND date <= ?
            ORDER BY date ASC
            """,
            (start_date, end_date),
        )
        return [self._row_to_daily(row) for row in rows]

    async def get_latest_price(self) -> Optional[DailyPrice]:
        """Get most recent daily price."""
        db = await self._get_db()
        row = await db.fetchone("SELECT * FROM daily_prices ORDER BY date DESC LIMIT 1")
        if not row:
            return None
        return self._row_to_daily(row)

    async def upsert_daily(self, price: DailyPrice) -> None:
        """Insert or update a daily price."""
        db = await self._get_db()
        now = datetime.now().isoformat()

        async with db.transaction() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO daily_prices
                (date, open_price, high_price, low_price, close_price,
                 volume, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    price.date,
                    price.open_price,
                    price.high_price,
                    price.low_price,
                    price.close_price,
                    price.volume,
                    price.source,
                    now,
                ),
            )

    async def upsert_daily_batch(self, prices: List[DailyPrice]) -> int:
        """Insert or update multiple daily prices."""
        if not prices:
            return 0

        db = await self._get_db()
        now = datetime.now().isoformat()

        async with db.transaction() as conn:
            for price in prices:
                await conn.execute(
                    """
                    INSERT OR REPLACE INTO daily_prices
                    (date, open_price, high_price, low_price, close_price,
                     volume, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        price.date,
                        price.open_price,
                        price.high_price,
                        price.low_price,
                        price.close_price,
                        price.volume,
                        price.source,
                        now,
                    ),
                )

        return len(prices)

    async def get_monthly_prices(self, limit: int = 120) -> List[MonthlyPrice]:
        """Get monthly prices (for CAGR calculations)."""
        db = await self._get_db()
        rows = await db.fetchall(
            """
            SELECT * FROM monthly_prices
            ORDER BY year_month DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [self._row_to_monthly(row) for row in rows]

    async def upsert_monthly(self, price: MonthlyPrice) -> None:
        """Insert or update a monthly price."""
        db = await self._get_db()
        now = datetime.now().isoformat()

        async with db.transaction() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO monthly_prices
                (year_month, avg_close, avg_adj_close, min_price,
                 max_price, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    price.year_month,
                    price.avg_close,
                    price.avg_adj_close,
                    price.min_price,
                    price.max_price,
                    price.source,
                    now,
                ),
            )

    async def aggregate_to_monthly(self) -> int:
        """Aggregate daily prices to monthly averages."""
        db = await self._get_db()
        now = datetime.now().isoformat()

        async with db.transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT OR REPLACE INTO monthly_prices
                (year_month, avg_close, avg_adj_close, min_price, max_price, source, created_at)
                SELECT
                    strftime('%Y-%m', date) as year_month,
                    AVG(close_price) as avg_close,
                    AVG(close_price) as avg_adj_close,
                    MIN(low_price) as min_price,
                    MAX(high_price) as max_price,
                    'calculated' as source,
                    ? as created_at
                FROM daily_prices
                GROUP BY strftime('%Y-%m', date)
                """,
                (now,),
            )
            return cursor.rowcount

    async def delete_before(self, date: str) -> int:
        """Delete daily prices before a date."""
        db = await self._get_db()

        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM daily_prices WHERE date < ?", (date,)
        )
        row = await cursor.fetchone()
        count = row["cnt"] if row else 0

        if count > 0:
            async with db.transaction() as conn:
                await conn.execute("DELETE FROM daily_prices WHERE date < ?", (date,))

        return count

    async def get_52_week_high(self) -> Optional[float]:
        """Get 52-week high price."""
        db = await self._get_db()
        row = await db.fetchone(
            """
            SELECT MAX(high_price) as high
            FROM daily_prices
            WHERE date >= date('now', '-52 weeks')
            """
        )
        return row["high"] if row else None

    async def get_52_week_low(self) -> Optional[float]:
        """Get 52-week low price."""
        db = await self._get_db()
        row = await db.fetchone(
            """
            SELECT MIN(low_price) as low
            FROM daily_prices
            WHERE date >= date('now', '-52 weeks')
            """
        )
        return row["low"] if row else None

    async def integrity_check(self) -> str:
        """Run integrity check on this symbol's database."""
        db = await self._get_db()
        return await db.integrity_check()

    def _row_to_daily(self, row) -> DailyPrice:
        """Convert database row to DailyPrice model."""
        return DailyPrice(
            date=row["date"],
            close_price=row["close_price"],
            open_price=row["open_price"],
            high_price=row["high_price"],
            low_price=row["low_price"],
            volume=row["volume"],
            source=row["source"] or "yahoo",
        )

    def _row_to_monthly(self, row) -> MonthlyPrice:
        """Convert database row to MonthlyPrice model."""
        return MonthlyPrice(
            year_month=row["year_month"],
            avg_close=row["avg_close"],
            avg_adj_close=row["avg_adj_close"],
            min_price=row["min_price"],
            max_price=row["max_price"],
            source=row["source"] or "calculated",
        )
