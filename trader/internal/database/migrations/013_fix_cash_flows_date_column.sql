-- Fix cash_flows schema: Add date column for compatibility with cash_flows module
-- Migration 013: Add date column to cash_flows table
--
-- The cash_flows module code expects a 'date' column (YYYY-MM-DD format),
-- but migration 010 created the table with 'executed_at' (ISO 8601 timestamp).
-- This migration adds the date column and populates it from executed_at.
--
-- Note: This migration handles the case where the table was created by migration 010
-- but the code still uses the older schema with 'date' column.

-- Add date column if it doesn't exist (for migration-created tables)
-- The migration system will skip this if column already exists
ALTER TABLE cash_flows ADD COLUMN date TEXT;

-- Populate date from executed_at (extract YYYY-MM-DD from ISO 8601 timestamp)
-- Only update rows where date is NULL to avoid overwriting existing data
UPDATE cash_flows
SET date = substr(executed_at, 1, 10)
WHERE date IS NULL AND executed_at IS NOT NULL;

-- Create index on date column if it doesn't exist
CREATE INDEX IF NOT EXISTS idx_cash_flows_date ON cash_flows(date);
