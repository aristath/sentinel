"""SQLite implementation of PortfolioRepository."""

import aiosqlite
from typing import Optional, List

from app.domain.repositories.portfolio_repository import (
    PortfolioRepository,
    PortfolioSnapshot,
)


class SQLitePortfolioRepository(PortfolioRepository):
    """SQLite implementation of PortfolioRepository."""

    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def get_latest(self) -> Optional[PortfolioSnapshot]:
        """Get the latest portfolio snapshot."""
        cursor = await self.db.execute("""
            SELECT * FROM portfolio_snapshots
            ORDER BY date DESC LIMIT 1
        """)
        row = await cursor.fetchone()
        if not row:
            return None
        return PortfolioSnapshot(
            date=row["date"],
            total_value=row["total_value"],
            cash_balance=row["cash_balance"],
            geo_eu_pct=row["geo_eu_pct"],
            geo_asia_pct=row["geo_asia_pct"],
            geo_us_pct=row["geo_us_pct"],
        )

    async def get_history(self, limit: int = 90) -> List[PortfolioSnapshot]:
        """Get portfolio history."""
        cursor = await self.db.execute("""
            SELECT * FROM portfolio_snapshots
            ORDER BY date DESC
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        return [
            PortfolioSnapshot(
                date=row["date"],
                total_value=row["total_value"],
                cash_balance=row["cash_balance"],
                geo_eu_pct=row["geo_eu_pct"],
                geo_asia_pct=row["geo_asia_pct"],
                geo_us_pct=row["geo_us_pct"],
            )
            for row in rows
        ]

    async def create(self, snapshot: PortfolioSnapshot, auto_commit: bool = True) -> None:
        """
        Create a new portfolio snapshot.
        
        Args:
            snapshot: Portfolio snapshot to create
            auto_commit: If True, commit immediately. If False, caller manages transaction.
        """
        await self.db.execute(
            """
            INSERT OR REPLACE INTO portfolio_snapshots
            (date, total_value, cash_balance, geo_eu_pct, geo_asia_pct, geo_us_pct)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.date,
                snapshot.total_value,
                snapshot.cash_balance,
                snapshot.geo_eu_pct,
                snapshot.geo_asia_pct,
                snapshot.geo_us_pct,
            ),
        )
        if auto_commit:
            await self.db.commit()

    async def get_latest_cash_balance(self) -> float:
        """Get cash balance from latest snapshot."""
        cursor = await self.db.execute("""
            SELECT cash_balance FROM portfolio_snapshots
            ORDER BY date DESC LIMIT 1
        """)
        row = await cursor.fetchone()
        return row[0] if row else 0.0

