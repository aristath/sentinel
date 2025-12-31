"""Database schemas for cash flows module."""

import logging

logger = logging.getLogger(__name__)

# Cash flow transactions (append-only)
CASH_FLOWS_SCHEMA = """
CREATE TABLE IF NOT EXISTS cash_flows (
    id INTEGER PRIMARY KEY,
    transaction_id TEXT UNIQUE NOT NULL,
    type_doc_id INTEGER NOT NULL,
    transaction_type TEXT,       -- 'DEPOSIT', 'WITHDRAWAL', 'DIVIDEND', etc.
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    amount_eur REAL NOT NULL,
    status TEXT,
    status_c INTEGER,
    description TEXT,
    params_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cash_flows_date ON cash_flows(date);
CREATE INDEX IF NOT EXISTS idx_cash_flows_type ON cash_flows(transaction_type);
"""


async def init_cash_flows_schema(db):
    """Initialize cash flows table schema."""
    await db.executescript(CASH_FLOWS_SCHEMA)
    logger.debug("Cash flows schema initialized")
