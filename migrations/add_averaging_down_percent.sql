-- Migration: Add averaging_down_percent to planner_settings
-- Date: 2026-01-10
-- Description: Adds configurable percentage for averaging down quantity calculation
--              Kelly sizing will be used as upper bound when available

-- Add averaging_down_percent column with default 0.10 (10%)
ALTER TABLE planner_settings ADD COLUMN averaging_down_percent REAL DEFAULT 0.10;
