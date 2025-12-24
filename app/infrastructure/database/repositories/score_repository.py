"""SQLite implementation of ScoreRepository."""

import aiosqlite
from typing import Optional, List
from datetime import datetime

from app.domain.repositories.score_repository import ScoreRepository, StockScore


def _safe_get(row: aiosqlite.Row, key: str, default=None):
    """Safely get a value from a row, handling missing columns."""
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


class SQLiteScoreRepository(ScoreRepository):
    """SQLite implementation of ScoreRepository."""

    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def get_by_symbol(self, symbol: str) -> Optional[StockScore]:
        """Get score by symbol."""
        cursor = await self.db.execute(
            "SELECT * FROM scores WHERE symbol = ?",
            (symbol.upper(),)
        )
        row = await cursor.fetchone()
        if not row:
            return None

        calculated_at = None
        if row["calculated_at"]:
            try:
                calculated_at = datetime.fromisoformat(row["calculated_at"])
            except (ValueError, TypeError):
                pass

        return StockScore(
            symbol=row["symbol"],
            # New primary scores
            quality_score=_safe_get(row, "quality_score"),
            opportunity_score=_safe_get(row, "opportunity_score"),
            analyst_score=row["analyst_score"],
            allocation_fit_score=_safe_get(row, "allocation_fit_score"),
            # Quality breakdown
            cagr_score=_safe_get(row, "cagr_score"),
            consistency_score=_safe_get(row, "consistency_score"),
            history_years=_safe_get(row, "history_years"),
            # Legacy fields
            technical_score=row["technical_score"],
            fundamental_score=row["fundamental_score"],
            # Common fields
            total_score=row["total_score"],
            volatility=row["volatility"],
            calculated_at=calculated_at,
        )

    async def upsert(self, score: StockScore, auto_commit: bool = True) -> None:
        """
        Insert or update a score.

        Args:
            score: Stock score to upsert
            auto_commit: If True, commit immediately. If False, caller manages transaction.
        """
        calculated_at_str = None
        if score.calculated_at:
            if isinstance(score.calculated_at, datetime):
                calculated_at_str = score.calculated_at.isoformat()
            else:
                calculated_at_str = str(score.calculated_at)

        await self.db.execute(
            """
            INSERT OR REPLACE INTO scores
            (symbol, technical_score, analyst_score, fundamental_score,
             total_score, volatility, calculated_at,
             quality_score, opportunity_score, allocation_fit_score,
             cagr_score, consistency_score, history_years)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                score.symbol,
                # Legacy fields
                score.technical_score,
                score.analyst_score,
                score.fundamental_score,
                score.total_score,
                score.volatility,
                calculated_at_str,
                # New fields
                score.quality_score,
                score.opportunity_score,
                score.allocation_fit_score,
                score.cagr_score,
                score.consistency_score,
                score.history_years,
            ),
        )
        if auto_commit:
            await self.db.commit()

    async def get_all(self) -> List[StockScore]:
        """Get all scores."""
        cursor = await self.db.execute("SELECT * FROM scores")
        rows = await cursor.fetchall()
        scores = []
        for row in rows:
            calculated_at = None
            if row["calculated_at"]:
                try:
                    calculated_at = datetime.fromisoformat(row["calculated_at"])
                except (ValueError, TypeError):
                    pass

            scores.append(StockScore(
                symbol=row["symbol"],
                # New primary scores
                quality_score=_safe_get(row, "quality_score"),
                opportunity_score=_safe_get(row, "opportunity_score"),
                analyst_score=row["analyst_score"],
                allocation_fit_score=_safe_get(row, "allocation_fit_score"),
                # Quality breakdown
                cagr_score=_safe_get(row, "cagr_score"),
                consistency_score=_safe_get(row, "consistency_score"),
                history_years=_safe_get(row, "history_years"),
                # Legacy fields
                technical_score=row["technical_score"],
                fundamental_score=row["fundamental_score"],
                # Common fields
                total_score=row["total_score"],
                volatility=row["volatility"],
                calculated_at=calculated_at,
            ))
        return scores

