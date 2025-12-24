"""SQLite implementation of SettingsRepository."""

from typing import Optional
import aiosqlite
from app.domain.repositories.settings_repository import SettingsRepository


class SQLiteSettingsRepository(SettingsRepository):
    """SQLite implementation of SettingsRepository."""

    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def get(self, key: str) -> Optional[str]:
        """Get a setting value by key."""
        cursor = await self._db.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def set(self, key: str, value: str) -> None:
        """Set a setting value."""
        await self._db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        await self._db.commit()

    async def get_float(self, key: str, default: float = 0.0) -> float:
        """Get a setting value as float."""
        value = await self.get(key)
        return float(value) if value else default

    async def set_float(self, key: str, value: float) -> None:
        """Set a setting value as float."""
        await self.set(key, str(value))

