-- Migration 026: Add risk management settings to planner_settings
--
-- This migration adds risk management settings to planner_settings table:
-- - min_hold_days: Minimum days a position must be held before selling
-- - sell_cooldown_days: Days to wait after selling before buying again
-- - max_loss_threshold: Maximum loss threshold before forced selling consideration
-- - max_sell_percentage: Maximum percentage of position allowed to sell per transaction

-- Add risk management columns
ALTER TABLE planner_settings ADD COLUMN IF NOT EXISTS min_hold_days INTEGER DEFAULT 90;
ALTER TABLE planner_settings ADD COLUMN IF NOT EXISTS sell_cooldown_days INTEGER DEFAULT 180;
ALTER TABLE planner_settings ADD COLUMN IF NOT EXISTS max_loss_threshold REAL DEFAULT -0.20;
ALTER TABLE planner_settings ADD COLUMN IF NOT EXISTS max_sell_percentage REAL DEFAULT 0.20;

