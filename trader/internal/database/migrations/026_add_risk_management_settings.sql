-- Migration 026: Add risk management settings to planner_settings
--
-- This migration adds risk management settings to planner_settings table:
-- - min_hold_days: Minimum days a position must be held before selling
-- - sell_cooldown_days: Days to wait after selling before buying again
-- - max_loss_threshold: Maximum loss threshold before forced selling consideration
-- - max_sell_percentage: Maximum percentage of position allowed to sell per transaction

-- Add risk management columns
-- Note: SQLite doesn't support ADD COLUMN in older versions.
-- Migration handler will skip if column already exists (duplicate column error)
ALTER TABLE planner_settings ADD COLUMN min_hold_days INTEGER DEFAULT 90;
ALTER TABLE planner_settings ADD COLUMN sell_cooldown_days INTEGER DEFAULT 180;
ALTER TABLE planner_settings ADD COLUMN max_loss_threshold REAL DEFAULT -0.20;
ALTER TABLE planner_settings ADD COLUMN max_sell_percentage REAL DEFAULT 0.20;
