"""Allocation repository - operations for allocation_targets table."""

from datetime import datetime
from typing import Dict, List

from app.domain.models import AllocationTarget
from app.infrastructure.database import get_db_manager
from app.repositories.base import transaction_context


class AllocationRepository:
    """Repository for allocation target operations."""

    def __init__(self, db=None):
        """Initialize repository.

        Args:
            db: Optional database connection for testing. If None, uses get_db_manager().config
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
            self._db = get_db_manager().config

    async def get_all(self) -> Dict[str, float]:
        """Get all allocation targets as dict with key 'type:name'."""
        rows = await self._db.fetchall(
            "SELECT type, name, target_pct FROM allocation_targets"
        )
        return {f"{row['type']}:{row['name']}": row["target_pct"] for row in rows}

    async def get_by_type(self, target_type: str) -> List[AllocationTarget]:
        """Get allocation targets by type (geography or industry)."""
        rows = await self._db.fetchall(
            "SELECT * FROM allocation_targets WHERE type = ?", (target_type,)
        )
        return [
            AllocationTarget(
                type=row["type"],
                name=row["name"],
                target_pct=row["target_pct"],
            )
            for row in rows
        ]

    async def get_geography_targets(self) -> Dict[str, float]:
        """Get geography allocation targets."""
        targets = await self.get_by_type("geography")
        return {t.name: t.target_pct for t in targets}

    async def get_industry_targets(self) -> Dict[str, float]:
        """Get industry allocation targets."""
        targets = await self.get_by_type("industry")
        return {t.name: t.target_pct for t in targets}

    async def upsert(self, target: AllocationTarget) -> None:
        """Insert or update an allocation target."""
        now = datetime.now().isoformat()

        async with transaction_context(self._db) as conn:
            await conn.execute(
                """
                INSERT INTO allocation_targets (type, name, target_pct, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(type, name) DO UPDATE SET
                    target_pct = excluded.target_pct,
                    updated_at = excluded.updated_at
                """,
                (target.type, target.name, target.target_pct, now, now),
            )

    async def delete(self, target_type: str, name: str) -> None:
        """Delete an allocation target."""
        async with transaction_context(self._db) as conn:
            await conn.execute(
                "DELETE FROM allocation_targets WHERE type = ? AND name = ?",
                (target_type, name),
            )
