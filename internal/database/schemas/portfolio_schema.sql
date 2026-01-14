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
    last_updated INTEGER,             -- Unix timestamp (seconds since epoch)
    first_bought INTEGER,            -- Unix timestamp at midnight UTC (seconds since epoch)
    last_sold INTEGER,               -- Unix timestamp at midnight UTC (seconds since epoch)
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
    stability_score REAL,
    sharpe_score REAL,
    drawdown_score REAL,
    dividend_bonus REAL,
    financial_strength_score REAL,
    rsi REAL,
    ema_200 REAL,
    below_52w_high_pct REAL,
    last_updated INTEGER NOT NULL    -- Unix timestamp (seconds since epoch)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_scores_total ON scores(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_scores_updated ON scores(last_updated);

-- Cash balances table: dedicated storage for cash balances
-- This replaces the previous "cash-as-securities" approach where cash was stored
-- as synthetic positions (CASH:EUR, CASH:USD, etc.) in the positions table.
-- Cash is now managed separately via CashManager and stored in this dedicated table.
CREATE TABLE IF NOT EXISTS cash_balances (
    currency TEXT PRIMARY KEY,
    balance REAL NOT NULL,
    last_updated INTEGER NOT NULL    -- Unix timestamp (seconds since epoch)
) STRICT;

-- Kelly sizes table: optimal position sizes calculated using Kelly Criterion
CREATE TABLE IF NOT EXISTS kelly_sizes (
    isin TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    kelly_fraction REAL NOT NULL,
    constrained_fraction REAL NOT NULL,
    fractional_multiplier REAL NOT NULL,
    regime_adjustment REAL NOT NULL,
    calculated_at INTEGER NOT NULL,    -- Unix timestamp (seconds since epoch)
    FOREIGN KEY (isin) REFERENCES scores(isin) ON DELETE CASCADE
) STRICT;

CREATE INDEX IF NOT EXISTS idx_kelly_sizes_symbol ON kelly_sizes(symbol);
CREATE INDEX IF NOT EXISTS idx_kelly_sizes_calculated ON kelly_sizes(calculated_at);
