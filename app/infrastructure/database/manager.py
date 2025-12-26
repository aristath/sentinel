"""
Database Manager - Single point of database access.

This module provides:
1. Centralized database connections (no direct aiosqlite.connect() elsewhere)
2. Per-responsibility database split (config, ledger, state, cache, history)
3. Automatic WAL mode and busy timeout configuration
4. Connection pooling with lazy initialization

All database access should go through db_manager.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

import aiosqlite

logger = logging.getLogger(__name__)


class Database:
    """
    Wrapper for a single SQLite database with proper configuration.

    Handles:
    - WAL mode for better concurrency
    - Busy timeout for retry on lock
    - Row factory for dict-like access
    - Connection lifecycle
    """

    def __init__(self, path: Path, readonly: bool = False):
        self.path = path
        self.readonly = readonly
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return self.path.stem

    async def connect(self) -> aiosqlite.Connection:
        """Get or create connection with proper configuration."""
        async with self._lock:
            if self._connection is None:
                # Ensure parent directory exists
                self.path.parent.mkdir(parents=True, exist_ok=True)

                if self.readonly:
                    # Use URI mode for readonly connections
                    uri = f"file:{self.path}?mode=ro"
                    self._connection = await aiosqlite.connect(uri, uri=True)
                else:
                    self._connection = await aiosqlite.connect(self.path)
                self._connection.row_factory = aiosqlite.Row

                # Configure for reliability over speed
                await self._connection.execute("PRAGMA journal_mode=WAL")
                await self._connection.execute(
                    "PRAGMA busy_timeout=60000"
                )  # 60 seconds
                await self._connection.execute(
                    "PRAGMA synchronous=NORMAL"
                )  # Balance of safety/speed
                await self._connection.execute("PRAGMA cache_size=-8000")  # 8MB cache
                await self._connection.execute("PRAGMA temp_store=MEMORY")

                logger.debug(f"Connected to database: {self.name}")

            return self._connection

    async def close(self):
        """Close the database connection."""
        async with self._lock:
            if self._connection is not None:
                await self._connection.close()
                self._connection = None
                logger.debug(f"Closed database: {self.name}")

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        """
        Transaction context manager with automatic rollback on error.

        Usage:
            async with db.transaction() as conn:
                await conn.execute("INSERT ...")
                await conn.execute("UPDATE ...")
                # Commits on success, rolls back on exception
        """
        conn = await self.connect()
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Execute a single SQL statement."""
        conn = await self.connect()
        return await conn.execute(sql, params)

    async def executemany(self, sql: str, params_seq) -> aiosqlite.Cursor:
        """Execute SQL with multiple parameter sets."""
        conn = await self.connect()
        return await conn.executemany(sql, params_seq)

    async def executescript(self, sql: str):
        """Execute multiple SQL statements."""
        conn = await self.connect()
        await conn.executescript(sql)

    async def commit(self):
        """Commit current transaction."""
        conn = await self.connect()
        await conn.commit()

    async def fetchone(self, sql: str, params: tuple = ()) -> Optional[aiosqlite.Row]:
        """Execute and fetch one row."""
        cursor = await self.execute(sql, params)
        return await cursor.fetchone()

    async def fetchall(self, sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
        """Execute and fetch all rows."""
        cursor = await self.execute(sql, params)
        rows = await cursor.fetchall()
        return list(rows)

    async def integrity_check(self) -> str:
        """Run SQLite integrity check."""
        row = await self.fetchone("PRAGMA integrity_check")
        return row[0] if row else "unknown"

    async def checkpoint(self):
        """Run WAL checkpoint."""
        await self.execute("PRAGMA wal_checkpoint(TRUNCATE)")


class DatabaseManager:
    """
    Single point of database access for the entire application.

    Databases:
    - config: Stock universe, allocation targets, settings (rarely changes)
    - ledger: Trades, cash flows (append-only audit trail)
    - state: Positions, scores, snapshots (current state, rebuildable)
    - cache: Computed aggregates (ephemeral, can be rebuilt)
    - calculations: Pre-computed raw metrics (RSI, EMA, Sharpe, CAGR, etc.)
    - history: Per-symbol price databases (isolated for corruption containment)
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.history_dir = data_dir / "history"

        # Core databases
        self.config = Database(data_dir / "config.db")
        self.ledger = Database(data_dir / "ledger.db")
        self.state = Database(data_dir / "state.db")
        self.cache = Database(data_dir / "cache.db")
        self.calculations = Database(data_dir / "calculations.db")

        # Per-symbol history databases (lazy loaded)
        self._history: dict[str, Database] = {}
        self._history_lock = asyncio.Lock()

    async def history(self, symbol: str) -> Database:
        """
        Get or create per-symbol history database.

        Each symbol gets its own database for:
        - Corruption isolation (one symbol's corruption doesn't affect others)
        - Independent recovery (can re-fetch from Yahoo if corrupted)
        - Smaller files (easier backup/restore)
        """
        from app.infrastructure.database.schemas import init_history_schema

        # Sanitize symbol for filename (replace dots with underscores)
        safe_symbol = symbol.replace(".", "_").replace("-", "_")

        async with self._history_lock:
            if symbol not in self._history:
                self.history_dir.mkdir(parents=True, exist_ok=True)
                db_path = self.history_dir / f"{safe_symbol}.db"
                db = Database(db_path)
                self._history[symbol] = db

                # Initialize schema for new history database
                await init_history_schema(db)
                logger.debug(f"Initialized history database for {symbol}")

            return self._history[symbol]

    async def close_all(self):
        """Close all database connections."""
        await self.config.close()
        await self.ledger.close()
        await self.state.close()
        await self.cache.close()
        await self.calculations.close()

        for db in self._history.values():
            await db.close()

        logger.info("All database connections closed")

    async def integrity_check_all(self) -> dict[str, str]:
        """
        Run integrity check on all databases.

        Returns dict of {database_name: result}.
        "ok" means healthy, anything else indicates corruption.
        """
        results = {}

        for name, db in [
            ("config", self.config),
            ("ledger", self.ledger),
            ("state", self.state),
            ("cache", self.cache),
            ("calculations", self.calculations),
        ]:
            try:
                results[name] = await db.integrity_check()
            except Exception as e:
                results[name] = f"error: {e}"

        # Check history databases
        for symbol, db in self._history.items():
            try:
                results[f"history/{symbol}"] = await db.integrity_check()
            except Exception as e:
                results[f"history/{symbol}"] = f"error: {e}"

        return results

    async def checkpoint_all(self):
        """Run WAL checkpoint on all databases."""
        for db in [self.config, self.ledger, self.state, self.cache, self.calculations]:
            await db.checkpoint()

        for db in self._history.values():
            await db.checkpoint()

        logger.info("WAL checkpoint completed for all databases")

    def get_history_symbols(self) -> list[str]:
        """Get list of symbols with history databases."""
        if not self.history_dir.exists():
            return []

        symbols = []
        for path in self.history_dir.glob("*.db"):
            # Convert filename back to symbol
            symbol = path.stem.replace("_", ".")
            # Handle cases like NOVO_B_CO -> NOVO-B.CO
            # This is a simplified approach; proper mapping should be stored
            symbols.append(symbol)

        return symbols


# Global instance - initialized by init_databases()
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    if _db_manager is None:
        raise RuntimeError(
            "Database manager not initialized. Call init_databases() first."
        )
    return _db_manager


async def init_databases(data_dir: Path) -> DatabaseManager:
    """
    Initialize the database manager and create schemas.

    This should be called once at application startup.
    """
    global _db_manager

    from app.infrastructure.database.schemas import (
        init_cache_schema,
        init_calculations_schema,
        init_config_schema,
        init_ledger_schema,
        init_state_schema,
    )

    _db_manager = DatabaseManager(data_dir)

    # Initialize schemas
    await init_config_schema(_db_manager.config)
    await init_ledger_schema(_db_manager.ledger)
    await init_state_schema(_db_manager.state)
    await init_cache_schema(_db_manager.cache)
    await init_calculations_schema(_db_manager.calculations)

    logger.info(f"Database manager initialized with data directory: {data_dir}")

    return _db_manager


async def shutdown_databases():
    """Shutdown all database connections."""
    global _db_manager
    if _db_manager is not None:
        await _db_manager.close_all()
        _db_manager = None
