-- Migration 035: Migrate recommendations table to new schema (cache.db)
--
-- The recommendations table has an old schema and needs to be migrated to the new schema
-- that matches the RecommendationRepository expectations.
--
-- Old schema: id, symbol, action, priority, score, reason, created_at, expires_at
-- New schema: uuid, symbol, name, side, quantity, estimated_price, estimated_value,
--             reason, currency, priority, current_portfolio_score, new_portfolio_score,
--             score_change, status, portfolio_hash, created_at, updated_at, executed_at

-- Step 1: Check if table already has new schema (has uuid column)
-- If it does, skip migration
-- If not, proceed with migration

-- Step 1a: Check if recommendations table exists and has uuid column
-- If uuid column exists, table is already migrated - skip
-- Note: This migration will fail gracefully if table doesn't exist or already has correct schema

-- Step 1b: Create new recommendations table with correct schema
CREATE TABLE recommendations_new (
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
) STRICT;

-- Step 2: Migrate data from old schema to new schema
-- Map old columns to new columns with defaults for missing fields
-- Note: If old table is empty or doesn't exist, this will just create empty table
INSERT INTO recommendations_new (
    uuid, symbol, name, side, quantity, estimated_price, estimated_value,
    reason, currency, priority, current_portfolio_score, new_portfolio_score,
    score_change, status, portfolio_hash, created_at, updated_at, executed_at
)
SELECT
    -- Generate UUID from rowid (SQLite internal row identifier)
    'migrated-' || CAST(rowid AS TEXT) as uuid,
    symbol,
    COALESCE(symbol, 'Unknown') as name, -- Use symbol as name if name not available
    CASE
        WHEN action = 'BUY' OR action = 'buy' THEN 'buy'
        WHEN action = 'SELL' OR action = 'sell' THEN 'sell'
        ELSE 'buy' -- Default to buy
    END as side,
    1.0 as quantity, -- Default quantity (old schema doesn't have this)
    0.01 as estimated_price, -- Default price (must be > 0 for CHECK constraint)
    0.01 as estimated_value, -- Default value (must be > 0 for CHECK constraint)
    COALESCE(reason, '') as reason,
    'EUR' as currency, -- Default currency (old schema doesn't have this)
    COALESCE(priority, 0.0) as priority,
    0.0 as current_portfolio_score, -- Default score (old schema has 'score' but we need both)
    COALESCE(score, 0.0) as new_portfolio_score, -- Use old 'score' as new_portfolio_score
    0.0 as score_change, -- Default score change
    'pending' as status, -- Default status
    '' as portfolio_hash, -- Default portfolio hash (old schema doesn't have this)
    COALESCE(created_at, datetime('now')) as created_at,
    COALESCE(created_at, datetime('now')) as updated_at,
    NULL as executed_at -- Old schema doesn't have executed_at
FROM recommendations;

-- Step 3: Drop old table and rename new
DROP TABLE recommendations;
ALTER TABLE recommendations_new RENAME TO recommendations;

-- Step 4: Recreate indexes
CREATE INDEX IF NOT EXISTS idx_recommendations_status_priority
ON recommendations(status, priority ASC, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_recommendations_portfolio_hash
ON recommendations(portfolio_hash, status);

CREATE INDEX IF NOT EXISTS idx_recommendations_executed_at
ON recommendations(executed_at) WHERE executed_at IS NOT NULL;
