"""SQLite implementation of AllocationRepository."""

import aiosqlite
from typing import Dict, List

from app.domain.repositories.allocation_repository import (
    AllocationRepository,
    AllocationTarget,
)


class SQLiteAllocationRepository(AllocationRepository):
    """SQLite implementation of AllocationRepository."""

    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def get_all(self) -> Dict[str, float]:
        """Get all allocation targets as dict with key 'type:name'."""
        cursor = await self.db.execute(
            "SELECT type, name, target_pct FROM allocation_targets"
        )
        rows = await cursor.fetchall()
        targets = {}
        for row in rows:
            key = f"{row[0]}:{row[1]}"
            targets[key] = row[2]
        return targets

    async def get_by_type(self, target_type: str) -> List[AllocationTarget]:
        """Get allocation targets by type (geography or industry)."""
        cursor = await self.db.execute(
            "SELECT type, name, target_pct FROM allocation_targets WHERE type = ?",
            (target_type,)
        )
        rows = await cursor.fetchall()
        return [
            AllocationTarget(
                type=row[0],
                name=row[1],
                target_pct=row[2],
            )
            for row in rows
        ]

    async def upsert(self, target: AllocationTarget, auto_commit: bool = True) -> None:
        """
        Insert or update an allocation target.
        
        Validates that target_pct is between 0 and 1 (0% to 100%).
        Note: It's recommended that targets of the same type sum to approximately 1.0 (100%),
        but this is not enforced here to allow flexibility.
        
        Args:
            target: Allocation target to upsert
            auto_commit: If True, commit immediately. If False, caller manages transaction.
        """
        # Validate target percentage
        if target.target_pct < 0 or target.target_pct > 1:
            raise ValueError(
                f"Allocation target percentage must be between 0 and 1 (0% to 100%), "
                f"got {target.target_pct} for {target.type}:{target.name}"
            )
        
        await self.db.execute(
            """
            INSERT OR REPLACE INTO allocation_targets (type, name, target_pct)
            VALUES (?, ?, ?)
            """,
            (target.type, target.name, target.target_pct),
        )
        if auto_commit:
            await self.db.commit()

