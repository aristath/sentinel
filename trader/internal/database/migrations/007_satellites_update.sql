-- Satellites Database Schema Update
-- Migration 007: Update satellites.db schema for agent integration
--
-- This migration updates the satellites database to support agent-based strategies:
-- - Add agent_id column to buckets table (references agent_configs in agents.db)
-- - Remove strategy_type column (replaced by agent_id)
--
-- Each satellite bucket will reference a TOML strategy configuration (agent)
-- from the agents database.
--
-- Data Migration Note:
-- During Phase 6, if strategy_type column exists:
-- - Map strategy_type values to agent_id (may require manual config)
-- - Drop strategy_type column

-- Add agent_id column to buckets table
-- This references agent_configs.id in agents.db
-- NULL = bucket uses default/core strategy
-- Note: This migration is for satellites.db only
-- The migration system will skip this on databases where buckets table doesn't exist
ALTER TABLE buckets ADD COLUMN agent_id TEXT;

CREATE INDEX IF NOT EXISTS idx_buckets_agent ON buckets(agent_id);

-- Note: strategy_type column will be dropped during data migration (Phase 6)
-- Cannot drop here as it may contain data that needs to be migrated first
