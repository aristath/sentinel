-- Ledger Database Schema
-- Single source of truth for ledger.db
-- This schema represents the final state after all migrations

-- Trades table: complete trade execution history
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    isin TEXT,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity REAL NOT NULL CHECK (quantity > 0),
    price REAL NOT NULL CHECK (price > 0),
    executed_at TEXT NOT NULL,       -- ISO 8601 timestamp
    order_id TEXT,
    currency TEXT NOT NULL,
    value_eur REAL NOT NULL,
    source TEXT DEFAULT 'manual',    -- 'manual', 'planner', 'rebalance', etc.
    mode TEXT DEFAULT 'normal',      -- 'normal', 'drip', 'fractional'
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_isin ON trades(isin);
CREATE INDEX IF NOT EXISTS idx_trades_executed ON trades(executed_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_order_id ON trades(order_id) WHERE order_id IS NOT NULL;

-- Cash flows table: deposits, withdrawals, fees, dividends, interest
CREATE TABLE IF NOT EXISTS cash_flows (
    id INTEGER PRIMARY KEY,
    transaction_id TEXT UNIQUE NOT NULL,
    type_doc_id INTEGER NOT NULL,
    transaction_type TEXT,
    date TEXT NOT NULL,              -- YYYY-MM-DD format
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    amount_eur REAL NOT NULL,
    status TEXT,
    status_c INTEGER,
    description TEXT,
    params_json TEXT,
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_cash_flows_date ON cash_flows(date);
CREATE INDEX IF NOT EXISTS idx_cash_flows_type ON cash_flows(transaction_type);

-- Dividend history: dividend payments received
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
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_dividends_symbol ON dividend_history(symbol);
CREATE INDEX IF NOT EXISTS idx_dividends_isin ON dividend_history(isin);
CREATE INDEX IF NOT EXISTS idx_dividends_payment_date ON dividend_history(payment_date DESC);

-- DRIP tracking: Dividend Reinvestment Plan status per security
CREATE TABLE IF NOT EXISTS drip_tracking (
    symbol TEXT PRIMARY KEY,
    drip_enabled INTEGER DEFAULT 0,  -- Boolean: is DRIP active for this security?
    total_dividends_received REAL DEFAULT 0,
    total_shares_reinvested REAL DEFAULT 0,
    last_dividend_date TEXT,
    updated_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_drip_enabled ON drip_tracking(drip_enabled);
