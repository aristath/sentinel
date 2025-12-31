"""Portfolio module database schemas."""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Positions table (part of state.db)
POSITIONS_SCHEMA = """
-- Current positions (derived from ledger, can be rebuilt)
CREATE TABLE IF NOT EXISTS positions (
    symbol TEXT PRIMARY KEY,
    isin TEXT,                   -- ISIN for broker-agnostic identification
    quantity REAL NOT NULL,
    avg_price REAL NOT NULL,
    current_price REAL,
    currency TEXT DEFAULT 'EUR',
    currency_rate REAL DEFAULT 1.0,
    market_value_eur REAL,
    cost_basis_eur REAL,
    unrealized_pnl REAL,
    unrealized_pnl_pct REAL,
    last_updated TEXT,
    first_bought_at TEXT,
    last_sold_at TEXT
);
"""

# Portfolio snapshots (snapshots.db)
SNAPSHOTS_SCHEMA = """
-- Portfolio snapshots (daily summary)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    date TEXT PRIMARY KEY,
    total_value REAL NOT NULL,
    cash_balance REAL NOT NULL,
    invested_value REAL,
    unrealized_pnl REAL,
    geo_eu_pct REAL,
    geo_asia_pct REAL,
    geo_us_pct REAL,
    position_count INTEGER,
    annual_turnover REAL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_date ON portfolio_snapshots(date);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);
"""

# History schema (per-symbol databases)
HISTORY_SCHEMA = """
-- Daily price data
CREATE TABLE IF NOT EXISTS daily_prices (
    date TEXT PRIMARY KEY,
    open_price REAL,
    high_price REAL,
    low_price REAL,
    close_price REAL NOT NULL,
    volume INTEGER,
    source TEXT DEFAULT 'yahoo',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_prices(date);

-- Monthly aggregates (for CAGR calculations)
CREATE TABLE IF NOT EXISTS monthly_prices (
    year_month TEXT PRIMARY KEY,  -- 'YYYY-MM' format
    avg_close REAL NOT NULL,
    avg_adj_close REAL,
    min_price REAL,
    max_price REAL,
    source TEXT DEFAULT 'calculated',
    created_at TEXT NOT NULL
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);
"""


async def init_history_schema(db):
    """Initialize per-symbol history database schema."""
    await db.executescript(HISTORY_SCHEMA)

    row = await db.fetchone("SELECT MAX(version) as v FROM schema_version")
    current_version = row["v"] if row and row["v"] else 0

    if current_version == 0:
        now = datetime.now().isoformat()
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (1, now, "Initial history schema"),
        )
        await db.commit()
        logger.info("History database initialized with schema version 1")


async def init_snapshots_schema(db):
    """Initialize snapshots database schema."""
    await db.executescript(SNAPSHOTS_SCHEMA)

    row = await db.fetchone("SELECT MAX(version) as v FROM schema_version")
    current_version = row["v"] if row and row["v"] else 0

    if current_version == 0:
        now = datetime.now().isoformat()
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (1, now, "Initial snapshots schema"),
        )
        await db.commit()
        logger.info("Snapshots database initialized with schema version 1")
        current_version = 1

    # Migration: Add annual_turnover column (version 1 -> 2)
    if current_version == 1:
        try:
            now = datetime.now().isoformat()
            logger.info(
                "Migrating snapshots database to schema version 2 (annual_turnover)..."
            )

            cursor = await db.execute("PRAGMA table_info(portfolio_snapshots)")
            columns = [row[1] for row in await cursor.fetchall()]

            if "annual_turnover" not in columns:
                await db.execute(
                    "ALTER TABLE portfolio_snapshots ADD COLUMN annual_turnover REAL"
                )
                await db.execute(
                    "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                    (
                        2,
                        now,
                        "Added annual_turnover column for portfolio turnover tracking",
                    ),
                )
            await db.commit()
            logger.info("Snapshots database migrated to schema version 2")
        except Exception as e:
            logger.error(f"Failed to migrate snapshots schema to version 2: {e}")
            await db.rollback()
