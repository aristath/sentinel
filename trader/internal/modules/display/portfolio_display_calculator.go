package display

import (
	"database/sql"
	"fmt"
	"math"
	"path/filepath"
	"strings"

	_ "github.com/mattn/go-sqlite3"

	"github.com/aristath/arduino-trader/internal/modules/settings"
	"github.com/rs/zerolog"
)

// PortfolioDisplayCalculator calculates portfolio display state from metrics
type PortfolioDisplayCalculator struct {
	universeDB    *sql.DB
	portfolioDB   *sql.DB
	portfolioPerf *PortfolioPerformanceService
	dataDir       string
	log           zerolog.Logger
}

// NewPortfolioDisplayCalculator creates a new portfolio display calculator
func NewPortfolioDisplayCalculator(
	universeDB, portfolioDB *sql.DB,
	portfolioPerf *PortfolioPerformanceService,
	dataDir string,
	log zerolog.Logger,
) *PortfolioDisplayCalculator {
	return &PortfolioDisplayCalculator{
		universeDB:    universeDB,
		portfolioDB:   portfolioDB,
		portfolioPerf: portfolioPerf,
		dataDir:       dataDir,
		log:           log.With().Str("service", "portfolio_display_calculator").Logger(),
	}
}

// CalculateDisplayState calculates the complete portfolio display state
func (c *PortfolioDisplayCalculator) CalculateDisplayState() (*PortfolioDisplayState, error) {
	// Get overall portfolio performance
	weightedPerf, err := c.portfolioPerf.CalculateWeightedPerformance()
	if err != nil {
		c.log.Warn().Err(err).Msg("Failed to calculate weighted performance, using 0")
		weightedPerf = 0
	}

	perfVsTarget, err := c.portfolioPerf.GetPerformanceVsTarget()
	if err != nil {
		c.log.Warn().Err(err).Msg("Failed to calculate performance vs target, using 0")
		perfVsTarget = 0
	}

	target := c.getSettingFloat("target_annual_return", 0.11)

	// Get top 5 holdings
	topHoldings, err := c.getTopHoldings(5)
	if err != nil {
		return nil, fmt.Errorf("failed to get top holdings: %w", err)
	}

	// Calculate total portfolio value
	totalValue, err := c.getTotalPortfolioValue()
	if err != nil {
		return nil, fmt.Errorf("failed to get total portfolio value: %w", err)
	}

	// Calculate clusters for top 5 holdings
	clusters := []ClusterData{}
	totalPixelsUsed := 0
	minClusterSize := int(c.getSettingFloat("display_min_cluster_size", 5.0))

	for i, holding := range topHoldings {
		// Calculate portfolio percentage
		pctOfPortfolio := holding.MarketValue / totalValue

		// Get security performance from history DB
		securityPerf, err := c.getSecurityPerformance(holding.Symbol, target)
		if err != nil {
			c.log.Warn().
				Err(err).
				Str("symbol", holding.Symbol).
				Msg("Failed to get security performance, using 0")
			securityPerf = 0
		}

		// Calculate visual parameters for this cluster
		params := c.calculateVisualParameters(securityPerf, target)

		// Calculate pixel count (proportional to portfolio %, min 5 pixels)
		pixels := int(math.Round(pctOfPortfolio * 104))
		if pixels < minClusterSize {
			pixels = minClusterSize
		}

		cluster := ClusterData{
			ClusterID:    i + 1, // 1-5
			Symbol:       holding.Symbol,
			Pixels:       pixels,
			Brightness:   params.Brightness,
			Clustering:   params.Clustering,
			Speed:        params.Speed,
			CAGR:         securityPerf,
			PortfolioPct: pctOfPortfolio * 100,
		}

		clusters = append(clusters, cluster)
		totalPixelsUsed += pixels

		c.log.Debug().
			Int("cluster_id", cluster.ClusterID).
			Str("symbol", cluster.Symbol).
			Int("pixels", cluster.Pixels).
			Float64("pct", cluster.PortfolioPct).
			Msg("Created cluster")
	}

	// Calculate background cluster (positions 6+)
	backgroundPct := c.calculateBackgroundPercentage(topHoldings, totalValue)
	backgroundPerf := c.calculateBackgroundPerformance(topHoldings, target)
	backgroundParams := c.calculateVisualParameters(backgroundPerf, target)

	// Adjust background brightness to be lower
	backgroundBrightness := c.adjustBackgroundBrightness(backgroundParams.Brightness)

	backgroundPixels := 104 - totalPixelsUsed
	if backgroundPixels < 0 {
		backgroundPixels = 0
	}

	backgroundCluster := ClusterData{
		ClusterID:    0, // 0 = background
		Symbol:       "",
		Pixels:       backgroundPixels,
		Brightness:   backgroundBrightness,
		Clustering:   backgroundParams.Clustering,
		Speed:        backgroundParams.Speed,
		CAGR:         backgroundPerf,
		PortfolioPct: backgroundPct * 100,
	}

	clusters = append(clusters, backgroundCluster)

	// Build final state
	state := &PortfolioDisplayState{
		Mode:     "PORTFOLIO",
		Clusters: clusters,
	}
	state.Metadata.PortfolioPerformance = weightedPerf
	state.Metadata.PerformanceVsTarget = perfVsTarget
	state.Metadata.TotalPixels = 104

	c.log.Info().
		Int("num_clusters", len(clusters)).
		Float64("portfolio_perf", weightedPerf).
		Float64("perf_vs_target", perfVsTarget).
		Msg("Calculated portfolio display state")

	return state, nil
}

// calculateVisualParameters maps performance metrics to visual parameters
func (c *PortfolioDisplayCalculator) calculateVisualParameters(perfVsTarget, target float64) VisualParameters {
	// Get thresholds from settings
	thrivingThreshold := c.getSettingFloat("display_performance_thriving_threshold", 0.03)
	onTargetThreshold := c.getSettingFloat("display_performance_on_target_threshold", 0.00)
	belowThreshold := c.getSettingFloat("display_performance_below_threshold", -0.03)

	// Determine state based on performance vs target
	var params VisualParameters

	if perfVsTarget >= thrivingThreshold {
		// Thriving state
		params.Brightness = c.mapRange(perfVsTarget, thrivingThreshold, thrivingThreshold+0.10,
			c.getSettingFloat("display_brightness_thriving_min", 180),
			c.getSettingFloat("display_brightness_thriving_max", 220))
		params.Clustering = 3 // Loose, organic
		params.Speed = int(c.getSettingFloat("display_animation_speed_smooth", 100))

	} else if perfVsTarget >= onTargetThreshold {
		// On target state
		params.Brightness = c.mapRange(perfVsTarget, onTargetThreshold, thrivingThreshold,
			c.getSettingFloat("display_brightness_on_target_min", 150),
			c.getSettingFloat("display_brightness_on_target_max", 180))
		params.Clustering = 4 // Moderate
		params.Speed = int(c.getSettingFloat("display_animation_speed_smooth", 100))

	} else if perfVsTarget >= belowThreshold {
		// Below target state
		params.Brightness = c.mapRange(perfVsTarget, belowThreshold, onTargetThreshold,
			c.getSettingFloat("display_brightness_below_min", 120),
			c.getSettingFloat("display_brightness_below_max", 150))
		params.Clustering = 5 // Moderate-tight
		params.Speed = int(c.getSettingFloat("display_animation_speed_smooth", 100))

	} else {
		// Critical state
		params.Brightness = c.mapRange(perfVsTarget, belowThreshold-0.10, belowThreshold,
			c.getSettingFloat("display_brightness_critical_min", 100),
			c.getSettingFloat("display_brightness_critical_max", 120))
		params.Clustering = 7 // Tight, erratic
		params.Speed = int(c.getSettingFloat("display_animation_speed_chaotic", 40))
	}

	// Clamp values
	params.Brightness = clamp(params.Brightness, 100, 220)
	params.Clustering = clamp(params.Clustering, 1, 10)
	params.Speed = clamp(params.Speed, 10, 500)

	return params
}

// getTopHoldings returns top N holdings by market value
func (c *PortfolioDisplayCalculator) getTopHoldings(n int) ([]struct {
	Symbol      string
	MarketValue float64
}, error) {
	rows, err := c.portfolioDB.Query(`
		SELECT symbol, market_value_eur
		FROM positions
		WHERE quantity > 0
		ORDER BY market_value_eur DESC
		LIMIT ?
	`, n)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var holdings []struct {
		Symbol      string
		MarketValue float64
	}

	for rows.Next() {
		var h struct {
			Symbol      string
			MarketValue float64
		}
		if err := rows.Scan(&h.Symbol, &h.MarketValue); err != nil {
			return nil, err
		}
		holdings = append(holdings, h)
	}

	return holdings, nil
}

// getTotalPortfolioValue calculates total portfolio market value
func (c *PortfolioDisplayCalculator) getTotalPortfolioValue() (float64, error) {
	var total float64
	err := c.portfolioDB.QueryRow(`
		SELECT COALESCE(SUM(market_value_eur), 0)
		FROM positions
		WHERE quantity > 0
	`).Scan(&total)
	return total, err
}

// getSecurityPerformance gets trailing 12mo CAGR for a security
func (c *PortfolioDisplayCalculator) getSecurityPerformance(symbol string, target float64) (float64, error) {
	// Build history database path
	// Symbol format: "AETF.GR" -> filename: "AETF_GR.db"
	dbFilename := strings.ReplaceAll(symbol, ".", "_") + ".db"
	historyDBPath := filepath.Join(c.dataDir, "history", dbFilename)

	// Open security-specific history database
	historyDB, err := sql.Open("sqlite3", historyDBPath)
	if err != nil {
		c.log.Warn().
			Err(err).
			Str("symbol", symbol).
			Str("path", historyDBPath).
			Msg("Failed to open history database")
		return 0, nil // Return 0 instead of error to avoid blocking display
	}
	defer historyDB.Close()

	// Create security performance service
	securityPerf := NewSecurityPerformanceService(historyDB, c.log)

	// Calculate trailing 12mo CAGR
	cagr, err := securityPerf.CalculateTrailing12MoCAGR(symbol)
	if err != nil {
		c.log.Warn().
			Err(err).
			Str("symbol", symbol).
			Msg("Failed to calculate security performance")
		return 0, nil // Return 0 instead of error to avoid blocking display
	}

	if cagr == nil {
		c.log.Debug().
			Str("symbol", symbol).
			Msg("No CAGR data available for security")
		return 0, nil
	}

	c.log.Debug().
		Str("symbol", symbol).
		Float64("cagr", *cagr).
		Msg("Calculated security performance")

	return *cagr, nil
}

// calculateBackgroundPercentage calculates % of portfolio in positions 6+
func (c *PortfolioDisplayCalculator) calculateBackgroundPercentage(topHoldings []struct {
	Symbol      string
	MarketValue float64
}, totalValue float64) float64 {
	topValue := 0.0
	for _, h := range topHoldings {
		topValue += h.MarketValue
	}
	return (totalValue - topValue) / totalValue
}

// calculateBackgroundPerformance calculates aggregate performance of positions 6+
func (c *PortfolioDisplayCalculator) calculateBackgroundPerformance(topHoldings []struct {
	Symbol      string
	MarketValue float64
}, target float64) float64 {
	// Get symbols of top holdings to exclude them
	topSymbols := make(map[string]bool)
	for _, h := range topHoldings {
		topSymbols[h.Symbol] = true
	}

	// Query all positions excluding top holdings
	rows, err := c.portfolioDB.Query(`
		SELECT symbol, market_value_eur
		FROM positions
		WHERE quantity > 0
		ORDER BY market_value_eur DESC
	`)
	if err != nil {
		c.log.Warn().Err(err).Msg("Failed to query background positions")
		return 0
	}
	defer rows.Close()

	var totalValue float64
	var weightedPerformance float64

	for rows.Next() {
		var symbol string
		var marketValue float64
		if err := rows.Scan(&symbol, &marketValue); err != nil {
			c.log.Warn().Err(err).Msg("Failed to scan background position")
			continue
		}

		// Skip top holdings
		if topSymbols[symbol] {
			continue
		}

		// Get security performance
		cagr, err := c.getSecurityPerformance(symbol, target)
		if err != nil {
			c.log.Warn().
				Err(err).
				Str("symbol", symbol).
				Msg("Failed to get background position performance")
			continue
		}

		// Add to weighted sum
		weightedPerformance += cagr * marketValue
		totalValue += marketValue
	}

	if totalValue == 0 {
		c.log.Debug().Msg("No background positions found")
		return 0
	}

	// Calculate weighted average
	avgPerformance := weightedPerformance / totalValue

	c.log.Debug().
		Float64("avg_performance", avgPerformance).
		Float64("total_value", totalValue).
		Msg("Calculated background performance")

	return avgPerformance
}

// adjustBackgroundBrightness reduces brightness for background cluster
func (c *PortfolioDisplayCalculator) adjustBackgroundBrightness(brightness int) int {
	minBg := int(c.getSettingFloat("display_background_brightness_min", 80))
	maxBg := int(c.getSettingFloat("display_background_brightness_max", 120))

	// Map from full range to background range
	mapped := c.mapRange(float64(brightness), 100, 220, float64(minBg), float64(maxBg))
	return clamp(mapped, minBg, maxBg)
}

// mapRange maps a value from one range to another
func (c *PortfolioDisplayCalculator) mapRange(value, inMin, inMax, outMin, outMax float64) int {
	if inMax == inMin {
		return int(outMin)
	}
	ratio := (value - inMin) / (inMax - inMin)
	ratio = math.Max(0, math.Min(1, ratio)) // Clamp to 0-1
	return int(outMin + ratio*(outMax-outMin))
}

// getSettingFloat retrieves a float setting with fallback to default
func (c *PortfolioDisplayCalculator) getSettingFloat(key string, defaultVal float64) float64 {
	var value float64
	err := c.universeDB.QueryRow("SELECT value FROM settings WHERE key = ?", key).Scan(&value)
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
