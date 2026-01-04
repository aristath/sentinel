-- History Database Schema
-- Migration 006: Create history.db schema for historical time-series data
--
-- This migration consolidates multiple databases into history.db:
-- - All history/{SYMBOL}.db files → single daily_prices table
-- - rates.db → exchange_rates table
-- - snapshots.db → portfolio_snapshots table (consolidated with portfolio.db)
--
-- Data Migration Note:
-- During Phase 6, data will be migrated from 65+ per-symbol databases:
-- - history/AAPL_US.db, history/AMD_US.db, etc. → daily_prices table
-- - rates.db → exchange_rates table

-- Daily prices: OHLC data for all securities
-- Consolidates all history/{SYMBOL}.db files into single table
CREATE TABLE IF NOT EXISTS daily_prices (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,              -- YYYY-MM-DD format
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER,
    adjusted_close REAL,
    PRIMARY KEY (symbol, date)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_prices_symbol ON daily_prices(symbol);
CREATE INDEX IF NOT EXISTS idx_prices_date ON daily_prices(date DESC);
CREATE INDEX IF NOT EXISTS idx_prices_symbol_date ON daily_prices(symbol, date DESC);

-- Exchange rates: currency conversion history
-- Migrated from rates.db
CREATE TABLE IF NOT EXISTS exchange_rates (
    from_currency TEXT NOT NULL,
    to_currency TEXT NOT NULL,
    date TEXT NOT NULL,              -- YYYY-MM-DD format
    rate REAL NOT NULL,
    PRIMARY KEY (from_currency, to_currency, date)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_rates_pair ON exchange_rates(from_currency, to_currency);
CREATE INDEX IF NOT EXISTS idx_rates_date ON exchange_rates(date DESC);
