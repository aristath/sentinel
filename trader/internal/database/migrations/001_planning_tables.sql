-- Planning Module Database Schema
-- Migration 001: Create planning tables

-- Sequences table: tracks all candidate sequences
CREATE TABLE IF NOT EXISTS sequences (
    sequence_hash TEXT NOT NULL,
    portfolio_hash TEXT NOT NULL,
    priority REAL NOT NULL,
    sequence_json TEXT NOT NULL,  -- JSON serialized List[ActionCandidate]
    depth INTEGER NOT NULL,       -- Sequence depth (1-5)
    pattern_type TEXT,            -- Pattern that generated this (e.g., 'direct_buy', 'combinatorial')
    completed INTEGER DEFAULT 0,  -- 0 = not evaluated, 1 = evaluated
    evaluated_at TEXT,            -- ISO timestamp when evaluated (NULL if not evaluated)
    created_at TEXT NOT NULL,
    PRIMARY KEY (sequence_hash, portfolio_hash)
);

CREATE INDEX IF NOT EXISTS idx_sequences_portfolio ON sequences(portfolio_hash);
CREATE INDEX IF NOT EXISTS idx_sequences_priority ON sequences(portfolio_hash, priority DESC, completed);
CREATE INDEX IF NOT EXISTS idx_sequences_completed ON sequences(portfolio_hash, completed);

-- Evaluations table: stores evaluation results
CREATE TABLE IF NOT EXISTS evaluations (
    sequence_hash TEXT NOT NULL,
    portfolio_hash TEXT NOT NULL,
    end_score REAL NOT NULL,
    breakdown_json TEXT NOT NULL,  -- JSON serialized score breakdown
    end_cash REAL NOT NULL,
    end_context_positions_json TEXT NOT NULL,  -- JSON serialized Dict[str, float]
    div_score REAL NOT NULL,      -- Diversification score
    total_value REAL NOT NULL,    -- Total portfolio value after sequence
    evaluated_at TEXT NOT NULL,
    PRIMARY KEY (sequence_hash, portfolio_hash)
);

CREATE INDEX IF NOT EXISTS idx_evaluations_portfolio ON evaluations(portfolio_hash);
CREATE INDEX IF NOT EXISTS idx_evaluations_score ON evaluations(portfolio_hash, end_score DESC);

-- Best result table: tracks best sequence found so far
CREATE TABLE IF NOT EXISTS best_result (
    portfolio_hash TEXT PRIMARY KEY,
    best_sequence_hash TEXT NOT NULL,
    best_score REAL NOT NULL,
    updated_at TEXT NOT NULL
);

-- Planner configurations: named TOML configurations for per-bucket planners
CREATE TABLE IF NOT EXISTS planner_configs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,              -- Display name/title (e.g., "Aggressive Growth")
    toml_config TEXT NOT NULL,       -- TOML configuration string
    bucket_id TEXT,                  -- Associated bucket (nullable for templates)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_planner_configs_bucket ON planner_configs(bucket_id);

-- Planner config history: version tracking and backup on every save
CREATE TABLE IF NOT EXISTS planner_config_history (
    id TEXT PRIMARY KEY,
    planner_config_id TEXT NOT NULL,
    name TEXT NOT NULL,
    toml_config TEXT NOT NULL,
    saved_at TEXT NOT NULL,
    FOREIGN KEY (planner_config_id) REFERENCES planner_configs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_planner_config_history_planner ON planner_config_history(planner_config_id);
CREATE INDEX IF NOT EXISTS idx_planner_config_history_saved ON planner_config_history(saved_at DESC);
