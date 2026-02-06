"""
Database - Single source of truth for all database operations.

Usage:
    db = Database()
    await db.connect()
    settings = await db.get_settings()
    await db.set_setting('key', 'value')
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from sentinel.database.base import BaseDatabase

logger = logging.getLogger(__name__)


class Database(BaseDatabase):
    """Single source of truth for all database operations."""

    _instances: dict[str, "Database"] = {}  # path -> instance
    _default_path: str | None = None
    _path: Path
    _connection: aiosqlite.Connection | None

    def __new__(cls, path: str | None = None):
        """
        Singleton pattern per path - one database instance per unique path.

        Args:
            path: Database file path. If None, uses default path.
        """
        if path is None:
            if cls._default_path is None:
                from sentinel.paths import DATA_DIR

                cls._default_path = str(DATA_DIR / "sentinel.db")
            path = cls._default_path

        if path not in cls._instances:
            instance = super().__new__(cls)
            instance._path = Path(path)
            instance._connection = None
            cls._instances[path] = instance

        return cls._instances[path]

    def __init__(self, path: str | None = None):
        # Path is already set in __new__, nothing to do here
        pass

    async def connect(self) -> "Database":
        """Connect to database and initialize schema."""
        if self._connection is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = await aiosqlite.connect(self._path)
            self._connection.row_factory = aiosqlite.Row
            await self._connection.execute("PRAGMA journal_mode=WAL")
            await self._connection.execute("PRAGMA busy_timeout=30000")
            await self._init_schema()
        return self

    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    def remove_from_cache(self):
        """Remove this instance from the singleton cache. Use for temporary databases."""
        path_str = str(self._path)
        if path_str in self._instances:
            del self._instances[path_str]

    # -------------------------------------------------------------------------
    # Settings
    # -------------------------------------------------------------------------

    async def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value by key."""
        cursor = await self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]

    async def set_setting(self, key: str, value: Any) -> None:
        """Set a setting value."""
        json_value = json.dumps(value) if not isinstance(value, str) else value
        await self.conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, json_value))
        await self.conn.commit()

    async def get_all_settings(self) -> dict:
        """Get all settings as a dictionary."""
        cursor = await self.conn.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        result = {}
        for row in rows:
            try:
                result[row["key"]] = json.loads(row["value"])
            except (json.JSONDecodeError, TypeError):
                result[row["key"]] = row["value"]
        return result

    # -------------------------------------------------------------------------
    # Securities (extended methods beyond BaseDatabase)
    # -------------------------------------------------------------------------

    async def update_quote_data(self, symbol: str, quote_data: dict) -> None:
        """Update quote data for a security."""
        import time

        await self.conn.execute(
            "UPDATE securities SET quote_data = ?, quote_updated_at = ? WHERE symbol = ?",
            (json.dumps(quote_data), int(time.time()), symbol),
        )
        await self.conn.commit()

    async def update_quotes_bulk(self, quotes: dict[str, dict]) -> None:
        """Update quote data for multiple securities."""
        import time

        now = int(time.time())
        for symbol, quote_data in quotes.items():
            await self.conn.execute(
                "UPDATE securities SET quote_data = ?, quote_updated_at = ? WHERE symbol = ?",
                (json.dumps(quote_data), now, symbol),
            )
        await self.conn.commit()

    # -------------------------------------------------------------------------
    # Prices (extended methods beyond BaseDatabase)
    # -------------------------------------------------------------------------

    async def save_prices(self, symbol: str, prices: list[dict]) -> None:
        """Save historical prices for a security (upsert)."""
        for price in prices:
            await self.conn.execute(
                """INSERT OR REPLACE INTO prices
                   (symbol, date, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    symbol,
                    price["date"],
                    price.get("open"),
                    price.get("high"),
                    price.get("low"),
                    price["close"],
                    price.get("volume"),
                ),
            )
        await self.conn.commit()

    async def get_prices_bulk(
        self,
        symbols: list[str],
        days: int | None = None,
        end_date: str | None = None,
    ) -> dict[str, list[dict]]:
        """Get historical prices for multiple securities in a single query.

        Args:
            symbols: List of security symbols
            days: Number of most recent days to fetch per symbol
            end_date: If set (YYYY-MM-DD), only return rows with date <= end_date

        Returns:
            Dict mapping symbol -> list of price records (newest first)
        """
        if not symbols:
            return {}

        placeholders = ",".join("?" * len(symbols))
        base_where = f"WHERE symbol IN ({placeholders})"
        if end_date is not None:
            base_where += " AND date <= ?"
        base_params: list = list(symbols)
        if end_date is not None:
            base_params.append(end_date)

        if days:
            # Use window function to get top N rows per symbol (after end_date filter)
            query = f"""
                SELECT * FROM (
                    SELECT *,
                        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) as rn
                    FROM prices
                    {base_where}
                )
                WHERE rn <= ?
                ORDER BY symbol, date DESC
            """  # noqa: S608
            params = [*base_params, days]
        else:
            query = f"""
                SELECT * FROM prices
                {base_where}
                ORDER BY symbol, date DESC
            """  # noqa: S608
            params = base_params

        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()

        # Group by symbol
        result = {s: [] for s in symbols}
        for row in rows:
            row_dict = dict(row)
            row_dict.pop("rn", None)  # Remove window function column if present
            result[row["symbol"]].append(row_dict)

        return result

    # -------------------------------------------------------------------------
    # Trades (extended methods beyond BaseDatabase)
    # -------------------------------------------------------------------------

    # record_trade() removed - trades are now synced from broker via upsert_trade()

    # -------------------------------------------------------------------------
    # Allocation Targets (extended methods beyond BaseDatabase)
    # -------------------------------------------------------------------------

    async def set_allocation_target(self, target_type: str, name: str, weight: float) -> None:
        """Set an allocation target weight."""
        await self.conn.execute(
            """INSERT OR REPLACE INTO allocation_targets (type, name, weight)
               VALUES (?, ?, ?)""",
            (target_type, name, weight),
        )
        await self.conn.commit()

    async def delete_allocation_target(self, target_type: str, name: str) -> None:
        """Delete an allocation target."""
        await self.conn.execute("DELETE FROM allocation_targets WHERE type = ? AND name = ?", (target_type, name))
        await self.conn.commit()

    # -------------------------------------------------------------------------
    # Cache
    # -------------------------------------------------------------------------

    async def cache_get(self, key: str) -> Optional[str]:
        """Get a cached value by key. Returns None if not found or expired."""
        import time

        cursor = await self.conn.execute("SELECT value, expires_at FROM cache WHERE key = ?", (key,))
        row = await cursor.fetchone()
        if not row:
            return None

        # Check expiry
        if row["expires_at"] is not None and row["expires_at"] < int(time.time()):
            # Expired - delete and return None
            await self.conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            await self.conn.commit()
            return None

        return row["value"]

    async def cache_set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """Set a cached value. TTL is optional (None = never expires)."""
        import time

        expires_at = int(time.time()) + ttl_seconds if ttl_seconds else None
        await self.conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)", (key, value, expires_at)
        )
        await self.conn.commit()

    async def cache_delete(self, key: str) -> None:
        """Delete a cached value."""
        await self.conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        await self.conn.commit()

    async def cache_clear(self, prefix: str | None = None) -> int:
        """Clear cache entries. If prefix given, only clear keys starting with it."""
        if prefix:
            cursor = await self.conn.execute("DELETE FROM cache WHERE key LIKE ?", (f"{prefix}%",))
        else:
            cursor = await self.conn.execute("DELETE FROM cache")
        await self.conn.commit()
        return cursor.rowcount

    async def cache_cleanup_expired(self) -> int:
        """Remove all expired cache entries."""
        import time

        cursor = await self.conn.execute(
            "DELETE FROM cache WHERE expires_at IS NOT NULL AND expires_at < ?", (int(time.time()),)
        )
        await self.conn.commit()
        return cursor.rowcount

    # -------------------------------------------------------------------------
    # Security Metadata
    # -------------------------------------------------------------------------

    async def update_security_metadata(self, symbol: str, data: dict, market_id: str | None = None) -> None:
        """Update security with raw Tradernet metadata."""
        import json
        import time

        updates = ["data = ?", "last_synced = ?"]
        params: list[str | int] = [json.dumps(data), int(time.time())]

        if market_id:
            updates.append("market_id = ?")
            params.append(market_id)

        # Extract useful fields from data
        if "lot" in data:
            updates.append("min_lot = ?")
            params.append(int(float(data["lot"])))

        params.append(symbol)
        await self.conn.execute(f"UPDATE securities SET {', '.join(updates)} WHERE symbol = ?", params)  # noqa: S608
        await self.conn.commit()

    # -------------------------------------------------------------------------
    # Categories
    # -------------------------------------------------------------------------

    async def get_categories(self, active_only: bool = False) -> dict:
        """Get distinct geographies and industries from securities.

        Values may be stored as comma-separated strings, so we split and dedupe.

        Args:
            active_only: If True, only include active securities

        Returns:
            Dict with 'geographies' and 'industries' lists
        """
        geographies = set()
        industries = set()

        active_filter = " AND active = 1" if active_only else ""

        cursor = await self.conn.execute(
            f"SELECT DISTINCT geography FROM securities WHERE geography IS NOT NULL AND geography != ''{active_filter}"  # noqa: S608
        )
        for row in await cursor.fetchall():
            for val in row["geography"].split(","):
                val = val.strip()
                if val:
                    geographies.add(val)

        cursor = await self.conn.execute(
            f"SELECT DISTINCT industry FROM securities WHERE industry IS NOT NULL AND industry != ''{active_filter}"  # noqa: S608
        )
        for row in await cursor.fetchall():
            for val in row["industry"].split(","):
                val = val.strip()
                if val:
                    industries.add(val)

        return {
            "geographies": sorted(geographies),
            "industries": sorted(industries),
        }

    # -------------------------------------------------------------------------
    # Job History
    # -------------------------------------------------------------------------

    async def log_job_execution(
        self,
        job_id: str,
        job_type: str,
        status: str,
        error: Optional[str],
        duration_ms: int,
        retry_count: int,
    ) -> None:
        """Log a job execution to the job history."""
        await self.conn.execute(
            """INSERT INTO job_history
               (job_id, job_type, status, error, duration_ms, executed_at, retry_count)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (job_id, job_type, status, error, duration_ms, int(datetime.now().timestamp()), retry_count),
        )
        await self.conn.commit()

    async def get_last_job_completion(self, job_type: str) -> Optional[datetime]:
        """Get the timestamp of the last successful completion for a job type."""
        cursor = await self.conn.execute(
            """SELECT executed_at FROM job_history
               WHERE job_type = ? AND status = 'completed'
               ORDER BY executed_at DESC LIMIT 1""",
            (job_type,),
        )
        row = await cursor.fetchone()
        if row:
            return datetime.fromtimestamp(row["executed_at"])
        return None

    async def get_last_job_completion_by_id(self, job_id: str) -> Optional[datetime]:
        """Get the timestamp of the last successful completion for a specific job ID.

        Use this for parameterized jobs like ML jobs where job_id includes the symbol.
        """
        cursor = await self.conn.execute(
            """SELECT executed_at FROM job_history
               WHERE job_id = ? AND status = 'completed'
               ORDER BY executed_at DESC LIMIT 1""",
            (job_id,),
        )
        row = await cursor.fetchone()
        if row:
            return datetime.fromtimestamp(row["executed_at"])
        return None

    async def is_job_completed(self, job_id: str) -> bool:
        """Check if a specific job has ever completed successfully."""
        cursor = await self.conn.execute(
            """SELECT 1 FROM job_history
               WHERE job_id = ? AND status = 'completed' LIMIT 1""",
            (job_id,),
        )
        return await cursor.fetchone() is not None

    async def get_job_history(self, limit: int = 50) -> list[dict]:
        """Get recent job execution history."""
        cursor = await self.conn.execute(
            """SELECT job_id, job_type, status, error, duration_ms,
                      executed_at, retry_count
               FROM job_history
               ORDER BY executed_at DESC LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_ml_enabled_securities(self) -> list[dict]:
        """Get securities with ML enabled."""
        cursor = await self.conn.execute("SELECT symbol FROM securities WHERE ml_enabled = 1 AND active = 1")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # -------------------------------------------------------------------------
    # Job Schedules
    # -------------------------------------------------------------------------

    async def get_job_schedules(self) -> list[dict]:
        """Get all job schedules."""
        cursor = await self.conn.execute("SELECT * FROM job_schedules ORDER BY category, job_type")
        return [dict(row) for row in await cursor.fetchall()]

    async def is_job_expired(self, job_type: str, market_open: bool = False) -> bool:
        """
        Check if a job has expired (needs to run).

        Args:
            job_type: The job type to check
            market_open: If True, use interval_market_open_minutes if available

        Handles exponential backoff for failed jobs:
        - failures < 3: use exponential backoff (2^failures minutes)
        - failures >= 3: use normal interval (stop aggressive retries)
        """
        cursor = await self.conn.execute(
            "SELECT last_run, interval_minutes, interval_market_open_minutes, consecutive_failures"
            " FROM job_schedules WHERE job_type = ?",
            (job_type,),
        )
        row = await cursor.fetchone()
        if row is None:
            return False  # Unknown job

        last_run = row["last_run"] or 0
        consecutive_failures = row["consecutive_failures"] or 0

        # Determine interval based on failure count
        if 0 < consecutive_failures < 3:
            # Exponential backoff: 2^failures minutes (2, 4 minutes)
            interval = 2**consecutive_failures
        else:
            # Normal interval (no failures, or >= 3 failures)
            interval = row["interval_minutes"]
            if market_open and row["interval_market_open_minutes"]:
                interval = row["interval_market_open_minutes"]

        if last_run == 0:
            return True  # Never run or forced = expired

        return int(datetime.now().timestamp()) - last_run >= interval * 60

    async def set_job_last_run(self, job_type: str, timestamp: int) -> None:
        """
        Set the last run timestamp for a job.
        Used to force a job to run by setting timestamp to 0.
        """
        await self.conn.execute("UPDATE job_schedules SET last_run = ? WHERE job_type = ?", (timestamp, job_type))
        await self.conn.commit()

    async def mark_job_completed(self, job_type: str) -> None:
        """Mark a job as completed (update last_run to now, reset failures)."""
        now = int(datetime.now().timestamp())
        await self.conn.execute(
            "UPDATE job_schedules SET last_run = ?, consecutive_failures = 0 WHERE job_type = ?", (now, job_type)
        )
        await self.conn.commit()

    async def mark_job_failed(self, job_type: str) -> None:
        """Mark a job as failed (increment failures, update last_run for backoff)."""
        now = int(datetime.now().timestamp())
        await self.conn.execute(
            "UPDATE job_schedules SET last_run = ?, consecutive_failures = consecutive_failures + 1 WHERE job_type = ?",
            (now, job_type),
        )
        await self.conn.commit()

    async def get_job_schedule(self, job_type: str) -> Optional[dict]:
        """Get a single job schedule by type."""
        cursor = await self.conn.execute("SELECT * FROM job_schedules WHERE job_type = ?", (job_type,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def upsert_job_schedule(
        self,
        job_type: str,
        interval_minutes: Optional[int] = None,
        interval_market_open_minutes: Optional[int] = None,
        market_timing: Optional[int] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
    ) -> None:
        """Insert or update a job schedule."""
        now = int(datetime.now().timestamp())

        existing = await self.get_job_schedule(job_type)
        if existing:
            # Build update query with only provided fields
            updates = []
            params = []
            if interval_minutes is not None:
                updates.append("interval_minutes = ?")
                params.append(interval_minutes)
            if interval_market_open_minutes is not None:
                updates.append("interval_market_open_minutes = ?")
                params.append(interval_market_open_minutes)
            if market_timing is not None:
                updates.append("market_timing = ?")
                params.append(market_timing)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if category is not None:
                updates.append("category = ?")
                params.append(category)

            updates.append("updated_at = ?")
            params.append(now)
            params.append(job_type)

            await self.conn.execute(
                f"UPDATE job_schedules SET {', '.join(updates)} WHERE job_type = ?",  # noqa: S608
                params,
            )
        else:
            await self.conn.execute(
                """INSERT INTO job_schedules
                   (job_type, interval_minutes, interval_market_open_minutes,
                    market_timing, description, category,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_type,
                    interval_minutes or 60,
                    interval_market_open_minutes,
                    market_timing or 0,
                    description,
                    category,
                    now,
                    now,
                ),
            )
        await self.conn.commit()

    async def seed_default_job_schedules(self) -> None:
        """Seed default job schedules if table is empty."""
        cursor = await self.conn.execute("SELECT COUNT(*) FROM job_schedules")
        row = await cursor.fetchone()
        count = row[0] if row else 0
        if count > 0:
            return

        now = int(datetime.now().timestamp())

        # Default job schedules
        # (job_type, interval, interval_open, timing, category, description)
        defaults = [
            ("sync:portfolio", 30, 5, 0, "sync", "Sync portfolio positions from broker"),
            ("sync:prices", 30, 5, 0, "sync", "Sync historical prices for securities"),
            ("sync:quotes", 1440, 1440, 0, "sync", "Sync current quotes"),
            ("sync:metadata", 1440, 1440, 0, "sync", "Sync security metadata"),
            ("sync:exchange_rates", 60, 60, 0, "sync", "Sync exchange rates"),
            ("sync:trades", 60, 60, 0, "sync", "Sync trade history from broker"),
            ("sync:cashflows", 1440, 1440, 0, "sync", "Sync cash flows from broker"),
            ("sync:dividends", 1440, 1440, 0, "sync", "Sync dividends from broker"),
            ("aggregate:compute", 1440, 1440, 1, "sync", "Compute aggregate price series"),
            ("scoring:calculate", 1440, 1440, 0, "scoring", "Calculate security scores"),
            ("trading:check_markets", 30, 30, 2, "trading", "Check which markets are open"),
            ("trading:execute", 30, 15, 2, "trading", "Execute pending trade recommendations"),
            ("trading:rebalance", 60, 60, 0, "trading", "Check portfolio rebalance needs"),
            ("trading:balance_fix", 15, 15, 0, "trading", "Fix negative currency balances"),
            ("planning:refresh", 60, 30, 0, "trading", "Refresh trading plan and recommendations"),
            ("backup:r2", 1440, 1440, 0, "backup", "Backup data folder to Cloudflare R2"),
        ]

        for job_type, interval, interval_open, timing, cat, desc in defaults:
            await self.conn.execute(
                """INSERT INTO job_schedules
                   (job_type, interval_minutes, interval_market_open_minutes,
                    market_timing, description, category,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_type,
                    interval,
                    interval_open,
                    timing,
                    desc,
                    cat,
                    now,
                    now,
                ),
            )
        await self.conn.commit()

    async def get_last_job_completion_by_prefix(self, prefix: str) -> Optional[datetime]:
        """Get most recent completion time for jobs matching prefix."""
        cursor = await self.conn.execute(
            """SELECT executed_at FROM job_history
               WHERE job_id LIKE ? AND status = 'completed'
               ORDER BY executed_at DESC LIMIT 1""",
            (prefix + "%",),
        )
        row = await cursor.fetchone()
        return datetime.fromtimestamp(row["executed_at"]) if row else None

    async def get_job_history_for_type(self, job_type: str, limit: int = 50) -> list[dict]:
        """Get job history for jobs matching type prefix."""
        cursor = await self.conn.execute(
            """SELECT job_id, job_type, status, error, duration_ms, executed_at, retry_count
               FROM job_history
               WHERE job_id LIKE ?
               ORDER BY executed_at DESC LIMIT ?""",
            (job_type + "%", limit),
        )
        return [dict(row) for row in await cursor.fetchall()]

    # -------------------------------------------------------------------------
    # Schema
    # -------------------------------------------------------------------------

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        await self.conn.executescript(SCHEMA)
        await self._apply_migrations()
        await self.conn.commit()

    async def _add_column_if_missing(self, table: str, column: str, definition: str) -> None:
        """Add a column to a table if it doesn't already exist."""
        cursor = await self.conn.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in await cursor.fetchall()}
        if column not in columns:
            await self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    async def _apply_migrations(self) -> None:
        """Apply schema migrations for existing tables."""
        # Add missing columns to securities table
        migrations = [
            ("market_id", "TEXT"),
            ("data", "TEXT"),
            ("last_synced", "INTEGER"),
            ("user_multiplier", "REAL DEFAULT 1.0"),
            ("ml_enabled", "INTEGER DEFAULT 0"),
            ("ml_blend_ratio", "REAL DEFAULT 0.5"),
            ("quote_data", "TEXT"),
            ("quote_updated_at", "INTEGER"),
            ("aliases", "TEXT"),
        ]

        for col_name, definition in migrations:
            await self._add_column_if_missing("securities", col_name, definition)

        # Create job system tables
        await self.conn.executescript("""
        -- Job History (for job system)
        CREATE TABLE IF NOT EXISTS job_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('completed', 'failed')),
            error TEXT,
            duration_ms INTEGER,
            executed_at INTEGER NOT NULL,
            retry_count INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_job_history_job_id ON job_history(job_id, executed_at DESC);
        CREATE INDEX IF NOT EXISTS idx_job_history_job_type ON job_history(job_type, status, executed_at DESC);

        -- Job Schedules (configurable job intervals and settings)
        CREATE TABLE IF NOT EXISTS job_schedules (
            job_type TEXT PRIMARY KEY,
            interval_minutes INTEGER NOT NULL,
            interval_market_open_minutes INTEGER,
            market_timing INTEGER DEFAULT 0,
            description TEXT,
            category TEXT,
            last_run INTEGER DEFAULT 0,
            consecutive_failures INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_job_schedules_category ON job_schedules(category, job_type);
        """)

        # Migration: Migrate trades table to new schema
        await self._migrate_trades_table()

        # Migration: Remove deprecated columns from job_schedules if they exist
        await self._migrate_job_schedules()

        # Migration: add last_run column to job_schedules if missing
        cursor = await self.conn.execute("PRAGMA table_info(job_schedules)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "last_run" not in columns:
            await self.conn.execute("ALTER TABLE job_schedules ADD COLUMN last_run INTEGER DEFAULT 0")
        if "consecutive_failures" not in columns:
            await self.conn.execute("ALTER TABLE job_schedules ADD COLUMN consecutive_failures INTEGER DEFAULT 0")

        # Drop orphaned tables (ML/regime moved to ml.db; others unused)
        for old_table in [
            "ml_training_samples",
            "ml_models",
            "ml_predictions",
            "ml_performance_tracking",
            "regime_states",
            "regime_models",
            "correlation_matrices",
            "hidden_categories",
            "optimization_results",
        ]:
            await self.conn.execute(f"DROP TABLE IF EXISTS {old_table}")

        # Migration: add sync:cashflows job schedule if missing (only for existing databases)
        # Check if job_schedules has any data (indicating an existing database, not fresh install)
        cursor = await self.conn.execute("SELECT COUNT(*) FROM job_schedules")
        count_row = await cursor.fetchone()
        if count_row and count_row[0] > 0:
            # Existing database - check if sync:cashflows is missing
            cursor = await self.conn.execute("SELECT 1 FROM job_schedules WHERE job_type = 'sync:cashflows'")
            if not await cursor.fetchone():
                now = int(datetime.now().timestamp())
                await self.conn.execute(
                    """INSERT INTO job_schedules
                       (job_type, interval_minutes, interval_market_open_minutes,
                        market_timing, description, category, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    ("sync:cashflows", 1440, 1440, 0, "Sync cash flows from broker", "sync", now, now),
                )
                logger.info("Added sync:cashflows job schedule")

            # Check if sync:dividends is missing
            cursor = await self.conn.execute("SELECT 1 FROM job_schedules WHERE job_type = 'sync:dividends'")
            if not await cursor.fetchone():
                now = int(datetime.now().timestamp())
                await self.conn.execute(
                    """INSERT INTO job_schedules
                       (job_type, interval_minutes, interval_market_open_minutes,
                        market_timing, description, category, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    ("sync:dividends", 1440, 1440, 0, "Sync dividends from broker", "sync", now, now),
                )
                logger.info("Added sync:dividends job schedule")

        # Migration: portfolio_snapshots old schema → new JSON schema
        await self._migrate_portfolio_snapshots()

        # Migration: deduplicate trades and enforce UNIQUE on broker_trade_id
        await self._migrate_trades_unique_constraint()

        # Migration: add commission columns to trades table if missing
        cursor = await self.conn.execute("PRAGMA table_info(trades)")
        trade_columns = {row[1] for row in await cursor.fetchall()}
        if "commission" not in trade_columns:
            await self.conn.execute("ALTER TABLE trades ADD COLUMN commission REAL DEFAULT 0")
            await self.conn.execute("ALTER TABLE trades ADD COLUMN commission_currency TEXT DEFAULT 'EUR'")
            # Backfill commission from raw_data for existing trades
            cursor = await self.conn.execute("SELECT id, raw_data FROM trades")
            rows = await cursor.fetchall()
            for row in rows:
                try:
                    data = json.loads(row["raw_data"])
                    commission = float(data.get("commission", 0) or 0)
                    commission_currency = data.get("commission_currency", "EUR")
                    await self.conn.execute(
                        "UPDATE trades SET commission = ?, commission_currency = ? WHERE id = ?",
                        (commission, commission_currency, row["id"]),
                    )
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass
            logger.info("Added commission columns to trades table and backfilled data")

    async def _migrate_trades_table(self) -> None:
        """Migrate trades table to new schema with broker_trade_id and raw_data."""
        cursor = await self.conn.execute("PRAGMA table_info(trades)")
        columns = {row[1] for row in await cursor.fetchall()}

        # Check if we need to migrate (old schema has 'quantity' and 'price' columns)
        if "quantity" in columns and "broker_trade_id" not in columns:
            logger.info("Migrating trades table to new schema...")

            # Drop old table and recreate with new schema
            # Note: We lose old local trades, but that's expected - broker trades are now the source of truth
            await self.conn.execute("DROP TABLE IF EXISTS trades")
            await self.conn.execute("""
                CREATE TABLE trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    broker_trade_id TEXT UNIQUE NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL')),
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    executed_at INTEGER NOT NULL,
                    raw_data TEXT NOT NULL,
                    FOREIGN KEY (symbol) REFERENCES securities(symbol)
                )
            """)
            await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_broker_id ON trades(broker_trade_id)")
            await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
            await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades(executed_at)")
            await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_side ON trades(side)")
            await self.conn.commit()
            logger.info("trades table migration complete")

    async def _migrate_trades_unique_constraint(self) -> None:
        """Ensure broker_trade_id has a UNIQUE constraint and deduplicate existing rows."""
        # Check the actual CREATE TABLE statement for UNIQUE on broker_trade_id
        cursor = await self.conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='trades'")
        row = await cursor.fetchone()
        if not row:
            return

        create_sql = row[0] or ""
        if "broker_trade_id TEXT UNIQUE" in create_sql:
            return  # Already correct

        logger.info("Fixing trades table: adding UNIQUE constraint on broker_trade_id...")

        # Count duplicates before fix
        cursor = await self.conn.execute(
            "SELECT COUNT(*) as total, COUNT(DISTINCT broker_trade_id) as unique_ids FROM trades"
        )
        counts = await cursor.fetchone()
        total = counts[0] or 0
        unique = counts[1] or 0
        logger.info(f"  Before: {total} rows, {unique} unique broker_trade_ids ({total - unique} duplicates)")

        # Rebuild table with UNIQUE constraint, keeping only one row per broker_trade_id
        await self.conn.execute("""
            CREATE TABLE trades_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                broker_trade_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL')),
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                commission REAL DEFAULT 0,
                commission_currency TEXT DEFAULT 'EUR',
                executed_at INTEGER NOT NULL,
                raw_data TEXT,
                FOREIGN KEY (symbol) REFERENCES securities(symbol)
            )
        """)

        # Copy deduplicated data
        await self.conn.execute("""
            INSERT INTO trades_new
                (broker_trade_id, symbol, side, quantity, price, commission,
                 commission_currency, executed_at, raw_data)
            SELECT broker_trade_id, symbol, side, quantity, price, commission,
                   commission_currency, executed_at, raw_data
            FROM trades
            WHERE id IN (
                SELECT MAX(id) FROM trades GROUP BY broker_trade_id
            )
        """)

        await self.conn.execute("DROP TABLE trades")
        await self.conn.execute("ALTER TABLE trades_new RENAME TO trades")

        # Recreate indexes
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_broker_id ON trades(broker_trade_id)")
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades(executed_at)")
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_side ON trades(side)")

        await self.conn.commit()

        # Verify
        cursor = await self.conn.execute("SELECT COUNT(*) FROM trades")
        new_count = (await cursor.fetchone())[0]
        logger.info(f"  After: {new_count} rows (removed {total - new_count} duplicates)")
        logger.info("  trades table UNIQUE constraint migration complete")

    async def _migrate_job_schedules(self) -> None:
        """Migrate job_schedules table to remove deprecated columns."""
        # Check if old columns exist
        cursor = await self.conn.execute("PRAGMA table_info(job_schedules)")
        columns = {row[1] for row in await cursor.fetchall()}

        # Columns to remove (if they exist)
        deprecated_columns = {"enabled", "dependencies", "is_parameterized", "parameter_source", "parameter_field"}

        if not deprecated_columns & columns:
            # No migration needed
            return

        logger.info("Migrating job_schedules table to remove deprecated columns...")

        # SQLite doesn't support DROP COLUMN directly (before 3.35), so we need to:
        # 1. Create new table with clean schema
        # 2. Copy data
        # 3. Drop old table
        # 4. Rename new table

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS job_schedules_new (
                job_type TEXT PRIMARY KEY,
                interval_minutes INTEGER NOT NULL,
                interval_market_open_minutes INTEGER,
                market_timing INTEGER DEFAULT 0,
                description TEXT,
                category TEXT,
                last_run INTEGER DEFAULT 0,
                consecutive_failures INTEGER DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)

        await self.conn.execute("""
            INSERT OR REPLACE INTO job_schedules_new
                (job_type, interval_minutes, interval_market_open_minutes,
                 market_timing, description, category, last_run,
                 consecutive_failures, created_at, updated_at)
            SELECT
                job_type, interval_minutes, interval_market_open_minutes,
                market_timing, description, category,
                COALESCE(last_run, 0),
                COALESCE(consecutive_failures, 0),
                created_at, updated_at
            FROM job_schedules
        """)

        await self.conn.execute("DROP TABLE job_schedules")
        await self.conn.execute("ALTER TABLE job_schedules_new RENAME TO job_schedules")
        await self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_job_schedules_category ON job_schedules(category, job_type)"
        )

        await self.conn.commit()
        logger.info("job_schedules migration complete")

    async def _migrate_portfolio_snapshots(self) -> None:
        """Drop old wide-column portfolio_snapshots and recreate with JSON schema."""
        cursor = await self.conn.execute("PRAGMA table_info(portfolio_snapshots)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "total_value_eur" in columns:
            logger.info("Migrating portfolio_snapshots to JSON schema (dropping old table)...")
            await self.conn.execute("DROP TABLE portfolio_snapshots")
            await self.conn.execute("""
                CREATE TABLE portfolio_snapshots (
                    date INTEGER PRIMARY KEY,
                    data TEXT NOT NULL
                )
            """)
            await self.conn.commit()
            logger.info("portfolio_snapshots migration complete")


SCHEMA = """
-- Settings (key-value store)
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Securities universe
CREATE TABLE IF NOT EXISTS securities (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    currency TEXT DEFAULT 'EUR',
    market_id TEXT,  -- Tradernet market ID (from security_info.mrkt.mkt_id)
    geography TEXT,
    industry TEXT,
    min_lot INTEGER DEFAULT 1,
    active INTEGER DEFAULT 1,
    allow_buy INTEGER DEFAULT 1,
    allow_sell INTEGER DEFAULT 1,
    user_multiplier REAL DEFAULT 1.0,  -- User conviction multiplier (0.5 = bearish, 1.0 = neutral, 2.0 = bullish)
    ml_enabled INTEGER DEFAULT 0,  -- Per-security ML toggle (0 = disabled, 1 = enabled)
    ml_blend_ratio REAL DEFAULT 0.5,  -- ML/wavelet blend (0.0 = pure wavelet, 1.0 = pure ML)
    aliases TEXT,  -- Comma-separated alternative names for news/sentiment search
    data TEXT,  -- Raw Tradernet API response (JSON)
    last_synced INTEGER,
    quote_data TEXT,  -- Raw quote data from Tradernet API (JSON)
    quote_updated_at INTEGER  -- When quote_data was last updated (unix timestamp)
);

-- Current positions
CREATE TABLE IF NOT EXISTS positions (
    symbol TEXT PRIMARY KEY,
    quantity REAL NOT NULL DEFAULT 0,
    avg_cost REAL,
    current_price REAL,
    currency TEXT DEFAULT 'EUR',
    updated_at TEXT,
    FOREIGN KEY (symbol) REFERENCES securities(symbol)
);

-- Historical prices
CREATE TABLE IF NOT EXISTS prices (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL NOT NULL,
    volume INTEGER,
    PRIMARY KEY (symbol, date)
);

-- Trade history (synced from broker)
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    broker_trade_id TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL')),
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    commission REAL DEFAULT 0,
    commission_currency TEXT DEFAULT 'EUR',
    executed_at INTEGER NOT NULL,
    raw_data TEXT NOT NULL,
    FOREIGN KEY (symbol) REFERENCES securities(symbol)
);

-- Allocation targets (weights, not percentages)
CREATE TABLE IF NOT EXISTS allocation_targets (
    type TEXT NOT NULL CHECK(type IN ('geography', 'industry')),
    name TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (type, name)
);

-- Scores (historical; one row per calculation, latest per symbol via query)
CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    score REAL,
    components TEXT,  -- JSON with breakdown
    calculated_at INTEGER NOT NULL,
    FOREIGN KEY (symbol) REFERENCES securities(symbol)
);
CREATE INDEX IF NOT EXISTS idx_scores_symbol_calculated_at ON scores (symbol, calculated_at);

-- Cash balances per currency
CREATE TABLE IF NOT EXISTS cash_balances (
    currency TEXT PRIMARY KEY,
    amount REAL NOT NULL DEFAULT 0,
    updated_at TEXT
);

-- Cache (key-value store with TTL)
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    expires_at INTEGER  -- Unix timestamp, NULL = never expires
);

-- Cash flows (synced from broker: deposits, withdrawals, dividends, taxes)
CREATE TABLE IF NOT EXISTS cash_flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash TEXT UNIQUE NOT NULL,  -- Hash of raw_data for deduplication
    date TEXT NOT NULL,
    type_id TEXT NOT NULL,  -- card, card_payout, dividend, tax, block, unblock
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    comment TEXT,
    raw_data TEXT NOT NULL
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_prices_symbol_date ON prices(symbol, date);
CREATE INDEX IF NOT EXISTS idx_trades_broker_id ON trades(broker_trade_id);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades(executed_at);
CREATE INDEX IF NOT EXISTS idx_trades_side ON trades(side);
CREATE INDEX IF NOT EXISTS idx_cache_expires_at ON cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_cash_flows_date ON cash_flows(date);
CREATE INDEX IF NOT EXISTS idx_cash_flows_type ON cash_flows(type_id);

-- Portfolio snapshots (daily composition tracking — JSON blob)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    date INTEGER PRIMARY KEY,  -- unix timestamp, midnight UTC
    data TEXT NOT NULL          -- JSON: {positions: {symbol: {quantity, value_eur}}, cash_eur}
);

-- Dividends (synced from broker corporate actions)
CREATE TABLE IF NOT EXISTS dividends (
    id TEXT PRIMARY KEY,  -- corporate_action_id from broker API
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    amount REAL NOT NULL,  -- Net credited amount in original currency (after taxes)
    currency TEXT NOT NULL,
    value REAL NOT NULL,  -- EUR-equivalent value (amount converted to EUR)
    data TEXT NOT NULL  -- Full raw JSON from corporate actions API
);
CREATE INDEX IF NOT EXISTS idx_dividends_symbol ON dividends(symbol);
CREATE INDEX IF NOT EXISTS idx_dividends_date ON dividends(date);

-- Historical FX rates cache
CREATE TABLE IF NOT EXISTS fx_rates_history (
    date TEXT NOT NULL,
    currency TEXT NOT NULL,
    rate_to_eur REAL NOT NULL,
    PRIMARY KEY (date, currency)
);
"""
