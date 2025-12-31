"""Dividend repository - operations for dividend_history table (dividends.db)."""

from datetime import datetime
from typing import Dict, List, Optional

from app.core.database.manager import get_db_manager
from app.domain.models import DividendRecord


class DividendRepository:
    """Repository for dividend history operations.

    Tracks dividend payments, DRIP (dividend reinvestment) status,
    and pending bonuses for securities where reinvestment wasn't possible.
    """

    def __init__(self):
        self._db = get_db_manager().dividends

    async def create(self, dividend: DividendRecord) -> DividendRecord:
        """Create a new dividend record."""
        now = datetime.now().isoformat()

        async with self._db.transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO dividend_history
                (symbol, cash_flow_id, amount, currency, amount_eur, payment_date,
                 reinvested, reinvested_at, reinvested_quantity, pending_bonus,
                 bonus_cleared, cleared_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dividend.symbol,
                    dividend.cash_flow_id,
                    dividend.amount,
                    dividend.currency,
                    dividend.amount_eur,
                    dividend.payment_date,
                    1 if dividend.reinvested else 0,
                    dividend.reinvested_at,
                    dividend.reinvested_quantity,
                    dividend.pending_bonus,
                    1 if dividend.bonus_cleared else 0,
                    dividend.cleared_at,
                    now,
                ),
            )
            dividend.id = cursor.lastrowid
            dividend.created_at = now

        return dividend

    async def get_by_id(self, dividend_id: int) -> Optional[DividendRecord]:
        """Get dividend record by ID."""
        row = await self._db.fetchone(
            "SELECT * FROM dividend_history WHERE id = ?", (dividend_id,)
        )
        if not row:
            return None
        return self._row_to_dividend(row)

    async def get_by_cash_flow_id(self, cash_flow_id: int) -> Optional[DividendRecord]:
        """Get dividend record linked to a cash flow."""
        row = await self._db.fetchone(
            "SELECT * FROM dividend_history WHERE cash_flow_id = ?", (cash_flow_id,)
        )
        if not row:
            return None
        return self._row_to_dividend(row)

    async def exists_for_cash_flow(self, cash_flow_id: int) -> bool:
        """Check if a dividend record already exists for a cash flow."""
        row = await self._db.fetchone(
            "SELECT 1 FROM dividend_history WHERE cash_flow_id = ?", (cash_flow_id,)
        )
        return row is not None

    async def get_by_symbol(self, symbol: str) -> List[DividendRecord]:
        """Get all dividend records for a symbol."""
        rows = await self._db.fetchall(
            "SELECT * FROM dividend_history WHERE symbol = ? ORDER BY payment_date DESC",
            (symbol.upper(),),
        )
        return [self._row_to_dividend(row) for row in rows]

    async def get_by_isin(self, isin: str) -> List[DividendRecord]:
        """Get all dividend records for an ISIN."""
        rows = await self._db.fetchall(
            "SELECT * FROM dividend_history WHERE isin = ? ORDER BY payment_date DESC",
            (isin.upper(),),
        )
        return [self._row_to_dividend(row) for row in rows]

    async def get_by_identifier(self, identifier: str) -> List[DividendRecord]:
        """Get dividend records by symbol or ISIN."""
        identifier = identifier.strip().upper()

        # Check if it looks like an ISIN (12 chars, country code + alphanumeric)
        if len(identifier) == 12 and identifier[:2].isalpha():
            records = await self.get_by_isin(identifier)
            if records:
                return records

        # Try symbol lookup
        return await self.get_by_symbol(identifier)

    async def get_all(self, limit: Optional[int] = None) -> List[DividendRecord]:
        """Get all dividend records, optionally limited."""
        if limit:
            rows = await self._db.fetchall(
                "SELECT * FROM dividend_history ORDER BY payment_date DESC LIMIT ?",
                (limit,),
            )
        else:
            rows = await self._db.fetchall(
                "SELECT * FROM dividend_history ORDER BY payment_date DESC"
            )
        return [self._row_to_dividend(row) for row in rows]

    async def get_pending_bonuses(self) -> Dict[str, float]:
        """
        Get all pending dividend bonuses by symbol.

        Returns a dict mapping symbol -> total pending bonus.
        Only includes records where bonus_cleared = 0 and pending_bonus > 0.
        """
        rows = await self._db.fetchall(
            """
            SELECT symbol, SUM(pending_bonus) as total_bonus
            FROM dividend_history
            WHERE bonus_cleared = 0 AND pending_bonus > 0
            GROUP BY symbol
            """
        )
        return {row["symbol"]: row["total_bonus"] for row in rows}

    async def get_pending_bonus(self, symbol: str) -> float:
        """
        Get pending dividend bonus for a specific symbol.

        Returns the sum of all unclaimed pending bonuses.
        """
        row = await self._db.fetchone(
            """
            SELECT COALESCE(SUM(pending_bonus), 0) as total
            FROM dividend_history
            WHERE symbol = ? AND bonus_cleared = 0 AND pending_bonus > 0
            """,
            (symbol.upper(),),
        )
        return row["total"] if row else 0.0

    async def mark_reinvested(
        self,
        dividend_id: int,
        quantity: int,
    ) -> None:
        """Mark a dividend as reinvested (DRIP executed)."""
        now = datetime.now().isoformat()
        await self._db.execute(
            """
            UPDATE dividend_history
            SET reinvested = 1,
                reinvested_at = ?,
                reinvested_quantity = ?,
                pending_bonus = 0
            WHERE id = ?
            """,
            (now, quantity, dividend_id),
        )
        await self._db.commit()

    async def set_pending_bonus(
        self,
        dividend_id: int,
        bonus: float,
    ) -> None:
        """Set pending bonus for a dividend that couldn't be reinvested."""
        await self._db.execute(
            """
            UPDATE dividend_history
            SET pending_bonus = ?
            WHERE id = ?
            """,
            (bonus, dividend_id),
        )
        await self._db.commit()

    async def clear_bonus(self, symbol: str) -> int:
        """
        Clear pending bonuses for a symbol (after security is bought).

        Called when a security is purchased to consume the pending dividend bonus.

        Returns:
            Number of records updated.
        """
        now = datetime.now().isoformat()
        cursor = await self._db.execute(
            """
            UPDATE dividend_history
            SET bonus_cleared = 1, cleared_at = ?, pending_bonus = 0
            WHERE symbol = ? AND bonus_cleared = 0 AND pending_bonus > 0
            """,
            (now, symbol.upper()),
        )
        await self._db.commit()
        return cursor.rowcount

    async def get_unreinvested_dividends(
        self,
        min_amount_eur: float = 0.0,
    ) -> List[DividendRecord]:
        """
        Get dividends that haven't been reinvested yet.

        Args:
            min_amount_eur: Minimum amount to consider for reinvestment

        Returns:
            List of dividend records eligible for DRIP
        """
        rows = await self._db.fetchall(
            """
            SELECT * FROM dividend_history
            WHERE reinvested = 0 AND amount_eur >= ?
            ORDER BY payment_date ASC
            """,
            (min_amount_eur,),
        )
        return [self._row_to_dividend(row) for row in rows]

    async def get_total_dividends_by_symbol(self) -> Dict[str, float]:
        """Get total dividends received per symbol (in EUR)."""
        rows = await self._db.fetchall(
            """
            SELECT symbol, SUM(amount_eur) as total
            FROM dividend_history
            GROUP BY symbol
            ORDER BY total DESC
            """
        )
        return {row["symbol"]: row["total"] for row in rows}

    async def get_total_reinvested(self) -> float:
        """Get total amount of dividends that were reinvested (in EUR)."""
        row = await self._db.fetchone(
            """
            SELECT COALESCE(SUM(amount_eur), 0) as total
            FROM dividend_history
            WHERE reinvested = 1
            """
        )
        return row["total"] if row else 0.0

    async def get_reinvestment_rate(self) -> float:
        """
        Get dividend reinvestment rate (0.0 to 1.0).

        Returns the fraction of total dividends that were reinvested.
        """
        row = await self._db.fetchone(
            """
            SELECT
                COALESCE(SUM(CASE WHEN reinvested = 1 THEN amount_eur ELSE 0 END), 0) as reinvested,
                COALESCE(SUM(amount_eur), 0) as total
            FROM dividend_history
            """
        )
        if not row or row["total"] == 0:
            return 0.0
        return row["reinvested"] / row["total"]

    def _row_to_dividend(self, row) -> DividendRecord:
        """Convert database row to DividendRecord model."""
        keys = row.keys()
        return DividendRecord(
            id=row["id"],
            symbol=row["symbol"],
            isin=row["isin"] if "isin" in keys else None,
            cash_flow_id=row["cash_flow_id"],
            amount=row["amount"],
            currency=row["currency"],
            amount_eur=row["amount_eur"],
            payment_date=row["payment_date"],
            reinvested=bool(row["reinvested"]),
            reinvested_at=row["reinvested_at"],
            reinvested_quantity=row["reinvested_quantity"],
            pending_bonus=row["pending_bonus"],
            bonus_cleared=bool(row["bonus_cleared"]),
            cleared_at=row["cleared_at"],
            created_at=row["created_at"],
        )
