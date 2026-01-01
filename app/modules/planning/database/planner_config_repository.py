"""Planner configuration repository - CRUD operations for planner_configs table."""

import uuid
from datetime import datetime
from typing import List, Optional

from app.core.database.manager import get_db_manager
from app.modules.planning.domain.planner_config import (
    PlannerConfig,
    PlannerConfigHistory,
)


class PlannerConfigRepository:
    """Repository for planner configuration CRUD operations.

    Manages named planner configurations stored in planner.db,
    including automatic version history/backup on updates.
    """

    def __init__(self):
        self._db_manager = None

    async def _get_db(self):
        """Get planner database connection."""
        if self._db_manager is None:
            self._db_manager = get_db_manager()
        return self._db_manager.planner

    async def get_all(self) -> List[PlannerConfig]:
        """Get all planner configurations."""
        db = await self._get_db()
        rows = await db.fetchall(
            """SELECT * FROM planner_configs
               ORDER BY name"""
        )
        return [self._row_to_config(row) for row in rows]

    async def get_by_id(self, config_id: str) -> Optional[PlannerConfig]:
        """Get planner configuration by ID."""
        db = await self._get_db()
        row = await db.fetchone(
            "SELECT * FROM planner_configs WHERE id = ?", (config_id,)
        )
        if not row:
            return None
        return self._row_to_config(row)

    async def get_by_bucket(self, bucket_id: str) -> Optional[PlannerConfig]:
        """Get planner configuration for a specific bucket."""
        db = await self._get_db()
        row = await db.fetchone(
            "SELECT * FROM planner_configs WHERE bucket_id = ?", (bucket_id,)
        )
        if not row:
            return None
        return self._row_to_config(row)

    async def create(
        self, name: str, toml_config: str, bucket_id: Optional[str] = None
    ) -> PlannerConfig:
        """Create a new planner configuration.

        Args:
            name: Human-readable name
            toml_config: TOML configuration string
            bucket_id: Associated bucket (None for templates)

        Returns:
            Newly created PlannerConfig
        """
        db = await self._get_db()
        now = datetime.now().isoformat()
        config_id = str(uuid.uuid4())

        config = PlannerConfig(
            id=config_id,
            name=name,
            toml_config=toml_config,
            bucket_id=bucket_id,
            created_at=now,
            updated_at=now,
        )

        await db.execute(
            """INSERT INTO planner_configs
               (id, name, toml_config, bucket_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                config.id,
                config.name,
                config.toml_config,
                config.bucket_id,
                config.created_at,
                config.updated_at,
            ),
        )
        await db.commit()

        return config

    async def update(
        self,
        config_id: str,
        name: Optional[str] = None,
        toml_config: Optional[str] = None,
        bucket_id: Optional[str] = None,
        create_backup: bool = True,
    ) -> Optional[PlannerConfig]:
        """Update a planner configuration.

        Automatically creates a backup in planner_config_history before updating.

        Args:
            config_id: ID of the configuration to update
            name: New name (if provided)
            toml_config: New TOML configuration (if provided)
            bucket_id: New bucket assignment (if provided, use empty string for None)
            create_backup: Whether to create backup (default True)

        Returns:
            Updated PlannerConfig or None if not found
        """
        db = await self._get_db()

        # Get current config
        current = await self.get_by_id(config_id)
        if not current:
            return None

        # Create backup in history table if requested
        if create_backup:
            await self._create_history_entry(current)

        # Prepare updates (Note: values can be str or None for nullable columns)
        updates: dict[str, str | None] = {"updated_at": datetime.now().isoformat()}
        if name is not None:
            updates["name"] = name
        if toml_config is not None:
            updates["toml_config"] = toml_config
        if bucket_id is not None:
            # Empty string means unassign (set to NULL)
            updates["bucket_id"] = bucket_id if bucket_id else None

        # Build dynamic UPDATE query with whitelisted columns
        ALLOWED_FIELDS = {"name", "toml_config", "bucket_id", "updated_at"}
        validated_updates = {k: v for k, v in updates.items() if k in ALLOWED_FIELDS}

        if not validated_updates:
            return await self.get_by_id(config_id)  # No valid fields to update

        set_clause = ", ".join(f"{k} = ?" for k in validated_updates.keys())
        values = list(validated_updates.values()) + [config_id]

        await db.execute(
            f"UPDATE planner_configs SET {set_clause} WHERE id = ?",
            values,
        )
        await db.commit()

        return await self.get_by_id(config_id)

    async def delete(self, config_id: str) -> bool:
        """Delete a planner configuration.

        Args:
            config_id: ID of the configuration to delete

        Returns:
            True if deleted, False if not found
        """
        db = await self._get_db()

        # Check if config exists
        config = await self.get_by_id(config_id)
        if not config:
            return False

        # Delete (CASCADE will handle history entries)
        await db.execute("DELETE FROM planner_configs WHERE id = ?", (config_id,))
        await db.commit()

        return True

    async def get_history(self, config_id: str) -> List[PlannerConfigHistory]:
        """Get version history for a planner configuration.

        Args:
            config_id: ID of the configuration

        Returns:
            List of historical versions, newest first
        """
        db = await self._get_db()
        rows = await db.fetchall(
            """SELECT * FROM planner_config_history
               WHERE planner_config_id = ?
               ORDER BY saved_at DESC""",
            (config_id,),
        )
        return [self._row_to_history(row) for row in rows]

    async def _create_history_entry(self, config: PlannerConfig) -> None:
        """Create a backup entry in history table.

        Args:
            config: The configuration to back up
        """
        db = await self._get_db()
        history_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        await db.execute(
            """INSERT INTO planner_config_history
               (id, planner_config_id, name, toml_config, saved_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                history_id,
                config.id,
                config.name,
                config.toml_config,
                now,
            ),
        )
        # Note: commit will happen in the calling update() transaction

    def _row_to_config(self, row) -> PlannerConfig:
        """Convert database row to PlannerConfig model."""
        return PlannerConfig(
            id=row["id"],
            name=row["name"],
            toml_config=row["toml_config"],
            bucket_id=row["bucket_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_history(self, row) -> PlannerConfigHistory:
        """Convert database row to PlannerConfigHistory model."""
        return PlannerConfigHistory(
            id=row["id"],
            planner_config_id=row["planner_config_id"],
            name=row["name"],
            toml_config=row["toml_config"],
            saved_at=row["saved_at"],
        )
