-- History Database Schema
-- Single source of truth for history.db
-- This schema represents the final state after all migrations

-- Daily prices: OHLC data for all securities
-- Note: Column is named 'isin' (not 'symbol') to match actual data storage (ISINs, not Tradernet symbols)
CREATE TABLE IF NOT EXISTS daily_prices (
    isin TEXT NOT NULL,
    date TEXT NOT NULL,              -- YYYY-MM-DD format
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER,
    adjusted_close REAL,
    PRIMARY KEY (isin, date)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_prices_isin ON daily_prices(isin);
CREATE INDEX IF NOT EXISTS idx_prices_date ON daily_prices(date DESC);
CREATE INDEX IF NOT EXISTS idx_prices_isin_date ON daily_prices(isin, date DESC);

-- Exchange rates: currency conversion history
CREATE TABLE IF NOT EXISTS exchange_rates (
    from_currency TEXT NOT NULL,
    to_currency TEXT NOT NULL,
    date TEXT NOT NULL,              -- YYYY-MM-DD format
    rate REAL NOT NULL,
    PRIMARY KEY (from_currency, to_currency, date)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_rates_pair ON exchange_rates(from_currency, to_currency);
CREATE INDEX IF NOT EXISTS idx_rates_date ON exchange_rates(date DESC);

-- Monthly prices: aggregated monthly averages for all securities
-- Used for CAGR calculations and historical analysis
-- Note: Column is named 'isin' (not 'symbol') to match actual data storage (ISINs, not Tradernet symbols)
CREATE TABLE IF NOT EXISTS monthly_prices (
    isin TEXT NOT NULL,
    year_month TEXT NOT NULL,
    avg_close REAL NOT NULL,
    avg_adj_close REAL NOT NULL,
    source TEXT,
    created_at TEXT,
    PRIMARY KEY (isin, year_month)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_monthly_isin ON monthly_prices(isin);
CREATE INDEX IF NOT EXISTS idx_monthly_year_month ON monthly_prices(year_month DESC);
CREATE INDEX IF NOT EXISTS idx_monthly_isin_year_month ON monthly_prices(isin, year_month DESC);
