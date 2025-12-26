"""Settings repository - key-value store for application settings."""

from datetime import datetime
from typing import Dict, Optional

from app.infrastructure.database import get_db_manager


class SettingsRepository:
    """Repository for application settings (key-value store)."""

    def __init__(self):
        self._db = get_db_manager().config

    async def get(self, key: str) -> Optional[str]:
        """Get a setting value by key."""
        row = await self._db.fetchone(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        return row["value"] if row else None

    async def set(self, key: str, value: str, description: str = None) -> None:
        """Set a setting value."""
        now = datetime.now().isoformat()

        async with self._db.transaction() as conn:
            if description:
                await conn.execute(
                    """
                    INSERT INTO settings (key, value, description, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        description = excluded.description,
                        updated_at = excluded.updated_at
                    """,
                    (key, value, description, now),
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (key, value, now),
                )

    async def get_all(self) -> Dict[str, str]:
        """Get all settings as a dictionary."""
        rows = await self._db.fetchall("SELECT key, value FROM settings")
        return {row["key"]: row["value"] for row in rows}

    async def get_float(self, key: str, default: float = 0.0) -> float:
        """Get a setting value as float."""
        value = await self.get(key)
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    async def set_float(self, key: str, value: float) -> None:
        """Set a setting value as float."""
        await self.set(key, str(value))

    async def get_int(self, key: str, default: int = 0) -> int:
        """Get a setting value as integer."""
        value = await self.get(key)
        if value is None:
            return default
        try:
            # Parse via float first to handle "12.0" strings from database
            return int(float(value))
        except (ValueError, TypeError):
            return default

    async def set_int(self, key: str, value: int) -> None:
        """Set a setting value as integer."""
        await self.set(key, str(value))

    async def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a setting value as boolean."""
        value = await self.get(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")

    async def set_bool(self, key: str, value: bool) -> None:
        """Set a setting value as boolean."""
        await self.set(key, "true" if value else "false")

    async def delete(self, key: str) -> None:
        """Delete a setting."""
        async with self._db.transaction() as conn:
            await conn.execute("DELETE FROM settings WHERE key = ?", (key,))
