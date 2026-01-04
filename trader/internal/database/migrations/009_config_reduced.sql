-- Config Database Schema (Reduced)
-- Migration 009: Create config.db schema for application configuration
--
-- This migration creates tables for the REDUCED config database:
-- - Settings: Key-value application configuration
-- - Allocation targets: Group-based portfolio allocation rules
--
-- What was REMOVED from config.db:
-- - securities → moved to universe.db
-- - country_groups → moved to universe.db
-- - industry_groups → moved to universe.db
-- - recommendations → moved to cache.db
-- - planner_configs → moved to agents.db
--
-- Data Migration Note:
-- During Phase 6, tables that belong to other databases will be dropped from config.db

-- Settings table: application configuration (key-value store)
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TEXT NOT NULL
) STRICT;

-- Allocation targets table: group-based allocation rules
-- Defines target percentages for country/industry groups
-- Schema matches repository expectations: id, type, name, target_pct
CREATE TABLE IF NOT EXISTS allocation_targets (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,      -- 'geography', 'industry', 'country_group', 'industry_group'
    name TEXT NOT NULL,
    target_pct REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(type, name)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_allocation_type ON allocation_targets(type);
