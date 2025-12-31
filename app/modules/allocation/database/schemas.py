"""Database schemas for allocation module."""

import logging

logger = logging.getLogger(__name__)

# Allocation targets (group-based weightings)
ALLOCATION_TARGETS_SCHEMA = """
CREATE TABLE IF NOT EXISTS allocation_targets (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,      -- 'country_group' or 'industry_group'
    name TEXT NOT NULL,
    target_pct REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(type, name)
);
"""


async def init_allocation_targets_schema(db):
    """Initialize allocation_targets table schema."""
    await db.executescript(ALLOCATION_TARGETS_SCHEMA)
    logger.debug("Allocation targets schema initialized")
