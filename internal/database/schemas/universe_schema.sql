-- Universe Database Schema
-- Single source of truth for universe.db
-- This schema represents the final state after all migrations

-- Securities table: investment universe (ISIN as PRIMARY KEY)
-- Migration 038: JSON storage - all security data stored as JSON blob in 'data' column
-- User-configurable fields (allow_buy, allow_sell, priority_multiplier) are stored in security_overrides
-- No soft delete (active column removed) - only hard delete supported
CREATE TABLE IF NOT EXISTS securities (
    isin TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    data TEXT NOT NULL CHECK (json_valid(data)),  -- JSON blob with validity check: {name, product_type, industry, geography, currency, fullExchangeName, market_code, min_lot, min_portfolio_target, max_portfolio_target, tradernet_raw}
    last_synced INTEGER                            -- Unix timestamp (seconds since epoch)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_securities_symbol ON securities(symbol);

-- Security overrides table: EAV pattern for user customizations
-- Stores overrides for fields like allow_buy, allow_sell, min_lot, priority_multiplier,
-- as well as user corrections to Tradernet-provided data (geography, industry, name, etc.)
-- Defaults (when no override exists):
--   allow_buy: true, allow_sell: true, min_lot: 1, priority_multiplier: 1.0
CREATE TABLE IF NOT EXISTS security_overrides (
    isin TEXT NOT NULL,
    field TEXT NOT NULL,               -- Field name (e.g., 'allow_buy', 'geography', 'min_lot')
    value TEXT NOT NULL,               -- Value as string (converted to appropriate type at read time)
    created_at INTEGER NOT NULL,       -- Unix timestamp (seconds since epoch)
    updated_at INTEGER NOT NULL,       -- Unix timestamp (seconds since epoch)
    PRIMARY KEY (isin, field),
    FOREIGN KEY (isin) REFERENCES securities(isin) ON DELETE CASCADE
) STRICT;

CREATE INDEX IF NOT EXISTS idx_security_overrides_isin ON security_overrides(isin);

-- Tags table: tag definitions with ID and human-readable name
CREATE TABLE IF NOT EXISTS tags (
    id TEXT PRIMARY KEY,  -- e.g., 'value-opportunity', 'volatile', 'stable'
    name TEXT NOT NULL,   -- e.g., 'Value Opportunity', 'Volatile', 'Stable'
    created_at INTEGER NOT NULL,      -- Unix timestamp (seconds since epoch)
    updated_at INTEGER NOT NULL       -- Unix timestamp (seconds since epoch)
) STRICT;

-- Security tags junction table: links securities to tags (many-to-many, ISIN-based)
CREATE TABLE IF NOT EXISTS security_tags (
    isin TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    created_at INTEGER NOT NULL,      -- Unix timestamp (seconds since epoch)
    updated_at INTEGER NOT NULL,     -- Unix timestamp (seconds since epoch)
    PRIMARY KEY (isin, tag_id),
    FOREIGN KEY (isin) REFERENCES securities(isin) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
) STRICT;

CREATE INDEX IF NOT EXISTS idx_security_tags_isin ON security_tags(isin);
CREATE INDEX IF NOT EXISTS idx_security_tags_tag_id ON security_tags(tag_id);

-- Insert default tags (from migrations 028 and 032)
-- Quality Gate Tags
INSERT OR IGNORE INTO tags (id, name, created_at, updated_at) VALUES
    ('quality-gate-pass', 'Quality Gate Pass', (strftime('%s', 'now')), (strftime('%s', 'now'))),
    ('quality-gate-fail', 'Quality Gate Fail', (strftime('%s', 'now')), (strftime('%s', 'now'))),
    ('quality-value', 'Quality Value', (strftime('%s', 'now')), (strftime('%s', 'now')));

-- Bubble Detection Tags
INSERT OR IGNORE INTO tags (id, name, created_at, updated_at) VALUES
    ('bubble-risk', 'Bubble Risk', (strftime('%s', 'now')), (strftime('%s', 'now'))),
    ('quality-high-cagr', 'Quality High CAGR', (strftime('%s', 'now')), (strftime('%s', 'now'))),
    ('poor-risk-adjusted', 'Poor Risk-Adjusted', (strftime('%s', 'now')), (strftime('%s', 'now'))),
    ('high-sharpe', 'High Sharpe', (strftime('%s', 'now')), (strftime('%s', 'now'))),
    ('high-sortino', 'High Sortino', (strftime('%s', 'now')), (strftime('%s', 'now')));

-- Value Trap Tags
INSERT OR IGNORE INTO tags (id, name, created_at, updated_at) VALUES
    ('value-trap', 'Value Trap', (strftime('%s', 'now')), (strftime('%s', 'now')));

-- Total Return Tags
INSERT OR IGNORE INTO tags (id, name, created_at, updated_at) VALUES
    ('high-total-return', 'High Total Return', (strftime('%s', 'now')), (strftime('%s', 'now'))),
    ('excellent-total-return', 'Excellent Total Return', (strftime('%s', 'now')), (strftime('%s', 'now'))),
    ('dividend-total-return', 'Dividend Total Return', (strftime('%s', 'now')), (strftime('%s', 'now'))),
    ('moderate-total-return', 'Moderate Total Return', (strftime('%s', 'now')), (strftime('%s', 'now')));

-- Optimizer Alignment Tags
INSERT OR IGNORE INTO tags (id, name, created_at, updated_at) VALUES
    ('underweight', 'Underweight', (strftime('%s', 'now')), (strftime('%s', 'now'))),
    ('target-aligned', 'Target Aligned', (strftime('%s', 'now')), (strftime('%s', 'now'))),
    ('needs-rebalance', 'Needs Rebalance', (strftime('%s', 'now')), (strftime('%s', 'now'))),
    ('slightly-overweight', 'Slightly Overweight', (strftime('%s', 'now')), (strftime('%s', 'now'))),
    ('slightly-underweight', 'Slightly Underweight', (strftime('%s', 'now')), (strftime('%s', 'now')));

-- Regime-Specific Tags
INSERT OR IGNORE INTO tags (id, name, created_at, updated_at) VALUES
    ('regime-bear-safe', 'Bear Market Safe', (strftime('%s', 'now')), (strftime('%s', 'now'))),
    ('regime-bull-growth', 'Bull Market Growth', (strftime('%s', 'now')), (strftime('%s', 'now'))),
    ('regime-sideways-value', 'Sideways Value', (strftime('%s', 'now')), (strftime('%s', 'now'))),
    ('regime-volatile', 'Regime Volatile', (strftime('%s', 'now')), (strftime('%s', 'now')));
