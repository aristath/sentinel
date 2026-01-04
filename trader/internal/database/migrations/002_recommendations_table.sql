-- Recommendations table for storing trading plan recommendations
-- Used by PlannerBatchJob to store generated plans
-- Used by EventBasedTradingJob to fetch and execute pending recommendations

CREATE TABLE IF NOT EXISTS recommendations (
    uuid TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity REAL NOT NULL CHECK (quantity > 0),
    estimated_price REAL NOT NULL CHECK (estimated_price > 0),
    estimated_value REAL NOT NULL,
    reason TEXT NOT NULL,
    currency TEXT NOT NULL,
    priority REAL NOT NULL,
    current_portfolio_score REAL NOT NULL,
    new_portfolio_score REAL NOT NULL,
    score_change REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'executed', 'rejected', 'expired')),
    portfolio_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    executed_at TEXT
);

-- Index for fetching pending recommendations ordered by priority
CREATE INDEX IF NOT EXISTS idx_recommendations_status_priority
ON recommendations(status, priority ASC, created_at ASC);

-- Index for filtering by portfolio hash and status
CREATE INDEX IF NOT EXISTS idx_recommendations_portfolio_hash
ON recommendations(portfolio_hash, status);

-- Index for executed_at lookups
CREATE INDEX IF NOT EXISTS idx_recommendations_executed_at
ON recommendations(executed_at) WHERE executed_at IS NOT NULL;
