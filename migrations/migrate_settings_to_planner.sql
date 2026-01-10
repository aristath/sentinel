-- Migration: Move settings from global settings to planner_settings
-- This migration copies optimizer and transaction cost settings from the settings table
-- to the planner_settings table, establishing planner config as the single source of truth.
--
-- Run this AFTER add_planner_optimizer_fields.sql

-- Temporary table to hold settings values
CREATE TEMP TABLE IF NOT EXISTS temp_migrated_settings (
    key TEXT PRIMARY KEY,
    value REAL
);

-- Extract values from settings table (if they exist)
INSERT OR IGNORE INTO temp_migrated_settings (key, value)
SELECT 'optimizer_blend', CAST(value AS REAL)
FROM settings WHERE key = 'optimizer_blend';

INSERT OR IGNORE INTO temp_migrated_settings (key, value)
SELECT 'optimizer_target_return', CAST(value AS REAL)
FROM settings WHERE key = 'optimizer_target_return';

INSERT OR IGNORE INTO temp_migrated_settings (key, value)
SELECT 'min_cash_reserve', CAST(value AS REAL)
FROM settings WHERE key = 'min_cash_reserve';

INSERT OR IGNORE INTO temp_migrated_settings (key, value)
SELECT 'transaction_cost_fixed', CAST(value AS REAL)
FROM settings WHERE key = 'transaction_cost_fixed';

INSERT OR IGNORE INTO temp_migrated_settings (key, value)
SELECT 'transaction_cost_percent', CAST(value AS REAL)
FROM settings WHERE key = 'transaction_cost_percent';

-- Update planner_settings with migrated values (only if values exist in settings table)
UPDATE planner_settings
SET
    optimizer_blend = COALESCE((SELECT value FROM temp_migrated_settings WHERE key = 'optimizer_blend'), optimizer_blend),
    optimizer_target_return = COALESCE((SELECT value FROM temp_migrated_settings WHERE key = 'optimizer_target_return'), optimizer_target_return),
    min_cash_reserve = COALESCE((SELECT value FROM temp_migrated_settings WHERE key = 'min_cash_reserve'), min_cash_reserve),
    transaction_cost_fixed = COALESCE((SELECT value FROM temp_migrated_settings WHERE key = 'transaction_cost_fixed'), transaction_cost_fixed),
    transaction_cost_percent = COALESCE((SELECT value FROM temp_migrated_settings WHERE key = 'transaction_cost_percent'), transaction_cost_percent),
    updated_at = strftime('%s', 'now')
WHERE id = 'main';

-- Archive old settings (keep for historical reference, mark as deprecated)
UPDATE settings
SET value = value || ' (DEPRECATED: moved to planner_settings)'
WHERE key IN ('optimizer_blend', 'optimizer_target_return', 'min_cash_reserve', 'transaction_cost_fixed', 'transaction_cost_percent')
  AND value NOT LIKE '%(DEPRECATED%';

-- Clean up temp table
DROP TABLE IF EXISTS temp_migrated_settings;

-- Verification: Show what was migrated
SELECT 'Migration complete. Planner settings now contain:' AS status;
SELECT
    optimizer_blend,
    optimizer_target_return,
    min_cash_reserve,
    transaction_cost_fixed,
    transaction_cost_percent
FROM planner_settings WHERE id = 'main';
