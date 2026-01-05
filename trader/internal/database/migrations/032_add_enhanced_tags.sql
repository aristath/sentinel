-- Migration 032: Add enhanced tags for algorithm improvements
--
-- This migration adds 20 new tags to support:
-- - Quality gates (quality-gate-pass, quality-gate-fail, quality-value)
-- - Bubble detection (bubble-risk, quality-high-cagr, poor-risk-adjusted, high-sharpe, high-sortino)
-- - Value trap detection (value-trap)
-- - Total return calculation (high-total-return, excellent-total-return, dividend-total-return, moderate-total-return)
-- - Optimizer alignment (underweight, target-aligned, needs-rebalance, slightly-overweight, slightly-underweight)
-- - Regime-specific adjustments (regime-bear-safe, regime-bull-growth, regime-sideways-value, regime-volatile)
--
-- All tags use INSERT OR IGNORE to avoid duplicates if migration is run multiple times.

-- Quality Gate Tags (3)
INSERT OR IGNORE INTO tags (id, name, created_at, updated_at) VALUES
    ('quality-gate-pass', 'Quality Gate Pass', datetime('now'), datetime('now')),
    ('quality-gate-fail', 'Quality Gate Fail', datetime('now'), datetime('now')),
    ('quality-value', 'Quality Value', datetime('now'), datetime('now'));

-- Bubble Detection Tags (5)
INSERT OR IGNORE INTO tags (id, name, created_at, updated_at) VALUES
    ('bubble-risk', 'Bubble Risk', datetime('now'), datetime('now')),
    ('quality-high-cagr', 'Quality High CAGR', datetime('now'), datetime('now')),
    ('poor-risk-adjusted', 'Poor Risk-Adjusted', datetime('now'), datetime('now')),
    ('high-sharpe', 'High Sharpe', datetime('now'), datetime('now')),
    ('high-sortino', 'High Sortino', datetime('now'), datetime('now'));

-- Value Trap Tags (1)
INSERT OR IGNORE INTO tags (id, name, created_at, updated_at) VALUES
    ('value-trap', 'Value Trap', datetime('now'), datetime('now'));

-- Total Return Tags (4)
INSERT OR IGNORE INTO tags (id, name, created_at, updated_at) VALUES
    ('high-total-return', 'High Total Return', datetime('now'), datetime('now')),
    ('excellent-total-return', 'Excellent Total Return', datetime('now'), datetime('now')),
    ('dividend-total-return', 'Dividend Total Return', datetime('now'), datetime('now')),
    ('moderate-total-return', 'Moderate Total Return', datetime('now'), datetime('now'));

-- Optimizer Alignment Tags (5)
INSERT OR IGNORE INTO tags (id, name, created_at, updated_at) VALUES
    ('underweight', 'Underweight', datetime('now'), datetime('now')),
    ('target-aligned', 'Target Aligned', datetime('now'), datetime('now')),
    ('needs-rebalance', 'Needs Rebalance', datetime('now'), datetime('now')),
    ('slightly-overweight', 'Slightly Overweight', datetime('now'), datetime('now')),
    ('slightly-underweight', 'Slightly Underweight', datetime('now'), datetime('now'));

-- Regime-Specific Tags (4)
INSERT OR IGNORE INTO tags (id, name, created_at, updated_at) VALUES
    ('regime-bear-safe', 'Bear Market Safe', datetime('now'), datetime('now')),
    ('regime-bull-growth', 'Bull Market Growth', datetime('now'), datetime('now')),
    ('regime-sideways-value', 'Sideways Value', datetime('now'), datetime('now')),
    ('regime-volatile', 'Regime Volatile', datetime('now'), datetime('now'));
