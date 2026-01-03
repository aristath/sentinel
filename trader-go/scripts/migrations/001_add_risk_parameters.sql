-- Migration: Add risk metric parameters to satellite settings
-- Created: 2026-01-03
-- Purpose: Parameterize risk calculations for multi-agent architecture
--
-- This migration adds four new columns to the satellite_settings table:
-- - risk_free_rate: Annual risk-free rate (default 3.5%)
-- - sortino_mar: Minimum Acceptable Return for Sortino ratio (default 5%)
-- - evaluation_period_days: Performance evaluation window (default 90 days)
-- - volatility_window: Volatility calculation window (default 60 days)
--
-- These parameters allow each satellite agent to have custom risk assessment criteria.

-- Add new columns to satellite_settings table
ALTER TABLE satellite_settings
ADD COLUMN risk_free_rate REAL DEFAULT 0.035;

ALTER TABLE satellite_settings
ADD COLUMN sortino_mar REAL DEFAULT 0.05;

ALTER TABLE satellite_settings
ADD COLUMN evaluation_period_days INTEGER DEFAULT 90;

ALTER TABLE satellite_settings
ADD COLUMN volatility_window INTEGER DEFAULT 60;

-- Add global defaults to allocation_settings table
INSERT OR IGNORE INTO allocation_settings (key, value, description)
VALUES ('default_risk_free_rate', 0.035, 'Default annual risk-free rate (3.5%)');

INSERT OR IGNORE INTO allocation_settings (key, value, description)
VALUES ('default_sortino_mar', 0.05, 'Default Sortino Minimum Acceptable Return (5%)');

INSERT OR IGNORE INTO allocation_settings (key, value, description)
VALUES ('default_evaluation_days', 90, 'Default performance evaluation period (days)');

-- Update schema version
INSERT INTO schema_version (version, applied_at, description)
VALUES (2, datetime('now'), 'Add risk metric parameters to satellite settings');
