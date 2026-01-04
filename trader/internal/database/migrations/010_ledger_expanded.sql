-- Ledger Database Schema (Expanded)
-- Migration 010: Create ledger.db schema for immutable financial audit trail
--
-- This migration creates tables for the EXPANDED ledger database:
-- - Trades: Complete trade history (already exists)
-- - Cash flows: Deposits, withdrawals, fees (already exists)
-- - Dividend history: Dividend payments with DRIP tracking (MERGED from dividends.db)
--
-- Rationale for merging dividends into ledger:
-- - All financial transactions belong together in the audit trail
-- - Ledger has ProfileLedger (maximum safety, synchronous=FULL)
-- - Hourly backups for all financial data
-- - Append-only, never modified or deleted
--
-- Data Migration Note:
-- During Phase 6:
-- - dividend_history: dividends.db → ledger.db
-- - drip_tracking: dividends.db → ledger.db (if exists)
-- - dividends.db will be deleted after migration

-- Trades table: complete trade execution history
-- (Schema already exists from previous migrations, but including for completeness)
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    isin TEXT,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity REAL NOT NULL CHECK (quantity > 0),
    price REAL NOT NULL CHECK (price > 0),
    executed_at TEXT NOT NULL,       -- ISO 8601 timestamp
    order_id TEXT,
    currency TEXT NOT NULL,
    value_eur REAL NOT NULL,
    source TEXT DEFAULT 'manual',    -- 'manual', 'planner', 'rebalance', etc.
    bucket_id TEXT DEFAULT 'core',
    mode TEXT DEFAULT 'normal',      -- 'normal', 'drip', 'fractional'
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_executed ON trades(executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_bucket ON trades(bucket_id);

-- Cash flows table: deposits, withdrawals, fees
-- (Schema already exists, including for completeness)
CREATE TABLE IF NOT EXISTS cash_flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_type TEXT NOT NULL CHECK (flow_type IN ('deposit', 'withdrawal', 'fee', 'dividend', 'interest')),
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    amount_eur REAL NOT NULL,
    description TEXT,
    executed_at TEXT NOT NULL,       -- ISO 8601 timestamp
    bucket_id TEXT DEFAULT 'core',
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_cashflows_type ON cash_flows(flow_type);
CREATE INDEX IF NOT EXISTS idx_cashflows_executed ON cash_flows(executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_cashflows_bucket ON cash_flows(bucket_id);

-- Dividend history: dividend payments received
-- MERGED from dividends.db into ledger.db
CREATE TABLE IF NOT EXISTS dividend_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    isin TEXT,
    payment_date TEXT NOT NULL,      -- YYYY-MM-DD when dividend was received
    ex_date TEXT,                    -- YYYY-MM-DD ex-dividend date
    amount_per_share REAL NOT NULL,
    shares_held REAL NOT NULL,       -- Shares owned on ex-date
    total_amount REAL NOT NULL,      -- Total dividend received
    currency TEXT NOT NULL,
    total_amount_eur REAL NOT NULL,
    drip_enabled INTEGER DEFAULT 0,  -- Boolean: was DRIP active?
    reinvested_shares REAL,          -- Shares acquired via DRIP
    bucket_id TEXT DEFAULT 'core',
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_dividends_symbol ON dividend_history(symbol);
CREATE INDEX IF NOT EXISTS idx_dividends_payment_date ON dividend_history(payment_date DESC);
CREATE INDEX IF NOT EXISTS idx_dividends_bucket ON dividend_history(bucket_id);

-- DRIP tracking: Dividend Reinvestment Plan status per security
-- MERGED from dividends.db into ledger.db
CREATE TABLE IF NOT EXISTS drip_tracking (
    symbol TEXT PRIMARY KEY,
    drip_enabled INTEGER DEFAULT 0,  -- Boolean: is DRIP active for this security?
    total_dividends_received REAL DEFAULT 0,
    total_shares_reinvested REAL DEFAULT 0,
    last_dividend_date TEXT,
    updated_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_drip_enabled ON drip_tracking(drip_enabled);
