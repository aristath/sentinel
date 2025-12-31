"""Base repository utilities for common operations."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator, Optional, Union

import aiosqlite

# Re-export for backward compatibility
from app.shared.utils.datetime_utils import safe_parse_datetime_string  # noqa: F401

__all__ = ["safe_parse_datetime_string"]

logger = logging.getLogger(__name__)


def safe_get(row: Any, key: str, default: Any = None) -> Any:
    """
    Safely get a value from a database row.

    Args:
        row: Database row (dict-like object)
        key: Key to retrieve
        default: Default value if key not found

    Returns:
        Value from row or default
    """
    try:
        if hasattr(row, "keys") and key in row.keys():
            return row[key]
        elif hasattr(row, "__getitem__"):
            return row[key]
        else:
            return default
    except (KeyError, IndexError, AttributeError):
        return default


@asynccontextmanager
async def transaction_context(
    db: Union[Any, aiosqlite.Connection],
) -> AsyncIterator[aiosqlite.Connection]:
    """
    Transaction context manager that works with both Database instances and raw aiosqlite.Connection.

    Args:
        db: Either a Database instance (from manager) or raw aiosqlite.Connection

    Yields:
        aiosqlite.Connection for executing queries
    """
    # Check if db has transaction method (Database instance or DatabaseAdapter)
    if hasattr(db, "transaction"):
        async with db.transaction() as conn:
            yield conn
    else:
        # Raw aiosqlite.Connection - already open, just use it directly
        # Don't re-enter with 'async with db:' as it's already entered
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise


def safe_get_datetime(row: Any, key: str) -> Optional[datetime]:
    """
    Safely parse a datetime from a database row.

    Args:
        row: Database row (dict-like object)
        key: Key containing datetime string

    Returns:
        Parsed datetime or None if invalid/missing
    """
    value = safe_get(row, key)
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    try:
        if isinstance(value, str):
            return datetime.fromisoformat(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse datetime from {key}: {e}")
        return None

    # Fallback (should never be reached, but satisfies type checker)
    return None


def safe_get_bool(row: Any, key: str, default: bool = False) -> bool:
    """
    Safely get a boolean value from a database row.

    Handles integer 0/1 values and boolean values.

    Args:
        row: Database row (dict-like object)
        key: Key to retrieve
        default: Default value if key not found

    Returns:
        Boolean value
    """
    value = safe_get(row, key, default)

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return bool(value)

    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")

    return bool(value) if value is not None else default


def safe_get_float(
    row: Any, key: str, default: Optional[float] = None
) -> Optional[float]:
    """
    Safely get a float value from a database row.

    Args:
        row: Database row (dict-like object)
        key: Key to retrieve
        default: Default value if key not found or invalid

    Returns:
        Float value or default
    """
    value = safe_get(row, key, default)

    if value is None:
        return default

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    return default


def safe_get_int(row: Any, key: str, default: Optional[int] = None) -> Optional[int]:
    """
    Safely get an integer value from a database row.

    Args:
        row: Database row (dict-like object)
        key: Key to retrieve
        default: Default value if key not found or invalid

    Returns:
        Integer value or default
    """
    value = safe_get(row, key, default)

    if value is None:
        return default

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    if isinstance(value, str):
        try:
            return int(float(value))  # Handle "123.0" strings
        except (ValueError, TypeError):
            return default

    return default


class DatabaseAdapter:
    """Adapter to make raw aiosqlite.Connection work like Database instance for testing."""

    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    async def fetchone(self, sql: str, params: tuple = ()):
        """Execute and fetch one row."""
        cursor = await self._conn.execute(sql, params)
        return await cursor.fetchone()

    async def fetchall(self, sql: str, params: tuple = ()):
        """Execute and fetch all rows."""
        cursor = await self._conn.execute(sql, params)
        return await cursor.fetchall()

    async def execute(self, sql: str, params: tuple = ()):
        """Execute a single SQL statement."""
        return await self._conn.execute(sql, params)

    async def commit(self):
        """Commit current transaction."""
        await self._conn.commit()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        """Transaction context manager."""
        # Connection is already open, don't re-enter
        try:
            yield self._conn
            await self._conn.commit()
        except Exception:
            await self._conn.rollback()
            raise
