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
    - state: Positions (current state, rebuildable from ledger)
    - cache: Ephemeral computed aggregates (can be deleted)
    - calculations: Pre-computed metrics and scores
    - recommendations: Trade recommendations (operational)
    - dividends: Dividend history with DRIP tracking
    - rates: Exchange rates
    - snapshots: Portfolio snapshots (daily time-series)
    - history: Per-stock price databases (keyed by ISIN)
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

        # New dedicated databases
        self.recommendations = Database(data_dir / "recommendations.db")
        self.dividends = Database(data_dir / "dividends.db")
        self.rates = Database(data_dir / "rates.db")
        self.snapshots = Database(data_dir / "snapshots.db")
        self.planner = Database(data_dir / "planner.db")

        # Per-stock history databases (lazy loaded, keyed by ISIN)
        self._history: dict[str, Database] = {}
        self._history_lock = asyncio.Lock()

    async def history(self, identifier: str) -> Database:
        """
        Get or create per-stock history database.

        Accepts either symbol or ISIN as identifier.
        Files are named by ISIN (if available) or sanitized symbol.

        Each stock gets its own database for:
        - Corruption isolation (one stock's corruption doesn't affect others)
        - Independent recovery (can re-fetch from Yahoo if corrupted)
        - Smaller files (easier backup/restore)
        """
        from app.modules.portfolio.database.schemas import init_history_schema

        # Normalize identifier
        identifier = identifier.strip().upper()

        async with self._history_lock:
            # Check if already cached
            if identifier in self._history:
                return self._history[identifier]

            self.history_dir.mkdir(parents=True, exist_ok=True)

            # Determine file path - prefer ISIN-based filename
            isin = await self._resolve_to_isin(identifier)

            if isin:
                # ISIN is alphanumeric, no sanitization needed
                db_path = self.history_dir / f"{isin}.db"
                cache_key = isin
            else:
                # Fall back to sanitized symbol
                safe_symbol = identifier.replace(".", "_").replace("-", "_")
                db_path = self.history_dir / f"{safe_symbol}.db"
                cache_key = identifier

            # Check for backwards compatibility - look for old symbol-based file
            if not db_path.exists() and isin:
                # ISIN-based file doesn't exist, check for old symbol-based file
                old_path = await self._find_legacy_history_file(identifier)
                if old_path and old_path.exists():
                    db_path = old_path

            db = Database(db_path)
            self._history[cache_key] = db

            # Also cache under original identifier for faster lookup
            if cache_key != identifier:
                self._history[identifier] = db

            # Initialize schema for new history database
            await init_history_schema(db)
            logger.debug(f"Initialized history database for {identifier} at {db_path}")

            return db

    async def _resolve_to_isin(self, identifier: str) -> Optional[str]:
        """Resolve identifier to ISIN if possible."""
        from app.modules.universe.domain.symbol_resolver import is_isin

        # If already an ISIN, return it
        if is_isin(identifier):
            return identifier

        # Look up ISIN from stocks table
        try:
            row = await self.config.fetchone(
                "SELECT isin FROM stocks WHERE symbol = ?", (identifier,)
            )
            if row and row["isin"]:
                return row["isin"]
        except Exception:
            pass

        return None

    async def _find_legacy_history_file(self, identifier: str) -> Optional[Path]:
        """Find legacy symbol-based history file for backwards compatibility."""
        # Try various sanitization patterns
        safe_symbol = identifier.replace(".", "_").replace("-", "_")
        legacy_path = self.history_dir / f"{safe_symbol}.db"
        if legacy_path.exists():
            return legacy_path
        return None

    async def close_all(self):
        """Close all database connections."""
        await self.config.close()
        await self.ledger.close()
        await self.state.close()
        await self.cache.close()
        await self.calculations.close()
        await self.recommendations.close()
        await self.dividends.close()
        await self.rates.close()
        await self.snapshots.close()

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
            ("recommendations", self.recommendations),
            ("dividends", self.dividends),
            ("rates", self.rates),
            ("snapshots", self.snapshots),
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
        for db in [
            self.config,
            self.ledger,
            self.state,
            self.cache,
            self.calculations,
            self.recommendations,
            self.dividends,
            self.rates,
            self.snapshots,
        ]:
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

    from app.core.database.schemas import (
        init_cache_schema,
        init_calculations_schema,
        init_config_schema,
        init_ledger_schema,
        init_rates_schema,
        init_recommendations_schema,
        init_state_schema,
    )
    from app.modules.dividends.database.schemas import init_dividends_schema
    from app.modules.planning.database.schemas import init_planner_schema
    from app.modules.portfolio.database.schemas import (
        init_history_schema,
        init_snapshots_schema,
    )

    _db_manager = DatabaseManager(data_dir)

    # Initialize schemas for core databases
    await init_config_schema(_db_manager.config)
    await init_ledger_schema(_db_manager.ledger)
    await init_state_schema(_db_manager.state)
    await init_cache_schema(_db_manager.cache)
    await init_calculations_schema(_db_manager.calculations)

    # Initialize schemas for new dedicated databases
    await init_recommendations_schema(_db_manager.recommendations)
    await init_dividends_schema(_db_manager.dividends)
    await init_rates_schema(_db_manager.rates)
    await init_snapshots_schema(_db_manager.snapshots)
    await init_planner_schema(_db_manager.planner)

    logger.info(f"Database manager initialized with data directory: {data_dir}")

    return _db_manager


async def shutdown_databases():
    """Shutdown all database connections."""
    global _db_manager
    if _db_manager is not None:
        await _db_manager.close_all()
        _db_manager = None
