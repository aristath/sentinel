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
        
        await db.commit()


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
    active INTEGER DEFAULT 1
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
"""
