-- Migration 033: Migrate scores table from symbol to ISIN PRIMARY KEY
--
-- This migration migrates the scores table in portfolio.db from symbol to ISIN.
-- Unlike migration 030, this doesn't reference securities table (which is in universe.db).
-- Instead, it assumes scores already have corresponding securities in universe.db.
--
-- Note: This migration should run AFTER migration 030 on universe.db has completed.
-- The scores table will use symbol as ISIN for cash positions, matching the securities table.

-- Step 1: Create new scores table with isin as PRIMARY KEY
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
    sharpe_score REAL,
    drawdown_score REAL,
    dividend_bonus REAL,
    financial_strength_score REAL,
    rsi REAL,
    ema_200 REAL,
    below_52w_high_pct REAL,
    last_updated TEXT NOT NULL
) STRICT;

-- Step 2: Copy data, using symbol as ISIN (matching securities table migration)
-- For cash positions, symbol is used as ISIN
-- For regular securities, we assume the symbol matches what's in securities table
INSERT INTO scores_new
SELECT
    symbol as isin,  -- Use symbol as ISIN (securities table migration does the same mapping)
    total_score,
    quality_score,
    opportunity_score,
    analyst_score,
    allocation_fit_score,
    volatility,
    cagr_score,
    consistency_score,
    history_years,
    technical_score,
    fundamental_score,
    sharpe_score,
    drawdown_score,
    dividend_bonus,
    financial_strength_score,
    rsi,
    ema_200,
    below_52w_high_pct,
    last_updated
FROM scores;

-- Step 3: Drop old table and rename new
DROP TABLE scores;
ALTER TABLE scores_new RENAME TO scores;

-- Step 4: Recreate indexes
CREATE INDEX IF NOT EXISTS idx_scores_total ON scores(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_scores_updated ON scores(last_updated);
