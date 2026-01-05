-- Migration 024: Remove beam_width column from planner_settings
--
-- This migration removes the beam_width column from planner_settings table.
-- Beam search algorithm was not migrated from Python to Go implementation.

-- Drop the beam_width column from planner_settings table
-- Note: SQLite doesn't support DROP COLUMN IF EXISTS.
-- Migration handler will skip if column doesn't exist (no such column error)
ALTER TABLE planner_settings DROP COLUMN beam_width;
