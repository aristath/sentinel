-- Migration 012: Remove Over-Engineering
--
-- This migration removes unnecessary tracking, audit logs, and unused features:
-- 1. Remove snapshot_json field from portfolio_snapshots (unused)
-- 2. Remove cleanup_log table (audit trail not needed)
-- 3. Remove symbol_removals table (simplify cleanup - delete orphans immediately)
-- 4. Remove _database_health tables from all databases (over-engineered for single-user)
-- 5. Remove satellite_regime_performance table (unused tracking)

-- ============================================================================
-- Portfolio Database (portfolio.db)
-- ============================================================================

-- Remove snapshot_json column (unused field)
ALTER TABLE portfolio_snapshots DROP COLUMN snapshot_json;

-- Remove _database_health table
DROP TABLE IF EXISTS _database_health;

-- ============================================================================
-- History Database (history.db)
-- ============================================================================

-- Remove cleanup_log table (audit trail not needed for calculations)
DROP TABLE IF EXISTS cleanup_log;

-- Remove symbol_removals table (simplify cleanup - delete orphans immediately)
DROP TABLE IF EXISTS symbol_removals;

-- Remove _database_health table
DROP TABLE IF EXISTS _database_health;

-- ============================================================================
-- Universe Database (universe.db)
-- ============================================================================

DROP TABLE IF EXISTS _database_health;

-- ============================================================================
-- Agents Database (agents.db)
-- ============================================================================

DROP TABLE IF EXISTS _database_health;

-- ============================================================================
-- Cache Database (cache.db)
-- ============================================================================

DROP TABLE IF EXISTS _database_health;

-- ============================================================================
-- Config Database (config.db)
-- ============================================================================

DROP TABLE IF EXISTS _database_health;

-- ============================================================================
-- Ledger Database (ledger.db)
-- ============================================================================

DROP TABLE IF EXISTS _database_health;

-- ============================================================================
-- Satellites Database (satellites.db)
-- ============================================================================

-- Remove satellite_regime_performance table (unused tracking)
DROP TABLE IF EXISTS satellite_regime_performance;
