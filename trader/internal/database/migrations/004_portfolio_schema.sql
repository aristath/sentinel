-- Portfolio Database Schema
-- Migration 004: Create portfolio.db schema for current portfolio state
--
-- This migration creates tables for the portfolio database which consolidates:
-- - Positions (from state.db)
-- - Scores (from state.db/calculations.db)
-- - Calculated metrics (from calculations.db)
-- - Portfolio snapshots (from snapshots.db)
--
-- Data Migration Note:
-- After this schema is created, data will be migrated during Phase 6:
-- - positions: state.db → portfolio.db
-- - scores: state.db → portfolio.db
-- - calculated_metrics: calculations.db → portfolio.db (if exists)
-- - portfolio_snapshots: snapshots.db → portfolio.db

-- Positions table: current holdings in the portfolio
CREATE TABLE IF NOT EXISTS positions (
    symbol TEXT PRIMARY KEY,
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
    isin TEXT,
    bucket_id TEXT DEFAULT 'core'
) STRICT;

CREATE INDEX IF NOT EXISTS idx_positions_bucket ON positions(bucket_id);
CREATE INDEX IF NOT EXISTS idx_positions_value ON positions(market_value_eur DESC);

-- Scores table: security scoring for ranking and selection
CREATE TABLE IF NOT EXISTS scores (
    symbol TEXT PRIMARY KEY,
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
    last_updated TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_scores_total ON scores(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_scores_updated ON scores(last_updated);

-- Calculated metrics table: raw technical/fundamental metrics
-- Pre-computed from price history for faster access
CREATE TABLE IF NOT EXISTS calculated_metrics (
    symbol TEXT NOT NULL,
    metric_name TEXT NOT NULL,  -- e.g., 'rsi_14', 'ema_50', 'cagr_1y'
    metric_value REAL NOT NULL,
    calculated_at TEXT NOT NULL,
    PRIMARY KEY (symbol, metric_name)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_metrics_symbol ON calculated_metrics(symbol);
CREATE INDEX IF NOT EXISTS idx_metrics_calculated ON calculated_metrics(calculated_at);

-- Portfolio snapshots table: daily portfolio summaries
-- Historical time-series for performance tracking
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    snapshot_date TEXT PRIMARY KEY,  -- YYYY-MM-DD format
    total_value REAL NOT NULL,
    cash_balance REAL NOT NULL,
    invested_value REAL NOT NULL,
    total_pnl REAL,
    total_pnl_pct REAL,
    position_count INTEGER NOT NULL,
    bucket_id TEXT DEFAULT 'core',
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_snapshots_date ON portfolio_snapshots(snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_bucket ON portfolio_snapshots(bucket_id);
