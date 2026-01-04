package satellites

import (
	"database/sql"
	"fmt"
)

// InitSchema initializes the satellites database schema
// Faithful translation from Python: app/modules/satellites/database/schemas.py
func InitSchema(db *sql.DB) error {
	schema := `
-- Bucket definitions (core + satellites)
CREATE TABLE IF NOT EXISTS buckets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,                    -- 'core' or 'satellite'
    notes TEXT,                            -- User documentation
    target_pct REAL,                       -- Current target allocation (0.0-1.0)
    min_pct REAL,                          -- Hibernation threshold
    max_pct REAL,                          -- Maximum allowed
    consecutive_losses INTEGER DEFAULT 0,
    max_consecutive_losses INTEGER DEFAULT 5,
    high_water_mark REAL DEFAULT 0,
    high_water_mark_date TEXT,
    loss_streak_paused_at TEXT,
    status TEXT DEFAULT 'active',          -- 'research', 'accumulating', 'active', 'hibernating', 'paused', 'retired'
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    agent_id TEXT                          -- References agent_configs.id in agents.db (added in migration 007)
);

CREATE INDEX IF NOT EXISTS idx_buckets_type ON buckets(type);
CREATE INDEX IF NOT EXISTS idx_buckets_status ON buckets(status);
CREATE INDEX IF NOT EXISTS idx_buckets_agent ON buckets(agent_id);

-- Satellite-specific settings (slider values and toggles)
CREATE TABLE IF NOT EXISTS satellite_settings (
    satellite_id TEXT PRIMARY KEY,
    preset TEXT,                           -- Strategy preset name
    risk_appetite REAL DEFAULT 0.5,        -- 0.0=Conservative, 1.0=Aggressive
    hold_duration REAL DEFAULT 0.5,        -- 0.0=Quick flips, 1.0=Patient holds
    entry_style REAL DEFAULT 0.5,          -- 0.0=Buy dips, 1.0=Buy breakouts
    position_spread REAL DEFAULT 0.5,      -- 0.0=Concentrated, 1.0=Diversified
    profit_taking REAL DEFAULT 0.5,        -- 0.0=Let winners run, 1.0=Take profits early
    trailing_stops INTEGER DEFAULT 0,
    follow_regime INTEGER DEFAULT 0,
    auto_harvest INTEGER DEFAULT 0,
    pause_high_volatility INTEGER DEFAULT 0,
    dividend_handling TEXT DEFAULT 'reinvest_same',  -- 'reinvest_same', 'send_to_core', 'accumulate_cash'
    -- Risk metric parameters (per-agent configuration)
    risk_free_rate REAL DEFAULT 0.035,     -- Annual risk-free rate (default 3.5%)
    sortino_mar REAL DEFAULT 0.05,         -- Minimum Acceptable Return for Sortino (default 5%)
    evaluation_period_days INTEGER DEFAULT 90,  -- Performance evaluation window (default 90 days)
    volatility_window INTEGER DEFAULT 60,  -- Volatility calculation window (default 60 days)
    FOREIGN KEY (satellite_id) REFERENCES buckets(id) ON DELETE CASCADE
);

-- Virtual cash balances per bucket per currency
CREATE TABLE IF NOT EXISTS bucket_balances (
    bucket_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    balance REAL NOT NULL DEFAULT 0,
    last_updated TEXT NOT NULL,
    PRIMARY KEY (bucket_id, currency),
    FOREIGN KEY (bucket_id) REFERENCES buckets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bucket_balances_bucket ON bucket_balances(bucket_id);

-- Transaction audit trail for bucket cash flows
CREATE TABLE IF NOT EXISTS bucket_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bucket_id TEXT NOT NULL,
    type TEXT NOT NULL,                    -- 'deposit', 'reallocation', 'trade_buy', 'trade_sell', 'dividend', 'transfer_in', 'transfer_out'
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (bucket_id) REFERENCES buckets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bucket_transactions_bucket ON bucket_transactions(bucket_id);
CREATE INDEX IF NOT EXISTS idx_bucket_transactions_type ON bucket_transactions(type);
CREATE INDEX IF NOT EXISTS idx_bucket_transactions_created ON bucket_transactions(created_at);

-- Allocation settings (global configuration)
CREATE TABLE IF NOT EXISTS allocation_settings (
    key TEXT PRIMARY KEY,
    value REAL NOT NULL,
    description TEXT
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);
`

	_, err := db.Exec(schema)
	if err != nil {
		return fmt.Errorf("failed to initialize schema: %w", err)
	}

	// Insert default allocation settings
	defaultSettings := []struct {
		key         string
		value       float64
		description string
	}{
		{"satellite_budget_pct", 0.00, "Total budget for all satellites combined (0.0-1.0)"},
		{"satellite_min_pct", 0.02, "Minimum viable allocation for any single satellite"},
		{"satellite_max_pct", 0.15, "Maximum any single satellite can reach"},
		{"evaluation_months", 3, "Months between reallocation cycles"},
		{"reallocation_dampening", 0.5, "Dampening factor for allocation changes (0.0-1.0)"},
		// Global risk metric defaults
		{"default_risk_free_rate", 0.035, "Default annual risk-free rate (3.5%)"},
		{"default_sortino_mar", 0.05, "Default Sortino Minimum Acceptable Return (5%)"},
		{"default_evaluation_days", 90, "Default performance evaluation period (days)"},
	}

	for _, setting := range defaultSettings {
		_, err = db.Exec(
			`INSERT OR IGNORE INTO allocation_settings (key, value, description)
			 VALUES (?, ?, ?)`,
			setting.key, setting.value, setting.description,
		)
		if err != nil {
			return fmt.Errorf("failed to insert default setting %s: %w", setting.key, err)
		}
	}

	// Insert schema version
	_, err = db.Exec(
		`INSERT OR IGNORE INTO schema_version (version, applied_at, description)
		 VALUES (1, datetime('now'), 'Initial satellites schema')`,
	)
	if err != nil {
		return fmt.Errorf("failed to insert schema version: %w", err)
	}

	return nil
}
