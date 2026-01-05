-- Migration 028: Add security tags support
--
-- This migration creates tables for the security tagging system:
-- - tags: Tag definitions with ID (code-friendly) and name (human-readable)
-- - security_tags: Junction table linking securities to tags (many-to-many)
--
-- Tags are internal-only, auto-assigned by the app/planner based on security analysis.
-- Tags are updated daily via scheduled job.

-- Tags table: tag definitions with ID and human-readable name
CREATE TABLE IF NOT EXISTS tags (
    id TEXT PRIMARY KEY,  -- e.g., 'value-opportunity', 'volatile', 'stable'
    name TEXT NOT NULL,   -- e.g., 'Value Opportunity', 'Volatile', 'Stable'
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
) STRICT;

-- Security tags junction table: links securities to tags
CREATE TABLE IF NOT EXISTS security_tags (
    symbol TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (symbol, tag_id),
    FOREIGN KEY (symbol) REFERENCES securities(symbol) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
) STRICT;

CREATE INDEX IF NOT EXISTS idx_security_tags_symbol ON security_tags(symbol);
CREATE INDEX IF NOT EXISTS idx_security_tags_tag_id ON security_tags(tag_id);
