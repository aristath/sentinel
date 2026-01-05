-- Migration 027: Add optimizer_blend to planner_settings
--
-- This migration adds optimizer_blend setting to planner_settings table:
-- - optimizer_blend: Blend between Mean-Variance (0.0) and HRP (1.0) optimization strategies

-- Add optimizer_blend column
ALTER TABLE planner_settings ADD COLUMN optimizer_blend REAL DEFAULT 0.5;
