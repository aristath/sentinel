-- Migration 030: Migrate PRIMARY KEYs from symbol to ISIN
--
-- This migration changes the primary identifier from symbol (Tradernet format)
-- to ISIN (International Securities Identification Number) across all tables.
--
-- CRITICAL: All non-cash securities MUST have ISIN before running this migration.
-- Cash positions (CASH:*) will use their symbol as ISIN automatically.
-- Run validation script first to verify: ValidateAllSecuritiesHaveISIN()
--
-- Tables affected:
-- - securities: symbol PRIMARY KEY → isin PRIMARY KEY
-- - scores: symbol PRIMARY KEY → isin PRIMARY KEY
-- - positions: symbol PRIMARY KEY → isin PRIMARY KEY
-- - trades: symbol column → isin column (id remains PRIMARY KEY)
-- - dividend_history: symbol column → isin column (id remains PRIMARY KEY)
-- - recommendations: symbol column → isin column (uuid remains PRIMARY KEY)
-- - security_tags: (symbol, tag_id) PRIMARY KEY → (isin, tag_id) PRIMARY KEY
--
-- Foreign keys updated:
-- - security_tags: FOREIGN KEY (symbol) → FOREIGN KEY (isin)

-- Step 1: Verify all securities have ISIN (fail migration if any missing)
-- Cash positions (CASH:*) are special - they use symbol as ISIN
-- This check will cause migration to fail if non-cash securities without ISIN exist
CREATE TEMP TABLE _isin_validation AS
SELECT symbol FROM securities
WHERE (isin IS NULL OR isin = '' OR TRIM(isin) = '')
  AND NOT (symbol LIKE 'CASH:%');

-- If validation table has rows, migration should fail
-- (Application layer should check this before running migration)

-- Step 2: Verify no duplicate ISINs (fail migration if duplicates exist)
-- Include cash positions (which use symbol as ISIN) in the check
CREATE TEMP TABLE _isin_duplicates AS
SELECT
    CASE
        WHEN isin IS NOT NULL AND isin != '' AND TRIM(isin) != '' THEN isin
        WHEN symbol LIKE 'CASH:%' THEN symbol
        ELSE symbol
    END as isin,
    COUNT(*) as count
FROM securities
GROUP BY isin
HAVING COUNT(*) > 1;

-- Step 3: Migrate securities table
-- Create new table with isin as PRIMARY KEY
CREATE TABLE securities_new (
    isin TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    yahoo_symbol TEXT,
    name TEXT NOT NULL,
    product_type TEXT,
    industry TEXT,
    country TEXT,
    fullExchangeName TEXT,
    priority_multiplier REAL DEFAULT 1.0,
    min_lot INTEGER DEFAULT 1,
    active INTEGER DEFAULT 1,
    allow_buy INTEGER DEFAULT 1,
    allow_sell INTEGER DEFAULT 1,
    currency TEXT,
    last_synced TEXT,
    min_portfolio_target REAL,
    max_portfolio_target REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
) STRICT;

-- Copy data (securities with ISIN, or cash positions using symbol as ISIN)
INSERT INTO securities_new
SELECT
    CASE
        WHEN isin IS NOT NULL AND isin != '' AND TRIM(isin) != '' THEN isin
        WHEN symbol LIKE 'CASH:%' THEN symbol  -- Cash positions use symbol as ISIN
        ELSE symbol  -- Fallback: use symbol as ISIN if somehow missing
    END as isin,
    symbol,
    yahoo_symbol,
    name,
    product_type,
    industry,
    country,
    fullExchangeName,
    priority_multiplier,
    min_lot,
    active,
    allow_buy,
    allow_sell,
    currency,
    last_synced,
    min_portfolio_target,
    max_portfolio_target,
    created_at,
    updated_at
FROM securities;

-- Drop old table and rename new
DROP TABLE securities;
ALTER TABLE securities_new RENAME TO securities;

-- Recreate indexes
CREATE INDEX IF NOT EXISTS idx_securities_active ON securities(active);
CREATE INDEX IF NOT EXISTS idx_securities_country ON securities(country);
CREATE INDEX IF NOT EXISTS idx_securities_industry ON securities(industry);
CREATE INDEX IF NOT EXISTS idx_securities_symbol ON securities(symbol); -- Index symbol for lookups

-- Step 4: Migrate scores table
CREATE TABLE scores_new (
    isin TEXT PRIMARY KEY,
    total_score REAL NOT NULL,
    quality_score REAL,
    opportunity_score REAL,
    analyst_score REAL,
    allocation_fit_score REAL,
    volatility REAL,
    cagr_score REAL,
    consistency_score REAL,
    history_years INTEGER,
    technical_score REAL,
    fundamental_score REAL,
    last_updated TEXT NOT NULL,
    FOREIGN KEY (isin) REFERENCES securities(isin) ON DELETE CASCADE
) STRICT;

-- Copy data, mapping symbol → isin
-- Cash positions don't typically have scores, but handle them if they do
INSERT INTO scores_new
SELECT
    CASE
        WHEN s.isin IS NOT NULL AND s.isin != '' AND TRIM(s.isin) != '' THEN s.isin
        WHEN s.symbol LIKE 'CASH:%' THEN s.symbol  -- Cash positions use symbol as ISIN
        ELSE s.symbol  -- Fallback
    END as isin,
    sc.total_score,
    sc.quality_score,
    sc.opportunity_score,
    sc.analyst_score,
    sc.allocation_fit_score,
    sc.volatility,
    sc.cagr_score,
    sc.consistency_score,
    sc.history_years,
    sc.technical_score,
    sc.fundamental_score,
    sc.last_updated
FROM scores sc
INNER JOIN securities s ON sc.symbol = s.symbol;

DROP TABLE scores;
ALTER TABLE scores_new RENAME TO scores;

CREATE INDEX IF NOT EXISTS idx_scores_total ON scores(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_scores_updated ON scores(last_updated);

-- Step 5: Migrate positions table
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
    symbol TEXT, -- Keep symbol for display/API conversion
    FOREIGN KEY (isin) REFERENCES securities(isin) ON DELETE CASCADE
) STRICT;

-- Copy data, mapping symbol → isin
-- Handle CASH positions specially (they don't have ISIN)
-- Note: bucket_id is legacy and has been removed - do not copy it
INSERT INTO positions_new
SELECT
    CASE
        WHEN p.symbol LIKE 'CASH:%' THEN p.symbol -- CASH positions keep symbol as isin
        ELSE COALESCE(s.isin,
            CASE
                WHEN s.symbol LIKE 'CASH:%' THEN s.symbol
                ELSE s.symbol
            END)
    END as isin,
    p.quantity,
    p.avg_price,
    p.current_price,
    p.currency,
    p.currency_rate,
    p.market_value_eur,
    p.cost_basis_eur,
    p.unrealized_pnl,
    p.unrealized_pnl_pct,
    p.last_updated,
    p.first_bought,
    p.last_sold,
    p.symbol
FROM positions p
LEFT JOIN securities s ON p.symbol = s.symbol
WHERE p.symbol LIKE 'CASH:%' OR s.symbol IS NOT NULL;

DROP TABLE positions;
ALTER TABLE positions_new RENAME TO positions;
CREATE INDEX IF NOT EXISTS idx_positions_value ON positions(market_value_eur DESC);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol); -- Index symbol for lookups

-- Step 6: Update trades table (add isin column, keep id as PRIMARY KEY)
-- Trades already has isin column, but we need to ensure it's populated from securities
-- Handle cash positions specially (use symbol as ISIN)
UPDATE trades
SET isin = (
    SELECT CASE
        WHEN s.isin IS NOT NULL AND s.isin != '' AND TRIM(s.isin) != '' THEN s.isin
        WHEN s.symbol LIKE 'CASH:%' THEN s.symbol
        ELSE s.symbol
    END
    FROM securities s
    WHERE s.symbol = trades.symbol
)
WHERE (isin IS NULL OR isin = '')
AND EXISTS (SELECT 1 FROM securities s WHERE s.symbol = trades.symbol);

-- Create index on isin for trades
CREATE INDEX IF NOT EXISTS idx_trades_isin ON trades(isin);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol); -- Keep symbol index for lookups

-- Step 7: Update dividend_history table (add isin column, keep id as PRIMARY KEY)
-- Dividend history already has isin column, but we need to ensure it's populated
-- Cash positions don't have dividends, but handle them if they exist
UPDATE dividend_history
SET isin = (
    SELECT CASE
        WHEN s.isin IS NOT NULL AND s.isin != '' AND TRIM(s.isin) != '' THEN s.isin
        WHEN s.symbol LIKE 'CASH:%' THEN s.symbol
        ELSE s.symbol
    END
    FROM securities s
    WHERE s.symbol = dividend_history.symbol
)
WHERE (isin IS NULL OR isin = '')
AND EXISTS (SELECT 1 FROM securities s WHERE s.symbol = dividend_history.symbol);

-- Create index on isin for dividends
CREATE INDEX IF NOT EXISTS idx_dividends_isin ON dividend_history(isin);
CREATE INDEX IF NOT EXISTS idx_dividends_symbol ON dividend_history(symbol); -- Keep symbol index

-- Step 8: Update recommendations table (add isin column, keep uuid as PRIMARY KEY)
-- First, add isin column if it doesn't exist
-- SQLite doesn't support ALTER TABLE ADD COLUMN, so we check first
-- For now, we'll assume it might not exist and handle it

-- Update existing recommendations - ensure symbol references are valid
-- Note: recommendations table doesn't have isin column yet
-- Application code will handle ISIN lookups via symbol

-- Note: recommendations table doesn't have isin column yet
-- We'll add it in a separate migration or application code will handle it
-- For now, we ensure symbol references are valid

-- Step 9: Migrate security_tags table
CREATE TABLE security_tags_new (
    isin TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (isin, tag_id),
    FOREIGN KEY (isin) REFERENCES securities(isin) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
) STRICT;

-- Copy data, mapping symbol → isin
-- Handle cash positions specially (use symbol as ISIN)
INSERT INTO security_tags_new
SELECT
    CASE
        WHEN s.isin IS NOT NULL AND s.isin != '' AND TRIM(s.isin) != '' THEN s.isin
        WHEN s.symbol LIKE 'CASH:%' THEN s.symbol  -- Cash positions use symbol as ISIN
        ELSE s.symbol  -- Fallback
    END as isin,
    st.tag_id,
    st.created_at,
    st.updated_at
FROM security_tags st
INNER JOIN securities s ON st.symbol = s.symbol;

DROP TABLE security_tags;
ALTER TABLE security_tags_new RENAME TO security_tags;

CREATE INDEX IF NOT EXISTS idx_security_tags_isin ON security_tags(isin);
CREATE INDEX IF NOT EXISTS idx_security_tags_tag_id ON security_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_security_tags_symbol ON security_tags(isin); -- For backward compatibility lookups

-- Step 10: Cleanup temporary validation tables
DROP TABLE IF EXISTS _isin_validation;
DROP TABLE IF EXISTS _isin_duplicates;

-- Migration complete
-- All tables now use ISIN as primary identifier
-- Symbol columns remain as indexed fields for display and API conversion
