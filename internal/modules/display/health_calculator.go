package display

import (
	"database/sql"
	"fmt"
	"math"

	"github.com/aristath/sentinel/internal/modules/settings"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// SecurityHealth represents the health score for a single security
type SecurityHealth struct {
	Symbol string  `json:"symbol"`
	Health float64 `json:"health"` // 0.0-1.0 normalized
}

// HealthUpdate represents a complete health update for the portfolio
type HealthUpdate struct {
	Securities []SecurityHealth `json:"securities"`
	Timestamp  int64            `json:"timestamp"`
}

// HealthCalculator calculates combined health scores for securities
type HealthCalculator struct {
	portfolioDB     *sql.DB
	historyDBClient universe.HistoryDBInterface
	configDB        *sql.DB
	securityPerf    *SecurityPerformanceService
	log             zerolog.Logger
	scoreWeight     float64
	perfWeight      float64
	volWeight       float64
	maxSecurities   int
}

// NewHealthCalculator creates a new health calculator
func NewHealthCalculator(
	portfolioDB *sql.DB,
	historyDBClient universe.HistoryDBInterface,
	configDB *sql.DB,
	log zerolog.Logger,
) *HealthCalculator {
	securityPerf := NewSecurityPerformanceService(historyDBClient, log)

	return &HealthCalculator{
		portfolioDB:     portfolioDB,
		historyDBClient: historyDBClient,
		configDB:        configDB,
		securityPerf:    securityPerf,
		log:             log.With().Str("service", "health_calculator").Logger(),
		scoreWeight:     0.4,
		perfWeight:      0.4,
		volWeight:       0.2,
		maxSecurities:   20,
	}
}

// CalculateAllHealth calculates health scores for all holdings
func (h *HealthCalculator) CalculateAllHealth() (*HealthUpdate, error) {
	// Load settings
	h.loadSettings()

	// Get target annual return
	target := h.getSettingFloat("target_annual_return", 0.11)

	// Get all holdings ordered by market value
	holdings, err := h.getHoldings()
	if err != nil {
		return nil, fmt.Errorf("failed to get holdings: %w", err)
	}

	// Limit to max securities
	if len(holdings) > h.maxSecurities {
		holdings = holdings[:h.maxSecurities]
	}

	securities := make([]SecurityHealth, 0, len(holdings))

	for _, holding := range holdings {
		health, err := h.calculateSecurityHealth(holding.Symbol, holding.ISIN, target)
		if err != nil {
			h.log.Warn().
				Err(err).
				Str("symbol", holding.Symbol).
				Msg("Failed to calculate health, using 0.5")
			health = 0.5 // Neutral default
		}

		securities = append(securities, SecurityHealth{
			Symbol: holding.Symbol,
			Health: health,
		})

		h.log.Debug().
			Str("symbol", holding.Symbol).
			Float64("health", health).
			Msg("Calculated security health")
	}

	return &HealthUpdate{
		Securities: securities,
		Timestamp:  h.getCurrentTimestamp(),
	}, nil
}

// calculateSecurityHealth calculates combined health score for a security
func (h *HealthCalculator) calculateSecurityHealth(symbol, isin string, target float64) (float64, error) {
	// Component 1: Security Score (0-100 scale)
	scoreComponent, err := h.getScoreComponent(symbol)
	if err != nil {
		h.log.Debug().Err(err).Str("symbol", symbol).Msg("Failed to get score component")
		scoreComponent = 0.5 // Neutral default
	}

	// Component 2: Performance vs Target
	perfComponent, err := h.getPerformanceComponent(isin, target)
	if err != nil {
		h.log.Debug().Err(err).Str("symbol", symbol).Msg("Failed to get performance component")
		perfComponent = 0.5 // Neutral default
	}

	// Component 3: Volatility (inverse - lower is better)
	volComponent, err := h.getVolatilityComponent(isin)
	if err != nil {
		h.log.Debug().Err(err).Str("symbol", symbol).Msg("Failed to get volatility component")
		volComponent = 0.5 // Neutral default
	}

	// Weighted average
	health := (scoreComponent * h.scoreWeight) +
		(perfComponent * h.perfWeight) +
		(volComponent * h.volWeight)

	// Clamp to 0-1
	health = math.Max(0.0, math.Min(1.0, health))

	h.log.Debug().
		Str("symbol", symbol).
		Float64("score_component", scoreComponent).
		Float64("perf_component", perfComponent).
		Float64("vol_component", volComponent).
		Float64("health", health).
		Msg("Calculated health components")

	return health, nil
}

// getScoreComponent gets normalized security score (0-1)
func (h *HealthCalculator) getScoreComponent(symbol string) (float64, error) {
	var score sql.NullFloat64
	err := h.portfolioDB.QueryRow(`
		SELECT total_score
		FROM scores
		WHERE symbol = ?
		ORDER BY calculated_at DESC
		LIMIT 1
	`, symbol).Scan(&score)

	if err != nil {
		if err == sql.ErrNoRows {
			return 0.5, nil // No score available, use neutral
		}
		return 0, err
	}

	if !score.Valid {
		return 0.5, nil
	}

	// Normalize from 0-100 to 0-1
	normalized := score.Float64 / 100.0
	return math.Max(0.0, math.Min(1.0, normalized)), nil
}

// getPerformanceComponent gets normalized performance vs target (0-1)
func (h *HealthCalculator) getPerformanceComponent(isin string, target float64) (float64, error) {
	if isin == "" {
		return 0.5, nil // No ISIN, use neutral
	}

	// Get trailing 12mo CAGR
	cagr, err := h.securityPerf.CalculateTrailing12MoCAGR(isin)
	if err != nil || cagr == nil {
		return 0.5, nil
	}

	// Calculate performance vs target
	perfVsTarget := *cagr - target

	// Normalize: -10% to +10% maps to 0-1
	// Below -10% = 0, above +10% = 1
	normalized := (perfVsTarget + 0.10) / 0.20
	return math.Max(0.0, math.Min(1.0, normalized)), nil
}

// getVolatilityComponent gets normalized volatility component (0-1, inverted)
func (h *HealthCalculator) getVolatilityComponent(isin string) (float64, error) {
	if isin == "" {
		return 0.5, nil // No ISIN, use neutral
	}

	// Query volatility from portfolio DB using ISIN (scores table uses ISIN as PRIMARY KEY)
	var volatility sql.NullFloat64
	err := h.portfolioDB.QueryRow(`
		SELECT volatility
		FROM scores
		WHERE isin = ?
		ORDER BY calculated_at DESC
		LIMIT 1
	`, isin).Scan(&volatility)

	if err != nil {
		if err == sql.ErrNoRows {
			h.log.Debug().Str("isin", isin).Msg("No volatility data found, using neutral")
			return 0.5, nil
		}
		h.log.Warn().Err(err).Str("isin", isin).Msg("Failed to query volatility, using neutral")
		return 0.5, nil // Graceful degradation
	}

	if !volatility.Valid {
		return 0.5, nil
	}

	// Volatility is typically 0-100% (0-1.0)
	// Invert it: low volatility = high health
	// Normalize: 0% = 1.0, 50%+ = 0.0
	normalized := 1.0 - math.Min(volatility.Float64*2.0, 1.0)
	return math.Max(0.0, math.Min(1.0, normalized)), nil
}

// getHoldings returns all holdings ordered by market value
func (h *HealthCalculator) getHoldings() ([]struct {
	Symbol      string
	ISIN        string
	MarketValue float64
}, error) {
	rows, err := h.portfolioDB.Query(`
		SELECT symbol, isin, market_value_eur
		FROM positions
		WHERE quantity > 0
		ORDER BY market_value_eur DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var holdings []struct {
		Symbol      string
		ISIN        string
		MarketValue float64
	}

	for rows.Next() {
		var h struct {
			Symbol      string
			ISIN        string
			MarketValue float64
		}
		if err := rows.Scan(&h.Symbol, &h.ISIN, &h.MarketValue); err != nil {
			return nil, err
		}
		holdings = append(holdings, h)
	}

	return holdings, nil
}

// loadSettings loads configuration from settings
func (h *HealthCalculator) loadSettings() {
	h.scoreWeight = h.getSettingFloat("display_health_score_weight", 0.4)
	h.perfWeight = h.getSettingFloat("display_health_performance_weight", 0.4)
	h.volWeight = h.getSettingFloat("display_health_volatility_weight", 0.2)
	h.maxSecurities = int(h.getSettingFloat("display_health_max_securities", 20))
}

// getSettingFloat retrieves a float setting with fallback to default
func (h *HealthCalculator) getSettingFloat(key string, defaultVal float64) float64 {
	var value float64
	err := h.configDB.QueryRow("SELECT value FROM settings WHERE key = ?", key).Scan(&value)
	if err != nil {
		// Fallback to SettingDefaults
		if val, ok := settings.SettingDefaults[key]; ok {
			if fval, ok := val.(float64); ok {
				return fval
			}
		}
		return defaultVal
	}
	return value
}

// getCurrentTimestamp returns current Unix timestamp
func (h *HealthCalculator) getCurrentTimestamp() int64 {
	var ts int64
	err := h.portfolioDB.QueryRow("SELECT strftime('%s', 'now')").Scan(&ts)
	if err != nil {
		h.log.Warn().Err(err).Msg("Failed to get current timestamp, using 0")
		return 0
	}
	return ts
}
