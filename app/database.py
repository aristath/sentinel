"""SQLite database connection and initialization."""

import logging
import aiosqlite
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
from app.config import settings

logger = logging.getLogger(__name__)


async def get_db():
    """Get database connection."""
    db = await aiosqlite.connect(settings.database_path)
    db.row_factory = aiosqlite.Row
    # Enable WAL mode for better concurrency and busy timeout for retries
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=30000")  # 30 seconds
    try:
        yield db
    finally:
        await db.close()


@asynccontextmanager
async def transaction(db: aiosqlite.Connection) -> AsyncIterator[aiosqlite.Connection]:
    """
    Transaction context manager for atomic operations.
    
    Usage:
        async with transaction(db) as tx_db:
            # All operations are atomic
            await repo1.create(...)
            await repo2.update(...)
            # Commits on success, rolls back on exception
    """
    savepoint_id = f"sp_{id(db)}"
    try:
        await db.execute(f"SAVEPOINT {savepoint_id}")
        yield db
        await db.execute(f"RELEASE SAVEPOINT {savepoint_id}")
    except Exception:
        await db.execute(f"ROLLBACK TO SAVEPOINT {savepoint_id}")
        raise


async def init_db():
    """Initialize database with schema and version tracking."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Ensure data directory exists
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        # Enable WAL mode for better concurrency and busy timeout for retries
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=30000")  # 30 seconds

        # Create schema version table first
        await db.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL,
                description TEXT
            )
        """)
        
        # Get current schema version
        cursor = await db.execute("SELECT MAX(version) as max_version FROM schema_version")
        row = await cursor.fetchone()
        current_version = row["max_version"] if row and row["max_version"] is not None else 0
        
        # Apply schema
        await db.executescript(SCHEMA)
        
        # Record schema version if this is a new database
        if current_version == 0:
            from datetime import datetime
            await db.execute(
                "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                (1, datetime.now().isoformat(), "Initial schema")
            )
            logger.info("Database initialized with schema version 1")
            current_version = 1

        # Apply migrations
        await apply_migrations(db, current_version)

        await db.commit()


async def apply_migrations(db: aiosqlite.Connection, current_version: int):
    """Apply pending database migrations."""
    from datetime import datetime

    # Migration 2: Add new scoring columns for long-term value investing
    if current_version < 2:
        logger.info("Applying migration 2: Adding new scoring columns...")

        # Check if columns already exist (in case of partial migration)
        cursor = await db.execute("PRAGMA table_info(scores)")
        existing_columns = {row[1] for row in await cursor.fetchall()}

        new_columns = [
            ("quality_score", "REAL"),
            ("opportunity_score", "REAL"),
            ("allocation_fit_score", "REAL"),
            ("cagr_score", "REAL"),
            ("consistency_score", "REAL"),
            ("history_years", "REAL"),
        ]

        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                await db.execute(f"ALTER TABLE scores ADD COLUMN {col_name} {col_type}")
                logger.info(f"  Added column: scores.{col_name}")

        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (2, datetime.now().isoformat(), "Add new scoring columns for long-term value investing")
        )
        logger.info("Migration 2 complete")

    # Migration 3: Add stock price history cache table
    if current_version < 3:
        logger.info("Applying migration 3: Adding stock_price_history table...")

        # Check if table already exists (in case of partial migration)
        cursor = await db.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='stock_price_history'
        """)
        table_exists = await cursor.fetchone()

        if not table_exists:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stock_price_history (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    close_price REAL NOT NULL,
                    open_price REAL,
                    high_price REAL,
                    low_price REAL,
                    volume INTEGER,
                    source TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(symbol, date)
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_stock_price_symbol_date 
                ON stock_price_history(symbol, date)
            """)
            logger.info("  Created table: stock_price_history")
        else:
            logger.info("  Table stock_price_history already exists, skipping")

        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (3, datetime.now().isoformat(), "Add stock_price_history table for chart data caching")
        )
        logger.info("Migration 3 complete")

    # Migration 4: Add allow_buy/allow_sell to stocks, first_bought_at/last_sold_at to positions
    if current_version < 4:
        logger.info("Applying migration 4: Adding sell feature columns...")

        # Add columns to stocks table
        cursor = await db.execute("PRAGMA table_info(stocks)")
        stock_columns = {row[1] for row in await cursor.fetchall()}

        if 'allow_buy' not in stock_columns:
            await db.execute("ALTER TABLE stocks ADD COLUMN allow_buy INTEGER DEFAULT 1")
            logger.info("  Added column: stocks.allow_buy")
        if 'allow_sell' not in stock_columns:
            await db.execute("ALTER TABLE stocks ADD COLUMN allow_sell INTEGER DEFAULT 0")
            logger.info("  Added column: stocks.allow_sell")

        # Add columns to positions table
        cursor = await db.execute("PRAGMA table_info(positions)")
        pos_columns = {row[1] for row in await cursor.fetchall()}

        if 'first_bought_at' not in pos_columns:
            await db.execute("ALTER TABLE positions ADD COLUMN first_bought_at TEXT")
            logger.info("  Added column: positions.first_bought_at")
        if 'last_sold_at' not in pos_columns:
            await db.execute("ALTER TABLE positions ADD COLUMN last_sold_at TEXT")
            logger.info("  Added column: positions.last_sold_at")

        # Backfill first_bought_at from trades table for existing positions
        await db.execute("""
            UPDATE positions
            SET first_bought_at = (
                SELECT MIN(executed_at)
                FROM trades
                WHERE trades.symbol = positions.symbol AND trades.side = 'BUY'
            )
            WHERE first_bought_at IS NULL
        """)
        logger.info("  Backfilled first_bought_at from trade history")

        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (4, datetime.now().isoformat(), "Add sell feature columns: allow_buy, allow_sell, first_bought_at, last_sold_at")
        )
        logger.info("Migration 4 complete")


SCHEMA = """
-- Stock universe
CREATE TABLE IF NOT EXISTS stocks (
    symbol TEXT PRIMARY KEY,
    yahoo_symbol TEXT,
    name TEXT NOT NULL,
    industry TEXT,
    geography TEXT NOT NULL,
    priority_multiplier REAL DEFAULT 1,
    min_lot INTEGER DEFAULT 1,
    active INTEGER DEFAULT 1,
    allow_buy INTEGER DEFAULT 1,
    allow_sell INTEGER DEFAULT 0
);

-- Current positions
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    quantity REAL NOT NULL,
    avg_price REAL NOT NULL,
    current_price REAL,
    currency TEXT DEFAULT 'EUR',  -- Default currency (see app.domain.constants.DEFAULT_CURRENCY)
    currency_rate REAL DEFAULT 1.0,
    market_value_eur REAL,
    last_updated TEXT,
    first_bought_at TEXT,  -- Track when position was first opened
    last_sold_at TEXT,     -- Track last sell for cooldown
    FOREIGN KEY (symbol) REFERENCES stocks(symbol)
);

-- Trade history
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    executed_at TEXT NOT NULL,
    order_id TEXT,
    FOREIGN KEY (symbol) REFERENCES stocks(symbol)
);

-- Stock scores (cached)
CREATE TABLE IF NOT EXISTS scores (
    symbol TEXT PRIMARY KEY,
    technical_score REAL,
    analyst_score REAL,
    fundamental_score REAL,
    total_score REAL,
    volatility REAL,
    calculated_at TEXT,
    FOREIGN KEY (symbol) REFERENCES stocks(symbol)
);

-- Portfolio snapshots (daily)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL UNIQUE,
    total_value REAL NOT NULL,
    cash_balance REAL NOT NULL,
    geo_eu_pct REAL,
    geo_asia_pct REAL,
    geo_us_pct REAL
);

-- Allocation targets
CREATE TABLE IF NOT EXISTS allocation_targets (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    target_pct REAL NOT NULL,
    UNIQUE(type, name)
);

-- Insert default allocation targets
-- Note: Geography targets sum to 1.0 (100%), Industry targets also sum to 1.0 (100%)
INSERT OR IGNORE INTO allocation_targets (type, name, target_pct) VALUES
    ('geography', 'EU', 0.50),
    ('geography', 'ASIA', 0.30),
    ('geography', 'US', 0.20),
    ('industry', 'Technology', 0.20),
    ('industry', 'Healthcare', 0.20),
    ('industry', 'Finance', 0.20),
    ('industry', 'Consumer', 0.20),
    ('industry', 'Industrial', 0.20);

-- Settings (key-value store for app settings)
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Cash flow transactions
CREATE TABLE IF NOT EXISTS cash_flows (
    id INTEGER PRIMARY KEY,
    transaction_id TEXT UNIQUE NOT NULL,
    type_doc_id INTEGER NOT NULL,
    transaction_type TEXT,
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    amount_eur REAL NOT NULL,
    status TEXT,
    status_c INTEGER,
    description TEXT,
    params_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cash_flows_date ON cash_flows(date);
CREATE INDEX IF NOT EXISTS idx_cash_flows_type ON cash_flows(transaction_type);
CREATE INDEX IF NOT EXISTS idx_cash_flows_type_doc_id ON cash_flows(type_doc_id);

-- Stock price history cache
CREATE TABLE IF NOT EXISTS stock_price_history (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    close_price REAL NOT NULL,
    open_price REAL,
    high_price REAL,
    low_price REAL,
    volume INTEGER,
    source TEXT,  -- 'tradernet' or 'yahoo'
    created_at TEXT NOT NULL,
    UNIQUE(symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_stock_price_symbol_date ON stock_price_history(symbol, date);

-- Stock price monthly averages (for long-term CAGR calculations)
CREATE TABLE IF NOT EXISTS stock_price_monthly (
    symbol TEXT NOT NULL,
    year_month TEXT NOT NULL,  -- 'YYYY-MM' format
    avg_close REAL NOT NULL,
    avg_adj_close REAL,  -- Adjusted close for CAGR (accounts for splits/dividends)
    min_price REAL,
    max_price REAL,
    source TEXT,  -- 'yahoo', 'calculated', or 'tradernet'
    created_at TEXT NOT NULL,
    PRIMARY KEY (symbol, year_month)
);

CREATE INDEX IF NOT EXISTS idx_stock_price_monthly_symbol ON stock_price_monthly(symbol);
"""
