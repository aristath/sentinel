"""Cash flow repository - operations for cash_flows table (ledger)."""

import json
from datetime import datetime
from typing import List, Optional

from app.domain.models import CashFlow
from app.infrastructure.database import get_db_manager


class CashFlowRepository:
    """Repository for cash flow operations (append-only ledger)."""

    def __init__(self):
        self._db = get_db_manager().ledger

    async def create(self, cash_flow: CashFlow) -> CashFlow:
        """Create a new cash flow record."""
        now = datetime.now().isoformat()

        async with self._db.transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO cash_flows
                (transaction_id, type_doc_id, transaction_type, date,
                 amount, currency, amount_eur, status, status_c,
                 description, params_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cash_flow.transaction_id,
                    cash_flow.type_doc_id,
                    cash_flow.transaction_type,
                    cash_flow.date,
                    cash_flow.amount,
                    cash_flow.currency,
                    cash_flow.amount_eur,
                    cash_flow.status,
                    cash_flow.status_c,
                    cash_flow.description,
                    cash_flow.params_json,
                    now,
                ),
            )
            cash_flow.id = cursor.lastrowid
            cash_flow.created_at = now

        return cash_flow

    async def get_by_transaction_id(self, transaction_id: str) -> Optional[CashFlow]:
        """Get cash flow by transaction ID."""
        row = await self._db.fetchone(
            "SELECT * FROM cash_flows WHERE transaction_id = ?", (transaction_id,)
        )
        if not row:
            return None
        return self._row_to_cash_flow(row)

    async def exists(self, transaction_id: str) -> bool:
        """Check if cash flow with transaction_id already exists."""
        row = await self._db.fetchone(
            "SELECT 1 FROM cash_flows WHERE transaction_id = ?", (transaction_id,)
        )
        return row is not None

    async def get_all(self, limit: Optional[int] = None) -> List[CashFlow]:
        """Get all cash flows, optionally limited."""
        if limit:
            rows = await self._db.fetchall(
                "SELECT * FROM cash_flows ORDER BY date DESC LIMIT ?", (limit,)
            )
        else:
            rows = await self._db.fetchall(
                "SELECT * FROM cash_flows ORDER BY date DESC"
            )
        return [self._row_to_cash_flow(row) for row in rows]

    async def get_by_date_range(self, start_date: str, end_date: str) -> List[CashFlow]:
        """Get cash flows within a date range."""
        rows = await self._db.fetchall(
            """
            SELECT * FROM cash_flows
            WHERE date >= ? AND date <= ?
            ORDER BY date DESC
            """,
            (start_date, end_date),
        )
        return [self._row_to_cash_flow(row) for row in rows]

    async def get_by_type(self, transaction_type: str) -> List[CashFlow]:
        """Get cash flows by transaction type."""
        rows = await self._db.fetchall(
            """
            SELECT * FROM cash_flows
            WHERE transaction_type = ?
            ORDER BY date DESC
            """,
            (transaction_type,),
        )
        return [self._row_to_cash_flow(row) for row in rows]

    async def sync_from_api(self, transactions: List[dict]) -> int:
        """
        Sync transactions from API response.

        Upserts transactions (inserts new ones, skips existing ones).

        Returns:
            Number of new transactions synced
        """
        now = datetime.now().isoformat()
        synced = 0

        for tx in transactions:
            transaction_id = str(tx.get("id", ""))
            if not transaction_id:
                continue

            # Skip if already exists
            if await self.exists(transaction_id):
                continue

            # Parse transaction data
            cash_flow = CashFlow(
                transaction_id=transaction_id,
                type_doc_id=tx.get("type_doc_id", 0),
                transaction_type=tx.get("type_doc"),
                date=tx.get("dt", ""),
                amount=float(tx.get("sm", 0)),
                currency=tx.get("curr", "EUR"),
                amount_eur=float(tx.get("sm_eur", tx.get("sm", 0))),
                status=tx.get("status"),
                status_c=tx.get("status_c"),
                description=tx.get("description"),
                params_json=json.dumps(tx.get("params")) if tx.get("params") else None,
                created_at=now,
            )

            await self.create(cash_flow)
            synced += 1

        return synced

    async def get_total_deposits(self) -> float:
        """Get total deposits in EUR."""
        row = await self._db.fetchone(
            """
            SELECT COALESCE(SUM(amount_eur), 0) as total
            FROM cash_flows
            WHERE transaction_type IN ('DEPOSIT', 'Deposit', 'deposit')
            """
        )
        return row["total"] if row else 0.0

    async def get_total_withdrawals(self) -> float:
        """Get total withdrawals in EUR."""
        row = await self._db.fetchone(
            """
            SELECT COALESCE(SUM(ABS(amount_eur)), 0) as total
            FROM cash_flows
            WHERE transaction_type IN ('WITHDRAWAL', 'Withdrawal', 'withdrawal')
            """
        )
        return row["total"] if row else 0.0

    async def get_cash_balance_history(
        self, start_date: str, end_date: str, initial_cash: float = 0.0
    ) -> List[dict]:
        """
        Get cash balance history over time from cash flows.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            initial_cash: Starting cash balance (default 0.0)

        Returns:
            List of dicts with keys: date, cash_balance
        """
        # Get all cash flows in date range
        rows = await self._db.fetchall(
            """
            SELECT date, amount_eur, transaction_type
            FROM cash_flows
            WHERE date >= ? AND date <= ?
            ORDER BY date ASC
            """,
            (start_date, end_date),
        )

        # Group by date and calculate net cash flow per day
        cash_flows_by_date = {}  # {date: net_amount}

        for row in rows:
            date = row["date"]
            amount_eur = row["amount_eur"] or 0.0
            tx_type = (row["transaction_type"] or "").upper()

            if date not in cash_flows_by_date:
                cash_flows_by_date[date] = 0.0

            # Deposits increase cash, withdrawals decrease cash
            if "DEPOSIT" in tx_type:
                cash_flows_by_date[date] += amount_eur
            elif "WITHDRAWAL" in tx_type:
                cash_flows_by_date[date] -= abs(amount_eur)
            # Dividends increase cash
            elif "DIVIDEND" in tx_type:
                cash_flows_by_date[date] += amount_eur

        # Calculate cumulative cash balance
        result = []
        current_cash = initial_cash

        # Get all unique dates sorted
        all_dates = sorted(cash_flows_by_date.keys())

        for date in all_dates:
            current_cash += cash_flows_by_date[date]
            result.append({"date": date, "cash_balance": current_cash})

        return result

    def _row_to_cash_flow(self, row) -> CashFlow:
        """Convert database row to CashFlow model."""
        return CashFlow(
            id=row["id"],
            transaction_id=row["transaction_id"],
            type_doc_id=row["type_doc_id"],
            transaction_type=row["transaction_type"],
            date=row["date"],
            amount=row["amount"],
            currency=row["currency"],
            amount_eur=row["amount_eur"],
            status=row["status"],
            status_c=row["status_c"],
            description=row["description"],
            params_json=row["params_json"],
            created_at=row["created_at"],
        )
