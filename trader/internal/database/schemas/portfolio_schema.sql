-- Portfolio Database Schema
-- Single source of truth for portfolio.db
-- This schema represents the final state after all migrations

-- Positions table: current holdings in the portfolio (ISIN as PRIMARY KEY)
CREATE TABLE IF NOT EXISTS positions (
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

CREATE INDEX IF NOT EXISTS idx_positions_value ON positions(market_value_eur DESC);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);

-- Scores table: security scoring for ranking and selection (ISIN as PRIMARY KEY)
CREATE TABLE IF NOT EXISTS scores (
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

-- Cash balances table: dedicated storage for cash balances
-- This replaces the previous "cash-as-securities" approach where cash was stored
-- as synthetic positions (CASH:EUR, CASH:USD, etc.) in the positions table.
-- Cash is now managed separately via CashManager and stored in this dedicated table.
CREATE TABLE IF NOT EXISTS cash_balances (
    currency TEXT PRIMARY KEY,
    balance REAL NOT NULL,
    last_updated TEXT NOT NULL
) STRICT;
