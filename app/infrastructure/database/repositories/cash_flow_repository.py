"""SQLite implementation of CashFlowRepository."""

import logging
import json
import aiosqlite
from typing import Optional, List
from datetime import datetime

from app.domain.repositories.cash_flow_repository import CashFlowRepository
from app.domain.models.cash_flow import CashFlow

logger = logging.getLogger(__name__)


class SQLiteCashFlowRepository(CashFlowRepository):
    """SQLite implementation of CashFlowRepository."""

    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def create(self, cash_flow: CashFlow) -> CashFlow:
        """Create a new cash flow record."""
        now = datetime.now().isoformat()
        
        cursor = await self.db.execute(
            """
            INSERT INTO cash_flows (
                transaction_id, type_doc_id, transaction_type, date,
                amount, currency, amount_eur, status, status_c,
                description, params_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                now,
            ),
        )
        await self.db.commit()
        
        # Get the created record
        cash_flow.id = cursor.lastrowid
        cash_flow.created_at = now
        cash_flow.updated_at = now
        return cash_flow

    async def get_by_transaction_id(self, transaction_id: str) -> Optional[CashFlow]:
        """Get cash flow by transaction ID."""
        cursor = await self.db.execute(
            "SELECT * FROM cash_flows WHERE transaction_id = ?",
            (transaction_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_cash_flow(row)

    async def get_all(self, limit: Optional[int] = None) -> List[CashFlow]:
        """Get all cash flows, optionally limited."""
        if limit:
            cursor = await self.db.execute(
                "SELECT * FROM cash_flows ORDER BY date DESC, id DESC LIMIT ?",
                (limit,)
            )
        else:
            cursor = await self.db.execute(
                "SELECT * FROM cash_flows ORDER BY date DESC, id DESC"
            )
        rows = await cursor.fetchall()
        return [self._row_to_cash_flow(row) for row in rows]

    async def get_by_date_range(self, start_date: str, end_date: str) -> List[CashFlow]:
        """Get cash flows within a date range."""
        cursor = await self.db.execute(
            """
            SELECT * FROM cash_flows
            WHERE date >= ? AND date <= ?
            ORDER BY date DESC, id DESC
            """,
            (start_date, end_date)
        )
        rows = await cursor.fetchall()
        return [self._row_to_cash_flow(row) for row in rows]

    async def get_by_type(self, transaction_type: str) -> List[CashFlow]:
        """Get cash flows by transaction type."""
        cursor = await self.db.execute(
            "SELECT * FROM cash_flows WHERE transaction_type = ? ORDER BY date DESC, id DESC",
            (transaction_type,)
        )
        rows = await cursor.fetchall()
        return [self._row_to_cash_flow(row) for row in rows]

    async def sync_from_api(self, transactions: List[dict]) -> int:
        """
        Sync transactions from API response.
        
        Upserts transactions (inserts new ones, updates existing ones based on transaction_id).
        """
        now = datetime.now().isoformat()
        synced_count = 0

        for tx in transactions:
            try:
                # Convert params dict to JSON string
                params_json = json.dumps(tx.get("params", {}))
                
                cash_flow = CashFlow(
                    transaction_id=tx["transaction_id"],
                    type_doc_id=tx["type_doc_id"],
                    transaction_type=tx.get("transaction_type"),
                    date=tx["date"],
                    amount=tx["amount"],
                    currency=tx["currency"],
                    amount_eur=tx["amount_eur"],
                    status=tx.get("status"),
                    status_c=tx.get("status_c"),
                    description=tx.get("description"),
                    params_json=params_json,
                    created_at=now,
                    updated_at=now,
                )

                # Check if exists to preserve created_at
                existing = await self.get_by_transaction_id(cash_flow.transaction_id)
                
                if existing:
                    # Update existing, preserve original created_at
                    await self.db.execute(
                        """
                        UPDATE cash_flows SET
                            type_doc_id = ?,
                            transaction_type = ?,
                            date = ?,
                            amount = ?,
                            currency = ?,
                            amount_eur = ?,
                            status = ?,
                            status_c = ?,
                            description = ?,
                            params_json = ?,
                            updated_at = ?
                        WHERE transaction_id = ?
                        """,
                        (
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
                            cash_flow.transaction_id,
                        ),
                    )
                else:
                    # Insert new
                    await self.db.execute(
                        """
                        INSERT INTO cash_flows (
                            transaction_id, type_doc_id, transaction_type, date,
                            amount, currency, amount_eur, status, status_c,
                            description, params_json, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                            now,
                        ),
                    )
                
                synced_count += 1
            except Exception as e:
                logger.error(f"Failed to sync transaction {tx.get('transaction_id', 'unknown')}: {e}")
                continue

        await self.db.commit()
        return synced_count

    def _row_to_cash_flow(self, row: aiosqlite.Row) -> CashFlow:
        """Convert database row to CashFlow domain model."""
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
            updated_at=row["updated_at"],
        )
