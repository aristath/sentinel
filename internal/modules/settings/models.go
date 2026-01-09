package settings

// SettingDefaults holds all default values for configurable settings
// Faithful translation from Python: app/api/settings.py -> SETTING_DEFAULTS
var SettingDefaults = map[string]interface{}{
	// Security scoring
	"min_security_score":   0.5,  // Minimum score for security to be recommended (0-1)
	"target_annual_return": 0.11, // Optimal CAGR for scoring (11%)
	"market_avg_pe":        22.0, // Reference P/E for valuation

	// Trading mode
	"trading_mode": "research", // "live" or "research" - blocks trades in research mode

	// API credentials
	"tradernet_api_key":    "", // Tradernet API key
	"tradernet_api_secret": "", // Tradernet API secret
	"github_token":         "", // GitHub personal access token for deployment artifact downloads

	// Cloudflare R2 Backup settings
	"r2_account_id":            "",      // Cloudflare R2 account ID
	"r2_access_key_id":         "",      // R2 access key ID
	"r2_secret_access_key":     "",      // R2 secret access key
	"r2_bucket_name":           "",      // R2 bucket name
	"r2_backup_enabled":        0.0,     // 1.0 = enabled, 0.0 = disabled
	"r2_backup_schedule":       "daily", // Backup schedule: "daily", "weekly", or "monthly"
	"r2_backup_retention_days": 90.0,    // Days to keep backups (0 = keep forever)

	// Portfolio Optimizer settings
	"optimizer_blend":             0.5,   // 0.0 = pure Mean-Variance, 1.0 = pure HRP
	"optimizer_target_return":     0.11,  // Target annual return for MV component
	"target_return_threshold_pct": 0.80,  // Threshold percentage for target return filtering (0.80 = 80% of target, default for retirement funds)
	"optimizer_max_cvar_95":       -0.15, // Maximum CVaR at 95% confidence (max -15% loss in tail risk)

	// Cash management
	"min_cash_reserve": 500.0, // Minimum cash to keep (never fully deploy)

	// LED Matrix settings
	"ticker_speed":        50.0,  // Ticker scroll speed in ms per frame (lower = faster)
	"led_brightness":      150.0, // LED brightness (0-255)
	"ticker_show_value":   1.0,   // Show portfolio value
	"ticker_show_cash":    1.0,   // Show cash balance
	"ticker_show_actions": 1.0,   // Show next actions (BUY/SELL)
	"ticker_show_amounts": 1.0,   // Show amounts for actions
	"ticker_max_actions":  3.0,   // Max recommendations to show (buy + sell)

	// Job scheduling intervals
	"job_sync_cycle_minutes":  15.0, // Unified sync cycle interval
	"job_maintenance_hour":    3.0,  // Daily maintenance hour (0-23)
	"job_auto_deploy_minutes": 5.0,  // Auto-deploy check interval (minutes)

	// Universe Pruning settings
	"universe_pruning_enabled":         1.0,  // 1.0 = enabled, 0.0 = disabled
	"universe_pruning_score_threshold": 0.50, // Minimum average score to keep security
	"universe_pruning_months":          3.0,  // Number of months to look back for scores
	"universe_pruning_min_samples":     2.0,  // Minimum number of score samples required
	"universe_pruning_check_delisted":  1.0,  // 1.0 = check for delisted securities

	// Event-Driven Rebalancing settings
	"event_driven_rebalancing_enabled":    1.0,  // 1.0 = enabled, 0.0 = disabled
	"rebalance_position_drift_threshold":  0.05, // Position drift threshold (0.05 = 5%)
	"rebalance_cash_threshold_multiplier": 2.0,  // Cash threshold = multiplier × min_trade_size

	// Trade Frequency Limits settings
	"trade_frequency_limits_enabled":  1.0,  // 1.0 = enabled, 0.0 = disabled
	"min_time_between_trades_minutes": 60.0, // Minimum minutes between any trades
	"max_trades_per_day":              4.0,  // Maximum trades per calendar day
	"max_trades_per_week":             10.0, // Maximum trades per rolling 7-day window

	// Trade Safety settings
	"buy_cooldown_days":   30.0, // Prevent buying same security within 30 days
	"min_hold_days":       90.0, // Minimum hold time before selling (days)
	"max_price_age_hours": 48.0, // Maximum age of price data before considered stale (hours)

	// Transaction costs (used by trade execution and planner)
	"transaction_cost_fixed":   2.0,   // Fixed transaction cost per trade in EUR
	"transaction_cost_percent": 0.002, // Variable transaction cost as decimal (0.002 = 0.2%)

	// Security Discovery settings
	"security_discovery_enabled":               1.0,          // 1.0 = enabled, 0.0 = disabled
	"security_discovery_score_threshold":       0.75,         // Minimum score to add security
	"security_discovery_max_per_month":         2.0,          // Maximum securities to add per month
	"security_discovery_require_manual_review": 0.0,          // 1.0 = require review, 0.0 = auto-add
	"security_discovery_geographies":           "EU,US,ASIA", // Comma-separated geography list
	"security_discovery_exchanges":             "usa,europe", // Comma-separated exchange list
	"security_discovery_min_volume":            1000000.0,    // Minimum daily volume for liquidity
	"security_discovery_fetch_limit":           50.0,         // Maximum candidates to fetch from API

	// Market Regime Detection settings
	"market_regime_detection_enabled":     1.0,   // 1.0 = enabled, 0.0 = disabled
	"market_regime_bull_cash_reserve":     0.02,  // Cash reserve percentage in bull market (2%)
	"market_regime_bear_cash_reserve":     0.05,  // Cash reserve percentage in bear market (5%)
	"market_regime_sideways_cash_reserve": 0.03,  // Cash reserve percentage in sideways market (3%)
	"market_regime_bull_threshold":        0.05,  // Threshold for bull market (5% above MA)
	"market_regime_bear_threshold":        -0.05, // Threshold for bear market (-5% below MA)

	// Virtual test currency (for testing planner in research mode)
	"virtual_test_cash": 0.0, // TEST currency amount (only visible in research mode)

	// Portfolio Display Mode settings
	"display_mode":               "STATS", // Display mode: "STATS" (CPU/RAM), "TICKER", or "PORTFOLIO"
	"display_min_cluster_size":   5.0,     // Minimum pixels per top holding cluster
	"display_top_holdings_count": 5.0,     // Number of top holdings to show as clusters

	// Performance calculation weights
	"display_performance_trailing12mo_weight": 0.70, // Weight for trailing 12mo CAGR
	"display_performance_inception_weight":    0.30, // Weight for since-inception CAGR

	// Performance thresholds (vs target)
	"display_performance_thriving_threshold":  0.03,  // +3% above target = thriving
	"display_performance_on_target_threshold": 0.00,  // ±0% from target = on target
	"display_performance_below_threshold":     -0.03, // -3% below target = below

	// Diversification health thresholds
	"display_diversification_healthy_deviation":  0.05, // ±5% from target = healthy
	"display_diversification_warning_deviation":  0.10, // ±10% = warning
	"display_diversification_critical_deviation": 0.15, // >15% = critical

	// Concentration risk thresholds
	"display_concentration_warning_threshold":  0.25, // 25% in one holding = warning
	"display_concentration_critical_threshold": 0.40, // 40% = critical

	// Visual parameter ranges - Thriving state (≥ +3% above target)
	"display_pixels_thriving_min":     70.0,
	"display_pixels_thriving_max":     104.0,
	"display_brightness_thriving_min": 180.0,
	"display_brightness_thriving_max": 220.0,

	// Visual parameter ranges - On Target state (±0% from target)
	"display_pixels_on_target_min":     50.0,
	"display_pixels_on_target_max":     70.0,
	"display_brightness_on_target_min": 150.0,
	"display_brightness_on_target_max": 180.0,

	// Visual parameter ranges - Below Target state (-3% to 0%)
	"display_pixels_below_min":     30.0,
	"display_pixels_below_max":     50.0,
	"display_brightness_below_min": 120.0,
	"display_brightness_below_max": 150.0,

	// Visual parameter ranges - Critical state (< -3%)
	"display_pixels_critical_min":     10.0,
	"display_pixels_critical_max":     30.0,
	"display_brightness_critical_min": 100.0,
	"display_brightness_critical_max": 120.0,

	// Background visual ranges
	"display_background_brightness_min": 80.0,
	"display_background_brightness_max": 120.0,

	// Animation behavior
	"display_clustering_strength_base":     4.0,   // Base clustering strength (1-10)
	"display_clustering_chaos_multiplier":  2.5,   // Multiply for imbalanced states
	"display_animation_speed_smooth":       100.0, // ms per frame for smooth states
	"display_animation_speed_chaotic":      40.0,  // ms per frame for chaotic states
	"display_transition_smoothing_seconds": 300.0, // 5min smooth transitions
	"display_enable_vertical_bias":         1.0,   // Enable rising/sinking effect (1.0 = yes)
	"display_momentum_sensitivity":         0.5,   // How much recent trend affects drift (0-1)

	// UI Preferences
	"security_table_visible_columns": `{"chart":true,"company":true,"country":true,"exchange":true,"sector":true,"tags":true,"value":true,"score":true,"mult":true,"bs":true,"priority":true}`, // JSON string with column visibility preferences

	// Limit Order Protection
	"limit_order_buffer_percent": 0.05, // 5% buffer for limit orders (buy up to 5% above Yahoo price, sell down to 5% below)
}

// StringSettings defines which settings should be treated as strings rather than floats
var StringSettings = map[string]bool{
	"trading_mode":                   true,
	"security_discovery_geographies": true,
	"security_discovery_exchanges":   true,
	"risk_profile":                   true,
	"display_mode":                   true,
	"tradernet_api_key":              true,
	"tradernet_api_secret":           true,
	"github_token":                   true,
	"security_table_visible_columns": true,
	"r2_account_id":                  true,
	"r2_access_key_id":               true,
	"r2_secret_access_key":           true,
	"r2_bucket_name":                 true,
	"r2_backup_schedule":             true,
}

// SettingDescriptions holds human-readable descriptions for all settings
var SettingDescriptions = map[string]string{
	"limit_order_buffer_percent": "Buffer percentage for limit orders (5% = buy up to 5% above Yahoo price, sell down to 5% below)",
}

// SettingUpdate represents a setting value update request
type SettingUpdate struct {
	Value interface{} `json:"value"`
}

// TradingModeResponse represents the trading mode response
type TradingModeResponse struct {
	TradingMode string `json:"trading_mode"`
}

// TradingModeToggleResponse represents the trading mode toggle response
type TradingModeToggleResponse struct {
	TradingMode  string `json:"trading_mode"`
	PreviousMode string `json:"previous_mode"`
}

// CacheStats represents cache statistics
type CacheStats struct {
	SimpleCache    SimpleCacheStats    `json:"simple_cache"`
	CalculationsDB CalculationsDBStats `json:"calculations_db"`
}

// SimpleCacheStats represents simple cache statistics
type SimpleCacheStats struct {
	Entries int `json:"entries"`
}

// CalculationsDBStats represents calculations database statistics
type CalculationsDBStats struct {
	Entries        int `json:"entries"`
	ExpiredCleaned int `json:"expired_cleaned"`
}
