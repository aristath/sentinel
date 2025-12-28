"""Score repository - operations for scores table."""

from datetime import datetime
from typing import List, Optional

from app.domain.models import StockScore
from app.infrastructure.database import get_db_manager
from app.repositories.base import transaction_context


class ScoreRepository:
    """Repository for stock score operations."""

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
            self._db = get_db_manager().state

    async def get_by_symbol(self, symbol: str) -> Optional[StockScore]:
        """Get score by symbol."""
        row = await self._db.fetchone(
            "SELECT * FROM scores WHERE symbol = ?", (symbol.upper(),)
        )
        if not row:
            return None
        return self._row_to_score(row)

    async def get_all(self) -> List[StockScore]:
        """Get all scores."""
        rows = await self._db.fetchall("SELECT * FROM scores")
        return [self._row_to_score(row) for row in rows]

    async def get_top(self, limit: int = 10) -> List[StockScore]:
        """Get top scored stocks."""
        rows = await self._db.fetchall(
            """
            SELECT * FROM scores
            WHERE total_score IS NOT NULL
            ORDER BY total_score DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [self._row_to_score(row) for row in rows]

    async def upsert(self, score: StockScore) -> None:
        """Insert or update a score."""
        calculated_at = (
            score.calculated_at.isoformat()
            if isinstance(score.calculated_at, datetime)
            else score.calculated_at or datetime.now().isoformat()
        )

        async with transaction_context(self._db) as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO scores
                (symbol, quality_score, opportunity_score, analyst_score,
                 allocation_fit_score, cagr_score, consistency_score,
                 financial_strength_score, sharpe_score, drawdown_score,
                 dividend_bonus, rsi, ema_200, below_52w_high_pct,
                 total_score, sell_score, history_years, calculated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    score.symbol.upper(),
                    score.quality_score,
                    score.opportunity_score,
                    score.analyst_score,
                    score.allocation_fit_score,
                    score.cagr_score,
                    score.consistency_score,
                    score.financial_strength_score,
                    score.sharpe_score,
                    score.drawdown_score,
                    score.dividend_bonus,
                    score.rsi,
                    score.ema_200,
                    score.below_52w_high_pct,
                    score.total_score,
                    score.sell_score,
                    score.history_years,
                    calculated_at,
                ),
            )

    async def delete(self, symbol: str) -> None:
        """Delete score for a symbol."""
        async with transaction_context(self._db) as conn:
            await conn.execute("DELETE FROM scores WHERE symbol = ?", (symbol.upper(),))

    async def delete_all(self) -> None:
        """Delete all scores."""
        async with transaction_context(self._db) as conn:
            await conn.execute("DELETE FROM scores")

    async def get_recent_scores(
        self, symbol: str, months: float
    ) -> List[StockScore]:
        """
        Get recent scores for a symbol within the specified time window.

        Note: Currently, the scores table only stores the latest score per symbol.
        This method returns the current score if it's within the time window.
        For proper historical tracking, we would need a score_history table.

        Args:
            symbol: Stock symbol
            months: Number of months to look back

        Returns:
            List of StockScore objects (currently 0 or 1 score)
        """
        from datetime import datetime, timedelta

        cutoff_date = (datetime.now() - timedelta(days=months * 30)).isoformat()

        row = await self._db.fetchone(
            """
            SELECT * FROM scores
            WHERE symbol = ? AND calculated_at >= ?
            ORDER BY calculated_at DESC
            """,
            (symbol.upper(), cutoff_date),
        )

        if row:
            return [self._row_to_score(row)]
        return []

    def _row_to_score(self, row) -> StockScore:
        """Convert database row to StockScore model."""
        calculated_at = None
        if row["calculated_at"]:
            try:
                calculated_at = datetime.fromisoformat(str(row["calculated_at"]))
            except (ValueError, TypeError):
                pass

        def safe_get(key, default=None):
            try:
                return row[key]
            except (KeyError, IndexError):
                return default

        return StockScore(
            symbol=row["symbol"],
            quality_score=safe_get("quality_score"),
            opportunity_score=safe_get("opportunity_score"),
            analyst_score=safe_get("analyst_score"),
            allocation_fit_score=safe_get("allocation_fit_score"),
            cagr_score=safe_get("cagr_score"),
            consistency_score=safe_get("consistency_score"),
            financial_strength_score=safe_get("financial_strength_score"),
            sharpe_score=safe_get("sharpe_score"),
            drawdown_score=safe_get("drawdown_score"),
            dividend_bonus=safe_get("dividend_bonus"),
            rsi=safe_get("rsi"),
            ema_200=safe_get("ema_200"),
            below_52w_high_pct=safe_get("below_52w_high_pct"),
            total_score=safe_get("total_score"),
            sell_score=safe_get("sell_score"),
            history_years=safe_get("history_years"),
            volatility=safe_get("volatility"),
            calculated_at=calculated_at,
        )
