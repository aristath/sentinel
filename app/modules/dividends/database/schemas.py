"""Dividends module database schemas."""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DIVIDENDS_SCHEMA = """
-- Dividend history with DRIP tracking
-- Tracks dividend payments and whether they were reinvested.
-- pending_bonus: If dividend couldn't be reinvested (too small), store a bonus
-- that the optimizer will apply to that security's expected return.
CREATE TABLE IF NOT EXISTS dividend_history (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    isin TEXT,                       -- ISIN for broker-agnostic identification
    cash_flow_id INTEGER,            -- Link to cash_flows table in ledger.db (optional)
    amount REAL NOT NULL,            -- Original dividend amount
    currency TEXT NOT NULL,
    amount_eur REAL NOT NULL,        -- Converted amount in EUR
    payment_date TEXT NOT NULL,
    reinvested INTEGER DEFAULT 0,    -- 0 = not reinvested, 1 = reinvested
    reinvested_at TEXT,              -- When reinvestment trade executed
    reinvested_quantity INTEGER,     -- Shares bought with dividend
    pending_bonus REAL DEFAULT 0,    -- Bonus to apply to expected return (0.0 to 1.0)
    bonus_cleared INTEGER DEFAULT 0, -- 1 when bonus has been used
    cleared_at TEXT,                 -- When bonus was cleared
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dividend_history_symbol ON dividend_history(symbol);
-- Note: idx_dividend_history_isin is created in migration or init_dividends_schema
CREATE INDEX IF NOT EXISTS idx_dividend_history_date ON dividend_history(payment_date);
CREATE INDEX IF NOT EXISTS idx_dividend_history_pending ON dividend_history(pending_bonus)
    WHERE pending_bonus > 0;

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);
"""


async def init_dividends_schema(db):
    """Initialize dividends database schema."""
    await db.executescript(DIVIDENDS_SCHEMA)

    row = await db.fetchone("SELECT MAX(version) as v FROM schema_version")
    current_version = row["v"] if row and row["v"] else 0

    if current_version == 0:
        now = datetime.now().isoformat()
        # Create ISIN index for new databases
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_dividend_history_isin ON dividend_history(isin)"
        )
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (2, now, "Initial dividends schema with ISIN column"),
        )
        await db.commit()
        logger.info("Dividends database schema initialized with version 2")
    else:
        await db.commit()
        logger.info("Dividends database schema initialized")
