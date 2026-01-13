-- Migration script for config.db: Remove dead planner settings columns
-- These columns are no longer used after the exhaustive generator refactoring (2026-01)
-- Pattern, generator, and eligibility/recently_traded filter columns removed
--
-- Run this script on the Arduino device:
--   sqlite3 /home/arduino/sentinel/data/config.db < migrate_planner_settings_cleanup.sql
--
-- NOTE: SQLite doesn't support DROP COLUMN in older versions, so we need to recreate the table.
-- This migration uses a safe approach: create new table, copy data, swap, and drop old.

-- Start transaction for safety
BEGIN TRANSACTION;

-- Create new table with only the columns we want
CREATE TABLE IF NOT EXISTS planner_settings_new (
    -- Primary key (constant value - only one row exists)
    id TEXT PRIMARY KEY DEFAULT 'main',

    -- Basic identification
    name TEXT NOT NULL DEFAULT 'default',
    description TEXT DEFAULT '',

    -- Global planner settings
    enable_batch_generation INTEGER DEFAULT 1,
    max_depth INTEGER DEFAULT 10,
    max_opportunities_per_category INTEGER DEFAULT 10,
    enable_diverse_selection INTEGER DEFAULT 1,
    diversity_weight REAL DEFAULT 0.3,

    -- Transaction costs
    transaction_cost_fixed REAL DEFAULT 5.0,
    transaction_cost_percent REAL DEFAULT 0.001,

    -- Trade permissions
    allow_sell INTEGER DEFAULT 1,
    allow_buy INTEGER DEFAULT 1,

    -- Risk management settings
    min_hold_days INTEGER DEFAULT 90,
    sell_cooldown_days INTEGER DEFAULT 180,
    max_loss_threshold REAL DEFAULT -0.20,
    max_sell_percentage REAL DEFAULT 0.20,
    averaging_down_percent REAL DEFAULT 0.10,

    -- Opportunity Calculator enabled flags
    enable_profit_taking_calc INTEGER DEFAULT 1,
    enable_averaging_down_calc INTEGER DEFAULT 1,
    enable_opportunity_buys_calc INTEGER DEFAULT 1,
    enable_rebalance_sells_calc INTEGER DEFAULT 1,
    enable_rebalance_buys_calc INTEGER DEFAULT 1,
    enable_weight_based_calc INTEGER DEFAULT 1,

    -- Post-generation filter enabled flags (eligibility/recently_traded removed)
    enable_correlation_aware_filter INTEGER DEFAULT 1,
    enable_diversity_filter INTEGER DEFAULT 1,
    enable_tag_filtering INTEGER DEFAULT 1,

    -- Optimizer settings
    optimizer_blend REAL DEFAULT 0.5,
    optimizer_target_return REAL DEFAULT 0.11,
    min_cash_reserve REAL DEFAULT 500.0,

    -- Timestamps
    updated_at INTEGER NOT NULL
) STRICT;

-- Copy data from old table (only the columns that still exist)
INSERT INTO planner_settings_new (
    id, name, description,
    enable_batch_generation,
    max_depth, max_opportunities_per_category,
    enable_diverse_selection, diversity_weight,
    transaction_cost_fixed, transaction_cost_percent,
    allow_sell, allow_buy,
    min_hold_days, sell_cooldown_days, max_loss_threshold, max_sell_percentage, averaging_down_percent,
    enable_profit_taking_calc,
    enable_averaging_down_calc,
    enable_opportunity_buys_calc,
    enable_rebalance_sells_calc,
    enable_rebalance_buys_calc,
    enable_weight_based_calc,
    enable_correlation_aware_filter,
    enable_diversity_filter,
    enable_tag_filtering,
    optimizer_blend, optimizer_target_return, min_cash_reserve,
    updated_at
)
SELECT
    id, name, description,
    enable_batch_generation,
    max_depth, max_opportunities_per_category,
    enable_diverse_selection, diversity_weight,
    transaction_cost_fixed, transaction_cost_percent,
    allow_sell, allow_buy,
    min_hold_days, sell_cooldown_days, max_loss_threshold, max_sell_percentage, averaging_down_percent,
    enable_profit_taking_calc,
    enable_averaging_down_calc,
    enable_opportunity_buys_calc,
    enable_rebalance_sells_calc,
    enable_rebalance_buys_calc,
    enable_weight_based_calc,
    enable_correlation_aware_filter,
    enable_diversity_filter,
    enable_tag_filtering,
    optimizer_blend, optimizer_target_return, min_cash_reserve,
    updated_at
FROM planner_settings;

-- Drop old table
DROP TABLE planner_settings;

-- Rename new table to original name
ALTER TABLE planner_settings_new RENAME TO planner_settings;

-- Commit transaction
COMMIT;

-- Verify: List columns in new table
.schema planner_settings
