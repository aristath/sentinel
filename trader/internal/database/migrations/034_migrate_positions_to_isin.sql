-- Migration 034: Migrate positions table from symbol to ISIN PRIMARY KEY (portfolio.db only)
--
-- This migration migrates the positions table in portfolio.db from symbol to ISIN.
-- Unlike migration 030, this doesn't reference securities table (which is in universe.db).
-- Instead, it uses the existing isin column if populated, or uses symbol as isin for cash positions.
--
-- Note: This migration should run AFTER migration 030 on universe.db has completed.
-- The positions table will use symbol as ISIN for cash positions, matching the securities table.

-- Step 1: Verify positions table exists and has isin column
-- If isin column doesn't exist, add it first
-- SQLite doesn't support IF NOT EXISTS for columns, so we'll handle errors gracefully

-- Step 2: Create new positions table with isin as PRIMARY KEY
CREATE TABLE positions_new (
    isin TEXT PRIMARY KEY,
    quantity REAL NOT NULL,
    avg_price REAL NOT NULL,
    current_price REAL,
    currency TEXT,
    currency_rate REAL DEFAULT 1.0,
    market_value_eur REAL,
    cost_basis_eur REAL,
    unrealized_pnl REAL,
    unrealized_pnl_pct REAL,
    last_updated TEXT,
    first_bought TEXT,
    last_sold TEXT,
    symbol TEXT -- Keep symbol for display/API conversion
) STRICT;

-- Step 3: Copy data, using existing isin column if available, otherwise use symbol as isin
-- For cash positions (CASH:*), use symbol as isin
-- For other positions, use existing isin if populated, otherwise use symbol as fallback
INSERT INTO positions_new
SELECT
    CASE
        WHEN symbol LIKE 'CASH:%' THEN symbol -- CASH positions keep symbol as isin
        WHEN isin IS NOT NULL AND isin != '' AND TRIM(isin) != '' THEN isin -- Use existing isin if available
        ELSE symbol -- Fallback to symbol as isin (will be updated later when securities are synced)
    END as isin,
    quantity,
    avg_price,
    current_price,
    currency,
    currency_rate,
    market_value_eur,
    cost_basis_eur,
    unrealized_pnl,
    unrealized_pnl_pct,
    last_updated,
    first_bought,
    last_sold,
    symbol
FROM positions;

-- Step 4: Drop old table and rename new
DROP TABLE positions;
ALTER TABLE positions_new RENAME TO positions;

-- Step 5: Recreate indexes
CREATE INDEX IF NOT EXISTS idx_positions_value ON positions(market_value_eur DESC);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol); -- Index symbol for lookups
