-- Client Data Cache Database Schema
-- Single source of truth for client_data.db
-- Stores raw JSON responses from external API clients with expiration timestamps

-- Alpha Vantage tables (per-security, keyed by ISIN)
-- Using expires_at for fast cache checks: WHERE expires_at > unixepoch()

CREATE TABLE IF NOT EXISTS alphavantage_overview (
    isin TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS alphavantage_balance_sheet (
    isin TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS alphavantage_cash_flow (
    isin TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS alphavantage_earnings (
    isin TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS alphavantage_dividends (
    isin TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS alphavantage_etf_profile (
    isin TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS alphavantage_insider (
    isin TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);

-- Alpha Vantage economic indicators (market-wide, keyed by indicator name)
CREATE TABLE IF NOT EXISTS alphavantage_economic (
    indicator TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);

-- OpenFIGI table (ISIN to ticker mapping)
CREATE TABLE IF NOT EXISTS openfigi (
    isin TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);

-- Yahoo Finance metadata table
CREATE TABLE IF NOT EXISTS yahoo_metadata (
    isin TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);

-- ExchangeRate table (keyed by currency pair, e.g., "EUR:USD")
CREATE TABLE IF NOT EXISTS exchangerate (
    pair TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);

-- Current prices cache (short TTL - 10 minutes)
CREATE TABLE IF NOT EXISTS current_prices (
    isin TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);

-- Indexes for expiration queries (cleanup, freshness checks)
CREATE INDEX IF NOT EXISTS idx_av_overview_expires ON alphavantage_overview(expires_at);
CREATE INDEX IF NOT EXISTS idx_av_balance_expires ON alphavantage_balance_sheet(expires_at);
CREATE INDEX IF NOT EXISTS idx_av_cashflow_expires ON alphavantage_cash_flow(expires_at);
CREATE INDEX IF NOT EXISTS idx_av_earnings_expires ON alphavantage_earnings(expires_at);
CREATE INDEX IF NOT EXISTS idx_av_dividends_expires ON alphavantage_dividends(expires_at);
CREATE INDEX IF NOT EXISTS idx_av_etf_expires ON alphavantage_etf_profile(expires_at);
CREATE INDEX IF NOT EXISTS idx_av_insider_expires ON alphavantage_insider(expires_at);
CREATE INDEX IF NOT EXISTS idx_av_economic_expires ON alphavantage_economic(expires_at);
CREATE INDEX IF NOT EXISTS idx_openfigi_expires ON openfigi(expires_at);
CREATE INDEX IF NOT EXISTS idx_yahoo_expires ON yahoo_metadata(expires_at);
CREATE INDEX IF NOT EXISTS idx_exchangerate_expires ON exchangerate(expires_at);
CREATE INDEX IF NOT EXISTS idx_prices_expires ON current_prices(expires_at);
