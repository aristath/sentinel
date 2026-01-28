"""
Database - Single source of truth for all database operations.

Usage:
    db = Database()
    await db.connect()
    settings = await db.get_settings()
    await db.set_setting('key', 'value')
"""

import aiosqlite
from pathlib import Path
from typing import Any, Optional
import json


class Database:
    """Single source of truth for all database operations."""

    _instances: dict[str, 'Database'] = {}  # path -> instance
    _default_path: str = None

    def __new__(cls, path: str = None):
        """
        Singleton pattern per path - one database instance per unique path.

        Args:
            path: Database file path. If None, uses default path.
        """
        if path is None:
            if cls._default_path is None:
                cls._default_path = str(Path(__file__).parent.parent / 'data' / 'sentinel.db')
            path = cls._default_path

        if path not in cls._instances:
            instance = super().__new__(cls)
            instance._path = Path(path)
            instance._connection = None
            cls._instances[path] = instance

        return cls._instances[path]

    def __init__(self, path: str = None):
        # Path is already set in __new__, nothing to do here
        pass

    async def connect(self) -> 'Database':
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

    @property
    def conn(self) -> aiosqlite.Connection:
        """Get raw connection for advanced operations."""
        if not self._connection:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection

    # -------------------------------------------------------------------------
    # Settings
    # -------------------------------------------------------------------------

    async def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value by key."""
        cursor = await self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        if row is None:
            return default
        try:
            return json.loads(row['value'])
        except (json.JSONDecodeError, TypeError):
            return row['value']

    async def set_setting(self, key: str, value: Any) -> None:
        """Set a setting value."""
        json_value = json.dumps(value) if not isinstance(value, str) else value
        await self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, json_value)
        )
        await self.conn.commit()

    async def get_all_settings(self) -> dict:
        """Get all settings as a dictionary."""
        cursor = await self.conn.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        result = {}
        for row in rows:
            try:
                result[row['key']] = json.loads(row['value'])
            except (json.JSONDecodeError, TypeError):
                result[row['key']] = row['value']
        return result

    # -------------------------------------------------------------------------
    # Securities
    # -------------------------------------------------------------------------

    async def get_security(self, symbol: str) -> Optional[dict]:
        """Get a security by symbol."""
        cursor = await self.conn.execute(
            "SELECT * FROM securities WHERE symbol = ?", (symbol,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_all_securities(self, active_only: bool = True) -> list[dict]:
        """Get all securities."""
        query = "SELECT * FROM securities"
        if active_only:
            query += " WHERE active = 1"
        cursor = await self.conn.execute(query)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def upsert_security(self, symbol: str, **data) -> None:
        """Insert or update a security."""
        existing = await self.get_security(symbol)
        if existing:
            sets = ", ".join(f"{k} = ?" for k in data.keys())
            await self.conn.execute(
                f"UPDATE securities SET {sets} WHERE symbol = ?",
                (*data.values(), symbol)
            )
        else:
            data['symbol'] = symbol
            cols = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))
            await self.conn.execute(
                f"INSERT INTO securities ({cols}) VALUES ({placeholders})",
                tuple(data.values())
            )
        await self.conn.commit()

    async def update_quote_data(self, symbol: str, quote_data: dict) -> None:
        """Update quote data for a security."""
        import time
        await self.conn.execute(
            "UPDATE securities SET quote_data = ?, quote_updated_at = ? WHERE symbol = ?",
            (json.dumps(quote_data), int(time.time()), symbol)
        )
        await self.conn.commit()

    async def update_quotes_bulk(self, quotes: dict[str, dict]) -> None:
        """Update quote data for multiple securities."""
        import time
        now = int(time.time())
        for symbol, quote_data in quotes.items():
            await self.conn.execute(
                "UPDATE securities SET quote_data = ?, quote_updated_at = ? WHERE symbol = ?",
                (json.dumps(quote_data), now, symbol)
            )
        await self.conn.commit()

    # -------------------------------------------------------------------------
    # Positions
    # -------------------------------------------------------------------------

    async def get_position(self, symbol: str) -> Optional[dict]:
        """Get a position by symbol."""
        cursor = await self.conn.execute(
            "SELECT * FROM positions WHERE symbol = ?", (symbol,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_all_positions(self) -> list[dict]:
        """Get all positions."""
        cursor = await self.conn.execute("SELECT * FROM positions WHERE quantity > 0")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def upsert_position(self, symbol: str, **data) -> None:
        """Insert or update a position."""
        existing = await self.get_position(symbol)
        if existing:
            sets = ", ".join(f"{k} = ?" for k in data.keys())
            await self.conn.execute(
                f"UPDATE positions SET {sets} WHERE symbol = ?",
                (*data.values(), symbol)
            )
        else:
            data['symbol'] = symbol
            cols = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))
            await self.conn.execute(
                f"INSERT INTO positions ({cols}) VALUES ({placeholders})",
                tuple(data.values())
            )
        await self.conn.commit()

    # -------------------------------------------------------------------------
    # Prices
    # -------------------------------------------------------------------------

    async def save_prices(self, symbol: str, prices: list[dict]) -> None:
        """Save historical prices for a security (upsert)."""
        for price in prices:
            await self.conn.execute(
                """INSERT OR REPLACE INTO prices
                   (symbol, date, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (symbol, price['date'], price.get('open'), price.get('high'),
                 price.get('low'), price['close'], price.get('volume'))
            )
        await self.conn.commit()

    async def replace_prices(self, symbol: str, prices: list[dict]) -> None:
        """Merge historical prices for a security (upsert - keeps existing data for missing dates)."""
        for price in prices:
            await self.conn.execute(
                """INSERT OR REPLACE INTO prices
                   (symbol, date, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (symbol, price['date'], price.get('open'), price.get('high'),
                 price.get('low'), price['close'], price.get('volume'))
            )
        await self.conn.commit()

    async def get_prices(self, symbol: str, days: int = None) -> list[dict]:
        """Get historical prices for a security."""
        query = "SELECT * FROM prices WHERE symbol = ? ORDER BY date DESC"
        params = [symbol]
        if days:
            query += " LIMIT ?"
            params.append(days)
        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_prices_bulk(self, symbols: list[str], days: int = None) -> dict[str, list[dict]]:
        """Get historical prices for multiple securities in a single query.

        Args:
            symbols: List of security symbols
            days: Number of most recent days to fetch per symbol

        Returns:
            Dict mapping symbol -> list of price records (newest first)
        """
        if not symbols:
            return {}

        placeholders = ','.join('?' * len(symbols))

        if days:
            # Use window function to get top N rows per symbol
            query = f"""
                SELECT * FROM (
                    SELECT *,
                        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) as rn
                    FROM prices
                    WHERE symbol IN ({placeholders})
                )
                WHERE rn <= ?
                ORDER BY symbol, date DESC
            """
            params = [*symbols, days]
        else:
            query = f"""
                SELECT * FROM prices
                WHERE symbol IN ({placeholders})
                ORDER BY symbol, date DESC
            """
            params = symbols

        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()

        # Group by symbol
        result = {s: [] for s in symbols}
        for row in rows:
            row_dict = dict(row)
            row_dict.pop('rn', None)  # Remove window function column if present
            result[row['symbol']].append(row_dict)

        return result

    # -------------------------------------------------------------------------
    # Trades
    # -------------------------------------------------------------------------

    async def record_trade(self, symbol: str, side: str, quantity: float,
                          price: float, **extra) -> int:
        """Record a trade."""
        cursor = await self.conn.execute(
            """INSERT INTO trades (symbol, side, quantity, price, executed_at)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (symbol, side, quantity, price)
        )
        await self.conn.commit()
        return cursor.lastrowid

    async def get_trades(self, symbol: str = None, limit: int = 100) -> list[dict]:
        """Get trade history."""
        query = "SELECT * FROM trades"
        params = []
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol)
        query += " ORDER BY executed_at DESC LIMIT ?"
        params.append(limit)
        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # -------------------------------------------------------------------------
    # Allocation Targets
    # -------------------------------------------------------------------------

    async def get_allocation_targets(self, target_type: str = None) -> list[dict]:
        """Get allocation targets (geography or industry weights)."""
        query = "SELECT * FROM allocation_targets"
        params = []
        if target_type:
            query += " WHERE type = ?"
            params.append(target_type)
        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def set_allocation_target(self, target_type: str, name: str, weight: float) -> None:
        """Set an allocation target weight."""
        await self.conn.execute(
            """INSERT OR REPLACE INTO allocation_targets (type, name, weight)
               VALUES (?, ?, ?)""",
            (target_type, name, weight)
        )
        await self.conn.commit()

    async def delete_allocation_target(self, target_type: str, name: str) -> None:
        """Delete an allocation target."""
        await self.conn.execute(
            "DELETE FROM allocation_targets WHERE type = ? AND name = ?",
            (target_type, name)
        )
        await self.conn.commit()

    # -------------------------------------------------------------------------
    # Cache
    # -------------------------------------------------------------------------

    async def cache_get(self, key: str) -> str | None:
        """Get a cached value by key. Returns None if not found or expired."""
        import time
        cursor = await self.conn.execute(
            "SELECT value, expires_at FROM cache WHERE key = ?",
            (key,)
        )
        row = await cursor.fetchone()
        if not row:
            return None

        # Check expiry
        if row['expires_at'] is not None and row['expires_at'] < int(time.time()):
            # Expired - delete and return None
            await self.conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            await self.conn.commit()
            return None

        return row['value']

    async def cache_set(self, key: str, value: str, ttl_seconds: int = None) -> None:
        """Set a cached value. TTL is optional (None = never expires)."""
        import time
        expires_at = int(time.time()) + ttl_seconds if ttl_seconds else None
        await self.conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
            (key, value, expires_at)
        )
        await self.conn.commit()

    async def cache_delete(self, key: str) -> None:
        """Delete a cached value."""
        await self.conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        await self.conn.commit()

    async def cache_clear(self, prefix: str = None) -> int:
        """Clear cache entries. If prefix given, only clear keys starting with it."""
        if prefix:
            cursor = await self.conn.execute(
                "DELETE FROM cache WHERE key LIKE ?",
                (f"{prefix}%",)
            )
        else:
            cursor = await self.conn.execute("DELETE FROM cache")
        await self.conn.commit()
        return cursor.rowcount

    async def cache_cleanup_expired(self) -> int:
        """Remove all expired cache entries."""
        import time
        cursor = await self.conn.execute(
            "DELETE FROM cache WHERE expires_at IS NOT NULL AND expires_at < ?",
            (int(time.time()),)
        )
        await self.conn.commit()
        return cursor.rowcount

    # -------------------------------------------------------------------------
    # Security Metadata
    # -------------------------------------------------------------------------

    async def update_security_metadata(self, symbol: str, data: dict, market_id: str = None) -> None:
        """Update security with raw Tradernet metadata."""
        import json
        updates = ["data = ?", "last_synced = datetime('now')"]
        params = [json.dumps(data)]

        if market_id:
            updates.append("market_id = ?")
            params.append(market_id)

        # Extract useful fields from data
        if 'lot' in data:
            updates.append("min_lot = ?")
            params.append(int(float(data['lot'])))

        params.append(symbol)
        await self.conn.execute(
            f"UPDATE securities SET {', '.join(updates)} WHERE symbol = ?",
            params
        )
        await self.conn.commit()

    # -------------------------------------------------------------------------
    # Cash Balances
    # -------------------------------------------------------------------------

    async def get_cash_balances(self) -> dict[str, float]:
        """Get all cash balances as a dictionary of currency -> amount."""
        cursor = await self.conn.execute("SELECT currency, amount FROM cash_balances")
        rows = await cursor.fetchall()
        return {row['currency']: row['amount'] for row in rows}

    async def set_cash_balance(self, currency: str, amount: float) -> None:
        """Set cash balance for a currency."""
        await self.conn.execute(
            """INSERT OR REPLACE INTO cash_balances (currency, amount, updated_at)
               VALUES (?, ?, datetime('now'))""",
            (currency, amount)
        )
        await self.conn.commit()

    async def set_cash_balances(self, balances: dict[str, float]) -> None:
        """Set multiple cash balances at once. Clears existing balances."""
        await self.conn.execute("DELETE FROM cash_balances")
        for currency, amount in balances.items():
            if amount > 0:  # Only store non-zero balances
                await self.conn.execute(
                    """INSERT INTO cash_balances (currency, amount, updated_at)
                       VALUES (?, ?, datetime('now'))""",
                    (currency, amount)
                )
        await self.conn.commit()

    # -------------------------------------------------------------------------
    # Categories
    # -------------------------------------------------------------------------

    async def get_distinct_categories(self) -> dict:
        """
        Get distinct geographies and industries from existing securities.

        Values may be stored as comma-separated strings, so we split and dedupe.

        Returns:
            Dict with 'geographies' and 'industries' lists
        """
        geographies = set()
        industries = set()

        # Get all geography values and split comma-separated entries
        cursor = await self.conn.execute(
            "SELECT DISTINCT geography FROM securities WHERE geography IS NOT NULL AND geography != ''"
        )
        rows = await cursor.fetchall()
        for row in rows:
            for val in row['geography'].split(','):
                val = val.strip()
                if val:
                    geographies.add(val)

        # Get all industry values and split comma-separated entries
        cursor = await self.conn.execute(
            "SELECT DISTINCT industry FROM securities WHERE industry IS NOT NULL AND industry != ''"
        )
        rows = await cursor.fetchall()
        for row in rows:
            for val in row['industry'].split(','):
                val = val.strip()
                if val:
                    industries.add(val)

        return {
            'geographies': list(geographies),
            'industries': list(industries),
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
        from datetime import datetime

        await self.conn.execute(
            """INSERT INTO job_history
               (job_id, job_type, status, error, duration_ms, executed_at, retry_count)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (job_id, job_type, status, error, duration_ms,
             int(datetime.now().timestamp()), retry_count)
        )
        await self.conn.commit()

    async def get_last_job_completion(self, job_type: str) -> Optional['datetime']:
        """Get the timestamp of the last successful completion for a job type."""
        from datetime import datetime

        cursor = await self.conn.execute(
            """SELECT executed_at FROM job_history
               WHERE job_type = ? AND status = 'completed'
               ORDER BY executed_at DESC LIMIT 1""",
            (job_type,)
        )
        row = await cursor.fetchone()
        if row:
            return datetime.fromtimestamp(row['executed_at'])
        return None

    async def get_last_job_completion_by_id(self, job_id: str) -> Optional['datetime']:
        """Get the timestamp of the last successful completion for a specific job ID.

        Use this for parameterized jobs like ML jobs where job_id includes the symbol.
        """
        from datetime import datetime

        cursor = await self.conn.execute(
            """SELECT executed_at FROM job_history
               WHERE job_id = ? AND status = 'completed'
               ORDER BY executed_at DESC LIMIT 1""",
            (job_id,)
        )
        row = await cursor.fetchone()
        if row:
            return datetime.fromtimestamp(row['executed_at'])
        return None

    async def is_job_completed(self, job_id: str) -> bool:
        """Check if a specific job has ever completed successfully."""
        cursor = await self.conn.execute(
            """SELECT 1 FROM job_history
               WHERE job_id = ? AND status = 'completed' LIMIT 1""",
            (job_id,)
        )
        return await cursor.fetchone() is not None

    async def get_job_history(self, limit: int = 50) -> list[dict]:
        """Get recent job execution history."""
        cursor = await self.conn.execute(
            """SELECT job_id, job_type, status, error, duration_ms,
                      executed_at, retry_count
               FROM job_history
               ORDER BY executed_at DESC LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_ml_enabled_securities(self) -> list[dict]:
        """Get securities with ML enabled."""
        cursor = await self.conn.execute(
            "SELECT symbol FROM securities WHERE ml_enabled = 1 AND active = 1"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # -------------------------------------------------------------------------
    # Job Schedules
    # -------------------------------------------------------------------------

    async def get_job_schedules(self) -> list[dict]:
        """Get all job schedules."""
        cursor = await self.conn.execute(
            "SELECT * FROM job_schedules ORDER BY category, job_type"
        )
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
        from datetime import datetime

        cursor = await self.conn.execute(
            "SELECT last_run, interval_minutes, interval_market_open_minutes, consecutive_failures FROM job_schedules WHERE job_type = ?",
            (job_type,)
        )
        row = await cursor.fetchone()
        if row is None:
            return False  # Unknown job

        last_run = row['last_run'] or 0
        consecutive_failures = row['consecutive_failures'] or 0

        # Determine interval based on failure count
        if 0 < consecutive_failures < 3:
            # Exponential backoff: 2^failures minutes (2, 4 minutes)
            interval = 2 ** consecutive_failures
        else:
            # Normal interval (no failures, or >= 3 failures)
            interval = row['interval_minutes']
            if market_open and row['interval_market_open_minutes']:
                interval = row['interval_market_open_minutes']

        if last_run == 0:
            return True  # Never run or forced = expired

        return int(datetime.now().timestamp()) - last_run >= interval * 60

    async def set_job_last_run(self, job_type: str, timestamp: int) -> None:
        """
        Set the last run timestamp for a job.
        Used to force a job to run by setting timestamp to 0.
        """
        await self.conn.execute(
            "UPDATE job_schedules SET last_run = ? WHERE job_type = ?",
            (timestamp, job_type)
        )
        await self.conn.commit()

    async def mark_job_completed(self, job_type: str) -> None:
        """Mark a job as completed (update last_run to now, reset failures)."""
        from datetime import datetime

        now = int(datetime.now().timestamp())
        await self.conn.execute(
            "UPDATE job_schedules SET last_run = ?, consecutive_failures = 0 WHERE job_type = ?",
            (now, job_type)
        )
        await self.conn.commit()

    async def mark_job_failed(self, job_type: str) -> None:
        """Mark a job as failed (increment failures, update last_run for backoff)."""
        from datetime import datetime

        now = int(datetime.now().timestamp())
        await self.conn.execute(
            "UPDATE job_schedules SET last_run = ?, consecutive_failures = consecutive_failures + 1 WHERE job_type = ?",
            (now, job_type)
        )
        await self.conn.commit()

    async def get_job_schedule(self, job_type: str) -> dict | None:
        """Get a single job schedule by type."""
        cursor = await self.conn.execute(
            "SELECT * FROM job_schedules WHERE job_type = ?",
            (job_type,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def upsert_job_schedule(
        self,
        job_type: str,
        enabled: bool | None = None,
        interval_minutes: int | None = None,
        interval_market_open_minutes: int | None = None,
        market_timing: int | None = None,
        dependencies: str | None = None,
        description: str | None = None,
        category: str | None = None,
        is_parameterized: bool | None = None,
        parameter_source: str | None = None,
        parameter_field: str | None = None,
    ) -> None:
        """Insert or update a job schedule."""
        from datetime import datetime

        now = int(datetime.now().timestamp())

        existing = await self.get_job_schedule(job_type)
        if existing:
            # Build update query with only provided fields
            updates = []
            params = []
            if enabled is not None:
                updates.append("enabled = ?")
                params.append(1 if enabled else 0)
            if interval_minutes is not None:
                updates.append("interval_minutes = ?")
                params.append(interval_minutes)
            if interval_market_open_minutes is not None:
                updates.append("interval_market_open_minutes = ?")
                params.append(interval_market_open_minutes)
            if market_timing is not None:
                updates.append("market_timing = ?")
                params.append(market_timing)
            if dependencies is not None:
                updates.append("dependencies = ?")
                params.append(dependencies)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if category is not None:
                updates.append("category = ?")
                params.append(category)
            if is_parameterized is not None:
                updates.append("is_parameterized = ?")
                params.append(1 if is_parameterized else 0)
            if parameter_source is not None:
                updates.append("parameter_source = ?")
                params.append(parameter_source)
            if parameter_field is not None:
                updates.append("parameter_field = ?")
                params.append(parameter_field)

            updates.append("updated_at = ?")
            params.append(now)
            params.append(job_type)

            await self.conn.execute(
                f"UPDATE job_schedules SET {', '.join(updates)} WHERE job_type = ?",
                params
            )
        else:
            await self.conn.execute(
                """INSERT INTO job_schedules
                   (job_type, enabled, interval_minutes, interval_market_open_minutes,
                    market_timing, dependencies, description, category,
                    is_parameterized, parameter_source, parameter_field,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (job_type, 1 if enabled else 0 if enabled is not None else 1,
                 interval_minutes or 60, interval_market_open_minutes,
                 market_timing or 0, dependencies or '[]', description, category,
                 1 if is_parameterized else 0, parameter_source, parameter_field,
                 now, now)
            )
        await self.conn.commit()

    async def seed_default_job_schedules(self) -> None:
        """Seed default job schedules if table is empty."""
        cursor = await self.conn.execute("SELECT COUNT(*) FROM job_schedules")
        count = (await cursor.fetchone())[0]
        if count > 0:
            return

        from datetime import datetime
        now = int(datetime.now().timestamp())

        # Default job schedules
        # (job_type, interval, interval_open, timing, category, description, is_param, param_source, param_field)
        defaults = [
            ('sync:portfolio', 30, 5, 0, 'sync', 'Sync portfolio positions from broker', False, None, None),
            ('sync:prices', 30, 5, 0, 'sync', 'Sync historical prices for securities', False, None, None),
            ('sync:quotes', 1440, 1440, 0, 'sync', 'Sync current quotes', False, None, None),
            ('sync:metadata', 1440, 1440, 0, 'sync', 'Sync security metadata', False, None, None),
            ('sync:exchange_rates', 60, 60, 0, 'sync', 'Sync exchange rates', False, None, None),
            ('scoring:calculate', 1440, 1440, 0, 'scoring', 'Calculate security scores', False, None, None),
            ('analytics:correlation', 10080, 10080, 3, 'analytics', 'Update correlation matrices', False, None, None),
            ('analytics:regime', 10080, 10080, 3, 'analytics', 'Train regime detection model', False, None, None),
            ('analytics:transfer_entropy', 10080, 10080, 3, 'analytics', 'Calculate transfer entropy', False, None, None),
            ('trading:check_markets', 30, 30, 2, 'trading', 'Check which markets are open', False, None, None),
            ('trading:execute', 30, 15, 2, 'trading', 'Execute pending trade recommendations', False, None, None),
            ('planning:refresh', 60, 30, 0, 'trading', 'Refresh trading plan and recommendations', False, None, None),
            ('ml:retrain', 10080, 10080, 3, 'ml', 'Retrain ML models', True, 'ml_enabled_securities', 'symbol'),
            ('ml:monitor', 10080, 10080, 0, 'ml', 'Monitor ML performance', True, 'ml_enabled_securities', 'symbol'),
        ]

        for job_type, interval, interval_open, timing, cat, desc, is_param, param_src, param_field in defaults:
            await self.conn.execute(
                """INSERT INTO job_schedules
                   (job_type, enabled, interval_minutes, interval_market_open_minutes,
                    market_timing, dependencies, description, category,
                    is_parameterized, parameter_source, parameter_field,
                    created_at, updated_at)
                   VALUES (?, 1, ?, ?, ?, '[]', ?, ?, ?, ?, ?, ?, ?)""",
                (job_type, interval, interval_open, timing, desc, cat,
                 1 if is_param else 0, param_src, param_field, now, now)
            )
        await self.conn.commit()

    async def get_last_job_completion_by_prefix(self, prefix: str) -> Optional['datetime']:
        """Get most recent completion time for jobs matching prefix."""
        from datetime import datetime

        cursor = await self.conn.execute(
            """SELECT executed_at FROM job_history
               WHERE job_id LIKE ? AND status = 'completed'
               ORDER BY executed_at DESC LIMIT 1""",
            (prefix + '%',)
        )
        row = await cursor.fetchone()
        return datetime.fromtimestamp(row['executed_at']) if row else None

    async def get_job_history_for_type(self, job_type: str, limit: int = 50) -> list[dict]:
        """Get job history for jobs matching type prefix."""
        cursor = await self.conn.execute(
            """SELECT job_id, job_type, status, error, duration_ms, executed_at, retry_count
               FROM job_history
               WHERE job_id LIKE ?
               ORDER BY executed_at DESC LIMIT ?""",
            (job_type + '%', limit)
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

    async def _apply_migrations(self) -> None:
        """Apply schema migrations for existing tables."""
        # Get existing columns in securities table
        cursor = await self.conn.execute("PRAGMA table_info(securities)")
        columns = {row[1] for row in await cursor.fetchall()}

        # Add missing columns
        migrations = [
            ("market_id", "ALTER TABLE securities ADD COLUMN market_id TEXT"),
            ("data", "ALTER TABLE securities ADD COLUMN data TEXT"),
            ("last_synced", "ALTER TABLE securities ADD COLUMN last_synced TEXT"),
            ("user_multiplier", "ALTER TABLE securities ADD COLUMN user_multiplier REAL DEFAULT 1.0"),
            ("ml_enabled", "ALTER TABLE securities ADD COLUMN ml_enabled INTEGER DEFAULT 0"),
            ("ml_blend_ratio", "ALTER TABLE securities ADD COLUMN ml_blend_ratio REAL DEFAULT 0.5"),
            ("quote_data", "ALTER TABLE securities ADD COLUMN quote_data TEXT"),
            ("quote_updated_at", "ALTER TABLE securities ADD COLUMN quote_updated_at INTEGER"),
        ]

        for col_name, sql in migrations:
            if col_name not in columns:
                await self.conn.execute(sql)

        # Create advanced analytics tables
        await self.conn.executescript("""
        -- Regime detection
        CREATE TABLE IF NOT EXISTS regime_states (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            regime INTEGER NOT NULL,
            regime_name TEXT,
            confidence REAL,
            PRIMARY KEY (symbol, date)
        );

        CREATE TABLE IF NOT EXISTS regime_models (
            model_id TEXT PRIMARY KEY,
            symbols TEXT,
            n_states INTEGER,
            trained_at TEXT,
            model_params TEXT
        );

        -- Transfer entropy
        CREATE TABLE IF NOT EXISTS transfer_entropy (
            source_symbol TEXT NOT NULL,
            target_symbol TEXT NOT NULL,
            te_value REAL NOT NULL,
            calculated_at TEXT,
            lag INTEGER,
            PRIMARY KEY (source_symbol, target_symbol)
        );

        -- Correlation matrices
        CREATE TABLE IF NOT EXISTS correlation_matrices (
            matrix_id TEXT PRIMARY KEY,
            matrix_type TEXT,
            symbols TEXT,
            matrix_data TEXT,
            calculated_at TEXT,
            n_symbols INTEGER,
            q_ratio REAL
        );

        -- Optimization results
        CREATE TABLE IF NOT EXISTS optimization_results (
            run_id TEXT PRIMARY KEY,
            method TEXT,
            symbols TEXT,
            allocations TEXT,
            expected_return REAL,
            expected_risk REAL,
            sharpe_ratio REAL,
            created_at TEXT
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_regime_symbol_date ON regime_states(symbol, date DESC);
        CREATE INDEX IF NOT EXISTS idx_te_target ON transfer_entropy(target_symbol, te_value DESC);
        CREATE INDEX IF NOT EXISTS idx_corr_type ON correlation_matrices(matrix_type, calculated_at DESC);

        -- ML Per-Security Prediction Tables
        -- 14 features per security - no cross-security contamination
        CREATE TABLE IF NOT EXISTS ml_training_samples (
            sample_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            sample_date TEXT NOT NULL,
            return_1d REAL,
            return_5d REAL,
            return_20d REAL,
            return_60d REAL,
            price_normalized REAL,
            volatility_10d REAL,
            volatility_30d REAL,
            atr_14d REAL,
            volume_normalized REAL,
            volume_trend REAL,
            rsi_14 REAL,
            macd REAL,
            bollinger_position REAL,
            sentiment_score REAL,
            future_return REAL,
            prediction_horizon_days INTEGER,
            created_at TEXT,
            UNIQUE(symbol, sample_date)
        );

        -- Per-symbol ML models (one model per symbol, overwritten on retrain)
        CREATE TABLE IF NOT EXISTS ml_models (
            symbol TEXT PRIMARY KEY,
            training_samples INTEGER,
            validation_rmse REAL,
            validation_mae REAL,
            validation_r2 REAL,
            last_trained_at TEXT
        );

        CREATE TABLE IF NOT EXISTS ml_predictions (
            prediction_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            model_version TEXT,
            predicted_at TEXT,
            features TEXT,
            predicted_return REAL,
            ml_score REAL,
            wavelet_score REAL,
            blend_ratio REAL,
            final_score REAL,
            inference_time_ms REAL
        );

        -- Per-symbol ML performance tracking
        CREATE TABLE IF NOT EXISTS ml_performance_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            tracked_at TEXT NOT NULL,
            mean_absolute_error REAL,
            root_mean_squared_error REAL,
            prediction_bias REAL,
            drift_detected INTEGER DEFAULT 0,
            predictions_evaluated INTEGER DEFAULT 0,
            UNIQUE(symbol, tracked_at)
        );

        -- ML Indexes
        CREATE INDEX IF NOT EXISTS idx_ml_samples_symbol_date ON ml_training_samples(symbol, sample_date DESC);
        CREATE INDEX IF NOT EXISTS idx_ml_predictions_symbol_date ON ml_predictions(symbol, predicted_at DESC);
        CREATE INDEX IF NOT EXISTS idx_ml_perf_symbol ON ml_performance_tracking(symbol, tracked_at DESC);

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
            enabled INTEGER DEFAULT 1,
            interval_minutes INTEGER NOT NULL,
            interval_market_open_minutes INTEGER,
            market_timing INTEGER DEFAULT 0,
            dependencies TEXT DEFAULT '[]',
            description TEXT,
            category TEXT,
            is_parameterized INTEGER DEFAULT 0,
            parameter_source TEXT,
            parameter_field TEXT,
            last_run INTEGER DEFAULT 0,
            consecutive_failures INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_job_schedules_category ON job_schedules(category, job_type);
        """)

        # Migration: add last_run column to job_schedules if missing
        cursor = await self.conn.execute("PRAGMA table_info(job_schedules)")
        columns = {row[1] for row in await cursor.fetchall()}
        if 'last_run' not in columns:
            await self.conn.execute(
                "ALTER TABLE job_schedules ADD COLUMN last_run INTEGER DEFAULT 0"
            )
        if 'consecutive_failures' not in columns:
            await self.conn.execute(
                "ALTER TABLE job_schedules ADD COLUMN consecutive_failures INTEGER DEFAULT 0"
            )


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
    data TEXT,  -- Raw Tradernet API response (JSON)
    last_synced TEXT,
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

-- Trade history
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL')),
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    executed_at TEXT NOT NULL,
    order_id TEXT,
    FOREIGN KEY (symbol) REFERENCES securities(symbol)
);

-- Allocation targets (weights, not percentages)
CREATE TABLE IF NOT EXISTS allocation_targets (
    type TEXT NOT NULL CHECK(type IN ('geography', 'industry')),
    name TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (type, name)
);

-- Scores (calculated metrics for each security)
CREATE TABLE IF NOT EXISTS scores (
    symbol TEXT PRIMARY KEY,
    score REAL,
    components TEXT,  -- JSON with breakdown
    calculated_at TEXT,
    FOREIGN KEY (symbol) REFERENCES securities(symbol)
);

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

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_prices_symbol_date ON prices(symbol, date);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades(executed_at);
CREATE INDEX IF NOT EXISTS idx_cache_expires_at ON cache(expires_at);
"""
