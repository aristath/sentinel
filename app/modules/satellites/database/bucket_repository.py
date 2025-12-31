"""Bucket repository - operations for buckets table (satellites.db)."""

from datetime import datetime
from typing import List, Optional

from app.core.database.manager import get_db_manager
from app.modules.satellites.domain.enums import BucketStatus, BucketType
from app.modules.satellites.domain.models import Bucket, SatelliteSettings


class BucketRepository:
    """Repository for bucket CRUD operations.

    Manages both core and satellite bucket definitions,
    including their status and configuration.
    """

    def __init__(self):
        self._db = get_db_manager().satellites

    async def get_by_id(self, bucket_id: str) -> Optional[Bucket]:
        """Get bucket by ID."""
        row = await self._db.fetchone(
            "SELECT * FROM buckets WHERE id = ?", (bucket_id,)
        )
        if not row:
            return None
        return self._row_to_bucket(row)

    async def get_all(self) -> List[Bucket]:
        """Get all buckets."""
        rows = await self._db.fetchall(
            "SELECT * FROM buckets ORDER BY type, created_at"
        )
        return [self._row_to_bucket(row) for row in rows]

    async def get_active(self) -> List[Bucket]:
        """Get all active buckets (not retired or paused)."""
        rows = await self._db.fetchall(
            """SELECT * FROM buckets
               WHERE status NOT IN ('retired', 'paused')
               ORDER BY type, created_at"""
        )
        return [self._row_to_bucket(row) for row in rows]

    async def get_by_type(self, bucket_type: BucketType) -> List[Bucket]:
        """Get all buckets of a specific type."""
        rows = await self._db.fetchall(
            "SELECT * FROM buckets WHERE type = ? ORDER BY created_at",
            (bucket_type.value,),
        )
        return [self._row_to_bucket(row) for row in rows]

    async def get_by_status(self, status: BucketStatus) -> List[Bucket]:
        """Get all buckets with a specific status."""
        rows = await self._db.fetchall(
            "SELECT * FROM buckets WHERE status = ? ORDER BY type, created_at",
            (status.value,),
        )
        return [self._row_to_bucket(row) for row in rows]

    async def get_satellites(self) -> List[Bucket]:
        """Get all satellite buckets (excluding core)."""
        return await self.get_by_type(BucketType.SATELLITE)

    async def get_core(self) -> Optional[Bucket]:
        """Get the core bucket."""
        return await self.get_by_id("core")

    async def create(self, bucket: Bucket) -> Bucket:
        """Create a new bucket."""
        now = datetime.now().isoformat()
        bucket.created_at = now
        bucket.updated_at = now

        async with self._db.transaction() as conn:
            await conn.execute(
                """INSERT INTO buckets
                   (id, name, type, notes, target_pct, min_pct, max_pct,
                    consecutive_losses, max_consecutive_losses, high_water_mark,
                    high_water_mark_date, loss_streak_paused_at, status,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    bucket.id,
                    bucket.name,
                    bucket.type.value,
                    bucket.notes,
                    bucket.target_pct,
                    bucket.min_pct,
                    bucket.max_pct,
                    bucket.consecutive_losses,
                    bucket.max_consecutive_losses,
                    bucket.high_water_mark,
                    bucket.high_water_mark_date,
                    bucket.loss_streak_paused_at,
                    bucket.status.value,
                    bucket.created_at,
                    bucket.updated_at,
                ),
            )

        return bucket

    async def update(self, bucket_id: str, **updates) -> Optional[Bucket]:
        """Update bucket fields.

        Args:
            bucket_id: ID of the bucket to update
            **updates: Fields to update (e.g., name="New Name", status="paused")

        Returns:
            Updated bucket or None if not found
        """
        if not updates:
            return await self.get_by_id(bucket_id)

        # Add updated_at timestamp
        updates["updated_at"] = datetime.now().isoformat()

        # Whitelist allowed columns to prevent SQL injection
        ALLOWED_COLUMNS = {
            "name",
            "notes",
            "description",
            "type",
            "status",
            "target_allocation_pct",
            "high_water_mark",
            "high_water_mark_date",
            "consecutive_losses",
            "max_consecutive_losses",
        }

        # Validate all column names
        invalid_columns = set(updates.keys()) - ALLOWED_COLUMNS
        if invalid_columns:
            raise ValueError(
                f"Invalid column names in update: {', '.join(invalid_columns)}"
            )

        # Convert enum values to strings
        if "type" in updates and isinstance(updates["type"], BucketType):
            updates["type"] = updates["type"].value
        if "status" in updates and isinstance(updates["status"], BucketStatus):
            updates["status"] = updates["status"].value

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [bucket_id]

        await self._db.execute(
            f"UPDATE buckets SET {set_clause} WHERE id = ?",
            values,
        )
        await self._db.commit()

        return await self.get_by_id(bucket_id)

    async def update_status(
        self, bucket_id: str, status: BucketStatus
    ) -> Optional[Bucket]:
        """Update bucket status."""
        return await self.update(bucket_id, status=status)

    async def increment_consecutive_losses(self, bucket_id: str) -> int:
        """Increment consecutive losses counter.

        Returns:
            New count of consecutive losses
        """
        await self._db.execute(
            """UPDATE buckets
               SET consecutive_losses = consecutive_losses + 1,
                   updated_at = ?
               WHERE id = ?""",
            (datetime.now().isoformat(), bucket_id),
        )
        await self._db.commit()

        row = await self._db.fetchone(
            "SELECT consecutive_losses FROM buckets WHERE id = ?", (bucket_id,)
        )
        return row["consecutive_losses"] if row else 0

    async def reset_consecutive_losses(self, bucket_id: str) -> None:
        """Reset consecutive losses counter to 0."""
        await self._db.execute(
            """UPDATE buckets
               SET consecutive_losses = 0,
                   loss_streak_paused_at = NULL,
                   updated_at = ?
               WHERE id = ?""",
            (datetime.now().isoformat(), bucket_id),
        )
        await self._db.commit()

    async def update_high_water_mark(
        self, bucket_id: str, value: float
    ) -> Optional[Bucket]:
        """Update high water mark if new value is higher."""
        now = datetime.now().isoformat()

        await self._db.execute(
            """UPDATE buckets
               SET high_water_mark = ?,
                   high_water_mark_date = ?,
                   updated_at = ?
               WHERE id = ? AND (high_water_mark IS NULL OR high_water_mark < ?)""",
            (value, now, now, bucket_id, value),
        )
        await self._db.commit()

        return await self.get_by_id(bucket_id)

    async def delete(self, bucket_id: str) -> bool:
        """Delete a bucket (typically only for satellites).

        Note: Core bucket should never be deleted.

        Returns:
            True if bucket was deleted, False if not found
        """
        if bucket_id == "core":
            raise ValueError("Cannot delete core bucket")

        result = await self._db.execute(
            "DELETE FROM buckets WHERE id = ?", (bucket_id,)
        )
        await self._db.commit()
        return result.rowcount > 0

    # Satellite settings methods

    async def get_settings(self, satellite_id: str) -> Optional[SatelliteSettings]:
        """Get settings for a satellite."""
        row = await self._db.fetchone(
            "SELECT * FROM satellite_settings WHERE satellite_id = ?",
            (satellite_id,),
        )
        if not row:
            return None
        return self._row_to_settings(row)

    async def save_settings(self, settings: SatelliteSettings) -> SatelliteSettings:
        """Save or update satellite settings."""
        settings.validate()

        await self._db.execute(
            """INSERT OR REPLACE INTO satellite_settings
               (satellite_id, preset, risk_appetite, hold_duration, entry_style,
                position_spread, profit_taking, trailing_stops, follow_regime,
                auto_harvest, pause_high_volatility, dividend_handling)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                settings.satellite_id,
                settings.preset,
                settings.risk_appetite,
                settings.hold_duration,
                settings.entry_style,
                settings.position_spread,
                settings.profit_taking,
                1 if settings.trailing_stops else 0,
                1 if settings.follow_regime else 0,
                1 if settings.auto_harvest else 0,
                1 if settings.pause_high_volatility else 0,
                settings.dividend_handling,
            ),
        )
        await self._db.commit()

        return settings

    async def delete_settings(self, satellite_id: str) -> bool:
        """Delete satellite settings."""
        result = await self._db.execute(
            "DELETE FROM satellite_settings WHERE satellite_id = ?",
            (satellite_id,),
        )
        await self._db.commit()
        return result.rowcount > 0

    # Helper methods

    def _row_to_bucket(self, row) -> Bucket:
        """Convert database row to Bucket model."""
        return Bucket(
            id=row["id"],
            name=row["name"],
            type=BucketType(row["type"]),
            notes=row["notes"],
            target_pct=row["target_pct"],
            min_pct=row["min_pct"],
            max_pct=row["max_pct"],
            consecutive_losses=row["consecutive_losses"] or 0,
            max_consecutive_losses=row["max_consecutive_losses"] or 5,
            high_water_mark=row["high_water_mark"] or 0.0,
            high_water_mark_date=row["high_water_mark_date"],
            loss_streak_paused_at=row["loss_streak_paused_at"],
            status=BucketStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_settings(self, row) -> SatelliteSettings:
        """Convert database row to SatelliteSettings model."""
        return SatelliteSettings(
            satellite_id=row["satellite_id"],
            preset=row["preset"],
            risk_appetite=row["risk_appetite"] or 0.5,
            hold_duration=row["hold_duration"] or 0.5,
            entry_style=row["entry_style"] or 0.5,
            position_spread=row["position_spread"] or 0.5,
            profit_taking=row["profit_taking"] or 0.5,
            trailing_stops=bool(row["trailing_stops"]),
            follow_regime=bool(row["follow_regime"]),
            auto_harvest=bool(row["auto_harvest"]),
            pause_high_volatility=bool(row["pause_high_volatility"]),
            dividend_handling=row["dividend_handling"] or "reinvest_same",
        )
