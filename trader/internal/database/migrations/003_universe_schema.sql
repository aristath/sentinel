-- Universe Database Schema
-- Migration 003: Create universe.db schema for investment universe definition
--
-- This migration creates tables for the universe database which stores:
-- - Securities (stocks/bonds/ETFs) that can be traded
-- - Country groupings for allocation strategies
-- - Industry groupings for diversification
--
-- Data Migration Note:
-- After this schema is created, data will be migrated from config.db to universe.db
-- during Phase 6 of the database architecture migration.

-- Securities table: investment universe (symbols that can be traded)
CREATE TABLE IF NOT EXISTS securities (
    symbol TEXT PRIMARY KEY,
    yahoo_symbol TEXT,
    isin TEXT,
    name TEXT NOT NULL,
    product_type TEXT,
    industry TEXT,
    country TEXT,
    fullExchangeName TEXT,
    priority_multiplier REAL DEFAULT 1.0,
    min_lot INTEGER DEFAULT 1,
    active INTEGER DEFAULT 1,  -- Boolean: 1 = active, 0 = inactive (soft delete)
    allow_buy INTEGER DEFAULT 1,
    allow_sell INTEGER DEFAULT 1,
    currency TEXT,
    last_synced TEXT,  -- ISO 8601 timestamp
    min_portfolio_target REAL,
    max_portfolio_target REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_securities_active ON securities(active);
CREATE INDEX IF NOT EXISTS idx_securities_country ON securities(country);
CREATE INDEX IF NOT EXISTS idx_securities_industry ON securities(industry);
CREATE INDEX IF NOT EXISTS idx_securities_isin ON securities(isin);

-- Country groups: custom groupings for allocation strategies
-- Example: 'EU' -> ['Germany', 'France', 'Italy']
CREATE TABLE IF NOT EXISTS country_groups (
    group_name TEXT NOT NULL,
    country_name TEXT NOT NULL,  -- '__EMPTY__' is special marker for empty groups
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (group_name, country_name)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_country_groups_group ON country_groups(group_name);

-- Industry groups: custom groupings for diversification strategies
-- Example: 'Tech' -> ['Software', 'Semiconductors', 'Hardware']
CREATE TABLE IF NOT EXISTS industry_groups (
    group_name TEXT NOT NULL,
    industry_name TEXT NOT NULL,  -- '__EMPTY__' is special marker for empty groups
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (group_name, industry_name)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_industry_groups_group ON industry_groups(group_name);
