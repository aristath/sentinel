package settings

// SettingDefaults holds all default values for configurable settings
// Faithful translation from Python: app/api/settings.py -> SETTING_DEFAULTS
var SettingDefaults = map[string]interface{}{
	// Temperament settings (controls 150+ parameters system-wide)
	"risk_tolerance":         0.5, // Risk tolerance (0 = conservative, 0.5 = balanced, 1 = risk-taking)
	"temperament_aggression": 0.5, // Aggression level (0 = passive, 0.5 = balanced, 1 = aggressive)
	"temperament_patience":   0.5, // Patience level (0 = impatient, 0.5 = balanced, 1 = patient)

	// Security scoring
	"min_security_score":   0.5,  // Minimum score for security to be recommended (0-1)
	"target_annual_return": 0.11, // Optimal CAGR for scoring (11%)

	// Trading mode
	"trading_mode": "research", // "live" or "research" - blocks trades in research mode

	// API credentials (Tradernet is the sole data source)
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

	// Portfolio Optimizer settings (NOTE: optimizer_blend and optimizer_target_return moved to planner_settings)
	"target_return_threshold_pct": 0.80,  // Threshold percentage for target return filtering (0.80 = 80% of target, default for retirement funds)
	"optimizer_max_cvar_95":       -0.15, // Maximum CVaR at 95% confidence (max -15% loss in tail risk)

	// Cash management (NOTE: min_cash_reserve moved to planner_settings)

	// LED Matrix settings
	"ticker_speed":        50.0,  // Ticker scroll speed in ms per frame (lower = faster)
	"led_brightness":      150.0, // LED brightness (0-255)
	"ticker_show_value":   1.0,   // Show portfolio value
	"ticker_show_cash":    1.0,   // Show cash balance
	"ticker_show_actions": 1.0,   // Show next actions (BUY/SELL)
	"ticker_show_amounts": 1.0,   // Show amounts for actions
	"ticker_max_actions":  3.0,   // Max recommendations to show (buy + sell)

	// Portfolio health display settings (for HEALTH mode)
	"display_health_update_interval":    1800.0, // Seconds between health updates (30 min)
	"display_health_max_securities":     20.0,   // Max securities to display
	"display_health_score_weight":       0.4,    // Weight for security score in health calculation
	"display_health_performance_weight": 0.4,    // Weight for performance vs target in health
	"display_health_volatility_weight":  0.2,    // Weight for volatility in health (inverted)
	"display_health_min_brightness":     100.0,  // Minimum LED brightness for health mode
	"display_health_max_brightness":     180.0,  // Maximum LED brightness for health mode
	"display_health_cluster_radius":     2.5,    // Cluster size in pixels
	"display_health_animation_fps":      60.0,   // Animation frame rate (handled by MCU)
	"display_health_drift_speed":        0.5,    // Cluster movement speed multiplier

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

	// Transaction costs (NOTE: transaction_cost_fixed and transaction_cost_percent moved to planner_settings)

	// Market Regime Detection settings
	"market_regime_detection_enabled":     1.0,   // 1.0 = enabled, 0.0 = disabled
	"market_regime_bull_cash_reserve":     0.02,  // Cash reserve percentage in bull market (2%)
	"market_regime_bear_cash_reserve":     0.05,  // Cash reserve percentage in bear market (5%)
	"market_regime_sideways_cash_reserve": 0.03,  // Cash reserve percentage in sideways market (3%)
	"market_regime_bull_threshold":        0.05,  // Threshold for bull market (5% above MA)
	"market_regime_bear_threshold":        -0.05, // Threshold for bear market (-5% below MA)

	// Virtual test currency (for testing planner in research mode)
	"virtual_test_cash": 0.0, // TEST currency amount (only visible in research mode)

	// Cooloff bypass (for testing planner in research mode)
	"disable_cooloff_checks": 0.0, // 1.0 = disable cooloff checks (only effective in research mode)

	// Portfolio Display Mode settings
	"display_mode":               "TEXT", // Display mode: "TEXT" (ticker), "HEALTH" (animated), or "STATS" (pixel count)
	"display_min_cluster_size":   5.0,    // Minimum pixels per top holding cluster
	"display_top_holdings_count": 5.0,    // Number of top holdings to show as clusters

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
	"security_table_visible_columns": `{"chart":true,"company":true,"geography":true,"exchange":true,"sector":true,"tags":true,"value":true,"score":true,"mult":true,"bs":true,"priority":true}`, // JSON string with column visibility preferences

	// Limit Order Protection
	"limit_order_buffer_percent": 0.05, // 5% buffer for limit orders (buy up to 5% above market price, sell down to 5% below)

	// Order Book Analysis settings
	"enable_order_book_analysis":  1.0,  // 1.0 = enabled, 0.0 = disabled (fallback to Tradernet-only)
	"min_liquidity_multiple":      2.0,  // Required liquidity as multiple of trade size (2.0 = need 2x quantity)
	"order_book_depth_levels":     5.0,  // Number of order book levels to check for liquidity
	"price_discrepancy_threshold": 0.50, // Max allowed price difference between order book and validation source (0.50 = 50%, asymmetric)
}

// StringSettings defines which settings should be treated as strings rather than floats
var StringSettings = map[string]bool{
	"trading_mode":                   true,
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
	// Temperament settings
	"risk_tolerance":         "Risk tolerance level (0 = conservative/risk-averse, 0.5 = balanced, 1 = risk-taking). Controls volatility acceptance, drawdown tolerance, position concentration, quality floors.",
	"temperament_aggression": "Aggression level (0 = passive/conservative, 0.5 = balanced, 1 = aggressive). Controls scoring thresholds, action frequency, evaluation weights, position sizing, and opportunity pursuit.",
	"temperament_patience":   "Patience level (0 = impatient, 0.5 = balanced, 1 = patient). Controls hold periods, cooldowns, windfall thresholds, rebalance triggers, and dividend focus.",

	// Trading settings
	"limit_order_buffer_percent":  "Buffer percentage for limit orders (5% = buy up to 5% above market price, sell down to 5% below)",
	"enable_order_book_analysis":  "Enable order book analysis (1.0 = yes, 0.0 = no/Tradernet-only fallback)",
	"min_liquidity_multiple":      "Required liquidity as multiple of trade size (2.0 = need 2x quantity available)",
	"order_book_depth_levels":     "Number of order book levels to check for liquidity (default 5)",
	"price_discrepancy_threshold": "Max allowed price difference between order book and validation source (0.50 = 50%, asymmetric: blocks overpaying on BUY, underselling on SELL)",
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
