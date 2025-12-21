"""SQLite database connection and initialization."""

import aiosqlite
from pathlib import Path
from app.config import settings


async def get_db():
    """Get database connection."""
    db = await aiosqlite.connect(settings.database_path)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    """Initialize database with schema."""
    # Ensure data directory exists
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(settings.database_path) as db:
        await db.executescript(SCHEMA)
        await db.commit()


SCHEMA = """
-- Stock universe
CREATE TABLE IF NOT EXISTS stocks (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    industry TEXT NOT NULL,
    geography TEXT NOT NULL,
    active INTEGER DEFAULT 1
);

-- Current positions
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    quantity REAL NOT NULL,
    avg_price REAL NOT NULL,
    current_price REAL,
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
INSERT OR IGNORE INTO allocation_targets (type, name, target_pct) VALUES
    ('geography', 'EU', 0.50),
    ('geography', 'ASIA', 0.30),
    ('geography', 'US', 0.20),
    ('industry', 'Technology', 0.20),
    ('industry', 'Healthcare', 0.20),
    ('industry', 'Finance', 0.20),
    ('industry', 'Consumer', 0.20),
    ('industry', 'Industrial', 0.20);
"""
