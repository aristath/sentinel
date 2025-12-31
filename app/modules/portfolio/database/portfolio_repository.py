"""Portfolio repository - operations for portfolio_snapshots table (snapshots.db)."""

from datetime import datetime
from typing import List, Optional

from app.core.database.manager import get_db_manager
from app.modules.portfolio.domain.models import PortfolioSnapshot
from app.repositories.base import transaction_context


class PortfolioRepository:
    """Repository for portfolio snapshot operations."""

    def __init__(self, db=None):
        """Initialize repository.

        Args:
            db: Optional database connection for testing. If None, uses get_db_manager().snapshots
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
            self._db = get_db_manager().snapshots

    async def get_by_date(self, date: str) -> Optional[PortfolioSnapshot]:
        """Get snapshot for a specific date."""
        row = await self._db.fetchone(
            "SELECT * FROM portfolio_snapshots WHERE date = ?", (date,)
        )
        if not row:
            return None
        return self._row_to_snapshot(row)

    async def get_latest(self) -> Optional[PortfolioSnapshot]:
        """Get most recent snapshot."""
        row = await self._db.fetchone(
            "SELECT * FROM portfolio_snapshots ORDER BY date DESC LIMIT 1"
        )
        if not row:
            return None
        return self._row_to_snapshot(row)

    async def get_latest_cash_balance(self) -> float:
        """Get cash balance from most recent snapshot."""
        row = await self._db.fetchone(
            "SELECT cash_balance FROM portfolio_snapshots ORDER BY date DESC LIMIT 1"
        )
        return row["cash_balance"] if row else 0.0

    async def get_history(self, days: int = 90) -> List[PortfolioSnapshot]:
        """Get snapshot history for last N days."""
        rows = await self._db.fetchall(
            """
            SELECT * FROM portfolio_snapshots
            ORDER BY date DESC
            LIMIT ?
            """,
            (days,),
        )
        return [self._row_to_snapshot(row) for row in rows]

    async def get_range(
        self, start_date: str, end_date: str
    ) -> List[PortfolioSnapshot]:
        """Get snapshots within a date range."""
        rows = await self._db.fetchall(
            """
            SELECT * FROM portfolio_snapshots
            WHERE date >= ? AND date <= ?
            ORDER BY date ASC
            """,
            (start_date, end_date),
        )
        return [self._row_to_snapshot(row) for row in rows]

    async def upsert(self, snapshot: PortfolioSnapshot) -> None:
        """Insert or update a snapshot."""
        now = datetime.now().isoformat()

        async with transaction_context(self._db) as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO portfolio_snapshots
                (date, total_value, cash_balance, invested_value,
                 unrealized_pnl, geo_eu_pct, geo_asia_pct, geo_us_pct,
                 position_count, annual_turnover, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.date,
                    snapshot.total_value,
                    snapshot.cash_balance,
                    snapshot.invested_value,
                    snapshot.unrealized_pnl,
                    snapshot.geo_eu_pct,
                    snapshot.geo_asia_pct,
                    snapshot.geo_us_pct,
                    snapshot.position_count,
                    snapshot.annual_turnover,
                    now,
                ),
            )

    async def delete_before(self, date: str) -> int:
        """Delete snapshots before a date. Returns count deleted."""
        cursor = await self._db.execute(
            "SELECT COUNT(*) as cnt FROM portfolio_snapshots WHERE date < ?", (date,)
        )
        row = await cursor.fetchone()
        count = row["cnt"] if row else 0

        if count > 0:
            async with transaction_context(self._db) as conn:
                await conn.execute(
                    "DELETE FROM portfolio_snapshots WHERE date < ?", (date,)
                )

        return count

    async def get_value_change(self, days: int = 30) -> dict:
        """Get portfolio value change over N days."""
        snapshots = await self.get_history(days)
        if len(snapshots) < 2:
            return {"change": 0, "change_pct": 0, "days": 0}

        latest = snapshots[0]
        oldest = snapshots[-1]

        change = latest.total_value - oldest.total_value
        change_pct = (change / oldest.total_value * 100) if oldest.total_value else 0

        return {
            "change": change,
            "change_pct": change_pct,
            "days": len(snapshots),
            "start_value": oldest.total_value,
            "end_value": latest.total_value,
        }

    def _row_to_snapshot(self, row) -> PortfolioSnapshot:
        """Convert database row to PortfolioSnapshot model."""

        def safe_get(key, default=None):
            try:
                return row[key]
            except (KeyError, IndexError):
                return default

        return PortfolioSnapshot(
            date=row["date"],
            total_value=row["total_value"],
            cash_balance=row["cash_balance"],
            invested_value=safe_get("invested_value"),
            unrealized_pnl=safe_get("unrealized_pnl"),
            geo_eu_pct=safe_get("geo_eu_pct"),
            geo_asia_pct=safe_get("geo_asia_pct"),
            geo_us_pct=safe_get("geo_us_pct"),
            position_count=safe_get("position_count"),
            annual_turnover=safe_get("annual_turnover"),
        )
