"""Planning module database schemas."""

import logging

logger = logging.getLogger(__name__)

PLANNER_SCHEMA = """
-- Sequences table: tracks all candidate sequences
CREATE TABLE IF NOT EXISTS sequences (
    sequence_hash TEXT NOT NULL,
    portfolio_hash TEXT NOT NULL,
    priority REAL NOT NULL,
    sequence_json TEXT NOT NULL,  -- JSON serialized List[ActionCandidate]
    depth INTEGER NOT NULL,       -- Sequence depth (1-5)
    pattern_type TEXT,            -- Pattern that generated this (e.g., 'direct_buy', 'combinatorial')
    completed INTEGER DEFAULT 0,  -- 0 = not evaluated, 1 = evaluated
    evaluated_at TEXT,            -- ISO timestamp when evaluated (NULL if not evaluated)
    created_at TEXT NOT NULL,
    PRIMARY KEY (sequence_hash, portfolio_hash)
);

CREATE INDEX IF NOT EXISTS idx_sequences_portfolio ON sequences(portfolio_hash);
CREATE INDEX IF NOT EXISTS idx_sequences_priority ON sequences(portfolio_hash, priority DESC, completed);
CREATE INDEX IF NOT EXISTS idx_sequences_completed ON sequences(portfolio_hash, completed);

-- Evaluations table: stores evaluation results
CREATE TABLE IF NOT EXISTS evaluations (
    sequence_hash TEXT NOT NULL,
    portfolio_hash TEXT NOT NULL,
    end_score REAL NOT NULL,
    breakdown_json TEXT NOT NULL,  -- JSON serialized score breakdown
    end_cash REAL NOT NULL,
    end_context_positions_json TEXT NOT NULL,  -- JSON serialized Dict[str, float]
    div_score REAL NOT NULL,      -- Diversification score
    total_value REAL NOT NULL,    -- Total portfolio value after sequence
    evaluated_at TEXT NOT NULL,
    PRIMARY KEY (sequence_hash, portfolio_hash)
);

CREATE INDEX IF NOT EXISTS idx_evaluations_portfolio ON evaluations(portfolio_hash);
CREATE INDEX IF NOT EXISTS idx_evaluations_score ON evaluations(portfolio_hash, end_score DESC);

-- Best result table: tracks best sequence found so far
CREATE TABLE IF NOT EXISTS best_result (
    portfolio_hash TEXT PRIMARY KEY,
    best_sequence_hash TEXT NOT NULL,
    best_score REAL NOT NULL,
    updated_at TEXT NOT NULL
);
"""


async def init_planner_schema(db):
    """Initialize planner database schema."""
    import logging

    logger = logging.getLogger(__name__)
    await db.executescript(PLANNER_SCHEMA)
    await db.commit()
    logger.info("Planner database schema initialized")
