-- Migration: Add optimizer_target_return and min_cash_reserve to planner_settings
-- These fields move from global settings to planner configuration for better separation of concerns

-- Add optimizer_target_return column
ALTER TABLE planner_settings ADD COLUMN optimizer_target_return REAL DEFAULT 0.11;

-- Add min_cash_reserve column
ALTER TABLE planner_settings ADD COLUMN min_cash_reserve REAL DEFAULT 500.0;

-- Update existing row with default values if needed
UPDATE planner_settings
SET optimizer_target_return = 0.11,
    min_cash_reserve = 500.0
WHERE id = 'main'
  AND (optimizer_target_return IS NULL OR min_cash_reserve IS NULL);
