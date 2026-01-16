package optimization

import (
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strings"
	"time"

	"gonum.org/v1/gonum/mat"
	"gonum.org/v1/gonum/stat"

	"github.com/aristath/sentinel/internal/market_regime"
	"github.com/aristath/sentinel/internal/modules/calculations"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// Constants for risk model configuration
const (
	DefaultLookbackDays      = 252  // 1 year of trading days
	HighCorrelationThreshold = 0.80 // 80% correlation is considered "high"
)

// cachedCovResult holds covariance matrix results for cache serialization
type cachedCovResult struct {
	Cov          [][]float64          `json:"cov"`
	Returns      map[string][]float64 `json:"returns"`
	Correlations []CorrelationPair    `json:"correlations"`
}

// hashISINs creates a deterministic hash from a list of ISINs for cache keys.
// ISINs are sorted to ensure consistent hashing regardless of input order.
func hashISINs(isins []string) string {
	sorted := make([]string, len(isins))
	copy(sorted, isins)
	sort.Strings(sorted)
	combined := strings.Join(sorted, ",")
	h := sha256.Sum256([]byte(combined))
	return hex.EncodeToString(h[:16]) // Use first 16 bytes (32 hex chars) for efficiency
}

// hashRegimeAwareCovKey creates a deterministic hash for regime-aware covariance caching.
// The key includes:
// - Sorted ISINs (order-independent)
// - Lookback days
// - Regime score (rounded to 0.1 for cache stability)
func hashRegimeAwareCovKey(isins []string, lookbackDays int, regimeScore float64) string {
	// Round regime score to 0.1 precision for cache key stability
	// This prevents cache misses for tiny regime score changes
	roundedRegime := math.Round(regimeScore*10) / 10

	// Sort ISINs for consistent hashing
	sorted := make([]string, len(isins))
	copy(sorted, isins)
	sort.Strings(sorted)

	// Build key data string
	keyData := fmt.Sprintf("%s|%d|%.1f", strings.Join(sorted, ","), lookbackDays, roundedRegime)
	h := sha256.Sum256([]byte(keyData))
	return hex.EncodeToString(h[:16])
}

// RiskModelBuilder builds covariance matrices and risk models for optimization.
type RiskModelBuilder struct {
	historyDBClient  universe.HistoryDBInterface // Filtered and cached price access
	securityProvider SecurityProvider            // For symbol -> ISIN lookup
	configDB         *sql.DB                     // config.db (for market_indices table)
	cache            *calculations.Cache         // calculations.db (optional, for caching results)
	log              zerolog.Logger
}

type RegimeAwareRiskOptions struct {
	RegimeWindowDays int
	HalfLifeDays     float64
	Bandwidth        float64
}

// indexSpec represents a market index for regime calculation
type indexSpec struct {
	Symbol string
	ISIN   string
	Region string
}

// NewRiskModelBuilder creates a new risk model builder.
// configDB is optional (can be nil) - if provided, enables dynamic index lookup for regime-aware calculations.
func NewRiskModelBuilder(historyDBClient universe.HistoryDBInterface, securityProvider SecurityProvider, configDB *sql.DB, log zerolog.Logger) *RiskModelBuilder {
	return &RiskModelBuilder{
		historyDBClient:  historyDBClient,
		securityProvider: securityProvider,
		configDB:         configDB,
		log:              log.With().Str("component", "risk_model").Logger(),
	}
}

// SetCache sets the calculation cache for caching covariance matrices and other results.
// This is optional - if not set, calculations are performed fresh each time.
func (rb *RiskModelBuilder) SetCache(cache *calculations.Cache) {
	rb.cache = cache
}

// BuildCovarianceMatrix builds a covariance matrix from historical prices.
// All parameters and returns use ISIN keys (not Symbol keys).
// Results are cached for 24 hours when a cache is configured via SetCache.
func (rb *RiskModelBuilder) BuildCovarianceMatrix(
	isins []string, // ISIN array ✅ (renamed from symbols)
	lookbackDays int,
) ([][]float64, map[string][]float64, []CorrelationPair, error) {
	if lookbackDays <= 0 {
		lookbackDays = DefaultLookbackDays
	}

	// Generate cache key from sorted ISINs
	isinHash := hashISINs(isins)

	// Check cache first if available
	if rb.cache != nil {
		if data, ok := rb.cache.GetOptimizer("covariance", isinHash); ok {
			var result cachedCovResult
			if err := json.Unmarshal(data, &result); err == nil {
				rb.log.Debug().
					Int("num_isins", len(isins)).
					Str("hash", isinHash[:8]).
					Msg("Using cached covariance matrix")
				return result.Cov, result.Returns, result.Correlations, nil
			}
			// If unmarshal fails, log and recalculate
			rb.log.Warn().Msg("Failed to unmarshal cached covariance matrix, recalculating")
		}
	}

	rb.log.Info().
		Int("num_isins", len(isins)).
		Int("lookback_days", lookbackDays).
		Msg("Building covariance matrix")

	// 1. Fetch price history from database
	priceData, err := rb.fetchPriceHistory(isins, lookbackDays) // Use ISINs ✅
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to fetch price history: %w", err)
	}

	if len(priceData.Dates) < 30 {
		return nil, nil, nil, fmt.Errorf("insufficient price history: only %d days available (need at least 30)", len(priceData.Dates))
	}

	rb.log.Debug().
		Int("num_dates", len(priceData.Dates)).
		Int("num_isins", len(priceData.Data)).
		Msg("Fetched price history")

	// 2. Handle missing data (forward-fill and back-fill)
	filledData := rb.handleMissingData(priceData)

	// 3. Calculate daily returns
	returns := rb.calculateReturns(filledData)

	// 4. Calculate covariance matrix with Ledoit-Wolf shrinkage using native Go implementation
	covMatrix, err := calculateCovarianceLedoitWolf(returns, isins) // Use ISINs ✅
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to calculate covariance: %w", err)
	}

	rb.log.Info().
		Int("matrix_size", len(covMatrix)).
		Msg("Calculated covariance matrix with Ledoit-Wolf shrinkage")

	// 5. Extract high correlations from covariance matrix
	correlations := rb.getCorrelations(covMatrix, isins, HighCorrelationThreshold) // Use ISINs ✅

	rb.log.Info().
		Int("high_correlations", len(correlations)).
		Msg("Identified high correlation pairs")

	// Cache the result if cache is available
	if rb.cache != nil {
		result := cachedCovResult{
			Cov:          covMatrix,
			Returns:      returns,
			Correlations: correlations,
		}
		if data, err := json.Marshal(result); err == nil {
			if err := rb.cache.SetOptimizer("covariance", isinHash, data, calculations.TTLOptimizer); err != nil {
				rb.log.Warn().Err(err).Msg("Failed to cache covariance matrix")
			} else {
				rb.log.Debug().
					Str("hash", isinHash[:8]).
					Msg("Cached covariance matrix")
			}
		}
	}

	return covMatrix, returns, correlations, nil
}

// BuildRegimeAwareCovarianceMatrix builds a covariance matrix from historical prices using
// regime-weighted observations (kernel on regime score + time decay).
//
// The regime score series is derived from a fixed set of market indices in history DB.
// All parameters and returns use ISIN keys (not Symbol keys).
func (rb *RiskModelBuilder) BuildRegimeAwareCovarianceMatrix(
	isins []string, // ISIN array ✅ (renamed from symbols)
	lookbackDays int,
	currentRegimeScore float64,
	opts RegimeAwareRiskOptions,
) ([][]float64, map[string][]float64, []CorrelationPair, error) {
	if lookbackDays <= 0 {
		lookbackDays = DefaultLookbackDays
	}

	regimeWindowDays := opts.RegimeWindowDays
	if regimeWindowDays <= 0 {
		regimeWindowDays = 30
	}
	halfLifeDays := opts.HalfLifeDays
	if halfLifeDays <= 0 {
		halfLifeDays = 63
	}
	bandwidth := opts.Bandwidth
	if bandwidth <= 0 {
		bandwidth = 0.25
	}

	// Generate cache key from inputs
	cacheKey := hashRegimeAwareCovKey(isins, lookbackDays, currentRegimeScore)

	// Check cache first if available
	if rb.cache != nil {
		if data, ok := rb.cache.GetOptimizer("regime_covariance", cacheKey); ok {
			var result cachedCovResult
			if err := json.Unmarshal(data, &result); err == nil {
				rb.log.Debug().
					Int("num_isins", len(isins)).
					Str("hash", cacheKey[:8]).
					Float64("regime_score", currentRegimeScore).
					Msg("Using cached regime-aware covariance matrix")
				return result.Cov, result.Returns, result.Correlations, nil
			}
			// If unmarshal fails, log and recalculate
			rb.log.Warn().Msg("Failed to unmarshal cached regime-aware covariance matrix, recalculating")
		}
	}

	rb.log.Info().
		Int("num_isins", len(isins)).
		Int("lookback_days", lookbackDays).
		Float64("current_regime_score", currentRegimeScore).
		Int("regime_window_days", regimeWindowDays).
		Float64("half_life_days", halfLifeDays).
		Float64("bandwidth", bandwidth).
		Msg("Building regime-aware covariance matrix")

	// 1. Fetch price history for assets.
	assetPriceData, err := rb.fetchPriceHistory(isins, lookbackDays) // Use ISINs ✅
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to fetch price history: %w", err)
	}
	if len(assetPriceData.Dates) < 30 {
		return nil, nil, nil, fmt.Errorf("insufficient price history: only %d days available (need at least 30)", len(assetPriceData.Dates))
	}

	assetFilled := rb.handleMissingData(assetPriceData)
	assetReturns := rb.calculateReturns(assetFilled)

	// 2. Build a regime score series aligned to asset returns observations.
	// Get market indices from database or use known indices as fallback
	indices := rb.getMarketIndices()
	if len(indices) == 0 {
		rb.log.Warn().Msg("No market indices configured, using neutral regime weights")
		// Fall through with empty indices - will use neutral regime score
	}

	// Fetch index price data
	indexISINs := make([]string, 0, len(indices))
	for _, idx := range indices {
		indexISINs = append(indexISINs, idx.ISIN)
	}

	var marketReturns []float64
	numObs := len(assetFilled.Dates) - 1

	if len(indexISINs) > 0 {
		indexPriceData, err := rb.fetchPriceHistory(indexISINs, lookbackDays)
		if err != nil {
			rb.log.Warn().Err(err).Msg("Failed to fetch index price history, using neutral regime")
			marketReturns = make([]float64, numObs)
		} else {
			alignedIndex := rb.alignToDates(indexPriceData, assetFilled.Dates)
			alignedIndexFilled := rb.handleMissingData(alignedIndex)
			indexReturns := rb.calculateReturns(alignedIndexFilled)

			// Composite market returns with equal weighting across indices
			marketReturns = make([]float64, numObs)
			for t := 0; t < numObs; t++ {
				composite := 0.0
				count := 0
				for _, idx := range indices {
					r, ok := indexReturns[idx.ISIN]
					if !ok || len(r) != numObs {
						continue
					}
					composite += r[t]
					count++
				}
				if count > 0 {
					marketReturns[t] = composite / float64(count)
				}
			}
		}
	} else {
		marketReturns = make([]float64, numObs)
	}

	// Regime score series per observation: use rolling window of market returns.
	regimeScores := make([]float64, numObs)
	detector := market_regime.NewMarketRegimeDetector(rb.log)
	for t := 0; t < numObs; t++ {
		start := t - (regimeWindowDays - 1)
		if start < 0 {
			start = 0
		}
		window := marketReturns[start : t+1]
		regimeScores[t] = float64(detector.CalculateRegimeScoreFromReturns(window))
	}

	// 3. Compute observation weights and build weighted covariance.
	obsWeights, err := regimeTimeDecayWeights(regimeScores, currentRegimeScore, halfLifeDays, bandwidth)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to build observation weights: %w", err)
	}

	weightedCov, err := weightedCovariance(assetReturns, isins, obsWeights) // Use ISINs ✅
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to calculate weighted covariance: %w", err)
	}

	// 4. Apply shrinkage for conditioning.
	covMatrix, err := applyLedoitWolfShrinkage(weightedCov)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to apply shrinkage: %w", err)
	}

	// 5. Correlation diagnostics.
	correlations := rb.getCorrelations(covMatrix, isins, HighCorrelationThreshold) // Use ISINs ✅

	rb.log.Info().
		Float64("effective_sample_size", effectiveSampleSize(obsWeights)).
		Int("high_correlations", len(correlations)).
		Msg("Built regime-aware covariance matrix")

	// Cache the result if cache is available
	if rb.cache != nil {
		result := cachedCovResult{
			Cov:          covMatrix,
			Returns:      assetReturns,
			Correlations: correlations,
		}
		if data, err := json.Marshal(result); err == nil {
			if err := rb.cache.SetOptimizer("regime_covariance", cacheKey, data, calculations.TTLRegimeCovariance); err != nil {
				rb.log.Warn().Err(err).Msg("Failed to cache regime-aware covariance matrix")
			} else {
				rb.log.Debug().
					Str("hash", cacheKey[:8]).
					Dur("ttl", calculations.TTLRegimeCovariance).
					Msg("Cached regime-aware covariance matrix")
			}
		}
	}

	return covMatrix, assetReturns, correlations, nil
}

// fetchPriceHistory fetches historical prices from the database using HistoryDB.
// This function expects ISINs as input (daily_prices.isin column stores ISINs).
func (rb *RiskModelBuilder) fetchPriceHistory(isins []string, days int) (TimeSeriesData, error) {
	// Calculate start date
	startTime := time.Now().AddDate(0, 0, -days)
	startDate := time.Date(startTime.Year(), startTime.Month(), startTime.Day(), 0, 0, 0, 0, time.UTC).Format("2006-01-02")

	rb.log.Debug().
		Str("start_date", startDate).
		Int("num_isins", len(isins)).
		Msg("Fetching price history from HistoryDB")

	if len(isins) == 0 {
		return TimeSeriesData{}, fmt.Errorf("no ISINs provided")
	}

	// Build time series data structure
	// Map ISIN -> date -> price
	pricesByISIN := make(map[string]map[string]float64)
	dateSet := make(map[string]bool)

	// Fetch prices for each ISIN using HistoryDB (filtered and cached)
	for _, isin := range isins {
		dailyPrices, err := rb.historyDBClient.GetDailyPrices(isin, 0) // 0 = no limit
		if err != nil {
			rb.log.Warn().Err(err).Str("isin", isin).Msg("Failed to get prices for ISIN")
			continue
		}

		pricesByISIN[isin] = make(map[string]float64)
		for _, p := range dailyPrices {
			// Only include prices within the lookback window
			if p.Date >= startDate {
				pricesByISIN[isin][p.Date] = p.Close
				dateSet[p.Date] = true
			}
		}
	}

	// Convert dateSet to sorted slice
	dates := make([]string, 0, len(dateSet))
	for date := range dateSet {
		dates = append(dates, date)
	}

	// Sort dates in ascending order
	sort.Strings(dates)

	// Build final data structure keyed by ISIN
	data := make(map[string][]float64)
	for _, isin := range isins {
		prices := make([]float64, len(dates))
		for i, date := range dates {
			if price, ok := pricesByISIN[isin][date]; ok {
				prices[i] = price
			} else {
				// Mark missing data as NaN
				prices[i] = math.NaN()
			}
		}
		data[isin] = prices
	}

	rb.log.Debug().
		Int("num_dates", len(dates)).
		Int("isins_with_data", len(data)).
		Msg("Built price time series")

	return TimeSeriesData{
		Dates: dates,
		Data:  data,
	}, nil
}

func (rb *RiskModelBuilder) alignToDates(data TimeSeriesData, dates []string) TimeSeriesData {
	aligned := TimeSeriesData{
		Dates: dates,
		Data:  make(map[string][]float64),
	}

	// Build date -> index mapping for the source series.
	dateIndex := make(map[string]int, len(data.Dates))
	for i, d := range data.Dates {
		dateIndex[d] = i
	}

	for symbol, prices := range data.Data {
		out := make([]float64, len(dates))
		for i, d := range dates {
			if j, ok := dateIndex[d]; ok && j < len(prices) {
				out[i] = prices[j]
			} else {
				out[i] = math.NaN()
			}
		}
		aligned.Data[symbol] = out
	}

	return aligned
}

// handleMissingData fills missing data using forward-fill and back-fill.
func (rb *RiskModelBuilder) handleMissingData(data TimeSeriesData) TimeSeriesData {
	filledData := TimeSeriesData{
		Dates: data.Dates,
		Data:  make(map[string][]float64),
	}

	missingCount := 0
	filledCount := 0

	for symbol, prices := range data.Data {
		filled := make([]float64, len(prices))
		copy(filled, prices)

		// First pass: forward-fill (use previous valid value)
		var lastValid float64
		hasLastValid := false

		for i := 0; i < len(filled); i++ {
			if math.IsNaN(filled[i]) {
				missingCount++
				if hasLastValid {
					filled[i] = lastValid
					filledCount++
				}
			} else {
				lastValid = filled[i]
				hasLastValid = true
			}
		}

		// Second pass: back-fill (for leading NaNs)
		var nextValid float64
		hasNextValid := false

		for i := len(filled) - 1; i >= 0; i-- {
			if math.IsNaN(filled[i]) {
				if hasNextValid {
					filled[i] = nextValid
					filledCount++
				}
			} else {
				nextValid = filled[i]
				hasNextValid = true
			}
		}

		filledData.Data[symbol] = filled
	}

	if missingCount > 0 {
		rb.log.Warn().
			Int("missing_data_points", missingCount).
			Int("filled_data_points", filledCount).
			Int("still_missing", missingCount-filledCount).
			Msg("Filled missing price data")
	}

	return filledData
}

// calculateReturns calculates daily returns from prices.
func (rb *RiskModelBuilder) calculateReturns(data TimeSeriesData) map[string][]float64 {
	returns := make(map[string][]float64)

	for symbol, prices := range data.Data {
		if len(prices) < 2 {
			returns[symbol] = []float64{}
			continue
		}

		dailyReturns := make([]float64, len(prices)-1)
		for i := 1; i < len(prices); i++ {
			if prices[i-1] > 0 && !math.IsNaN(prices[i]) && !math.IsNaN(prices[i-1]) {
				dailyReturns[i-1] = (prices[i] - prices[i-1]) / prices[i-1]
			} else {
				dailyReturns[i-1] = 0.0
			}
		}
		returns[symbol] = dailyReturns
	}

	return returns
}

// getCorrelations extracts high correlation pairs from covariance matrix.
// All parameters use ISIN keys (not Symbol keys).
func (rb *RiskModelBuilder) getCorrelations(
	covMatrix [][]float64,
	isins []string, // ISIN array ✅ (renamed from symbols)
	threshold float64,
) []CorrelationPair {
	if len(covMatrix) == 0 || len(isins) == 0 {
		return []CorrelationPair{}
	}

	// Calculate correlation matrix from covariance matrix
	// correlation(i,j) = covariance(i,j) / sqrt(variance(i) * variance(j))

	// Extract variances (diagonal elements)
	variances := make([]float64, len(covMatrix))
	for i := 0; i < len(covMatrix); i++ {
		variances[i] = covMatrix[i][i]
	}

	// Find high correlations
	correlations := make([]CorrelationPair, 0)

	for i := 0; i < len(covMatrix); i++ {
		for j := i + 1; j < len(covMatrix); j++ {
			if variances[i] > 0 && variances[j] > 0 {
				correlation := covMatrix[i][j] / math.Sqrt(variances[i]*variances[j])

				// Check if correlation exceeds threshold (absolute value)
				if math.Abs(correlation) >= threshold {
					correlations = append(correlations, CorrelationPair{
						ISIN1:       isins[i],
						ISIN2:       isins[j],
						Correlation: correlation,
					})

					rb.log.Debug().
						Str("isin1", isins[i]).
						Str("isin2", isins[j]).
						Float64("correlation", correlation).
						Msg("High correlation detected")
				}
			}
		}
	}

	return correlations
}

// BuildCorrelationMap converts a slice of CorrelationPair to a map for efficient lookups.
// The map uses keys in "ISIN1:ISIN2" format and stores both orderings for symmetric access.
func BuildCorrelationMap(pairs []CorrelationPair) map[string]float64 {
	correlationMap := make(map[string]float64, len(pairs)*2)

	for _, pair := range pairs {
		// Store both orderings for symmetric lookup
		key1 := pair.ISIN1 + ":" + pair.ISIN2
		key2 := pair.ISIN2 + ":" + pair.ISIN1

		correlationMap[key1] = pair.Correlation
		correlationMap[key2] = pair.Correlation
	}

	return correlationMap
}

// calculateSampleCovariance calculates the sample covariance matrix from returns.
// Returns a symmetric matrix where element (i,j) is the covariance between isins[i] and isins[j].
// All parameters use ISIN keys (not Symbol keys).
func calculateSampleCovariance(returns map[string][]float64, isins []string) ([][]float64, error) {
	if len(isins) == 0 {
		return nil, fmt.Errorf("no ISINs provided")
	}

	// Find the length of returns (should be same for all ISINs)
	var returnLength int
	for _, isin := range isins {
		ret, ok := returns[isin]
		if !ok {
			return nil, fmt.Errorf("missing returns for ISIN %s", isin)
		}
		if returnLength == 0 {
			returnLength = len(ret)
		}
		if len(ret) != returnLength {
			return nil, fmt.Errorf("inconsistent return lengths: expected %d, got %d for ISIN %s", returnLength, len(ret), isin)
		}
	}

	if returnLength < 2 {
		return nil, fmt.Errorf("insufficient data: need at least 2 observations, got %d", returnLength)
	}

	n := len(isins)
	covMatrix := make([][]float64, n)
	for i := range covMatrix {
		covMatrix[i] = make([]float64, n)
	}

	// Build data matrix: each column is an ISIN's returns
	data := make([][]float64, returnLength)
	for i := 0; i < returnLength; i++ {
		data[i] = make([]float64, n)
		for j, isin := range isins {
			data[i][j] = returns[isin][i]
		}
	}

	// Calculate covariance matrix using gonum/stat
	// For each pair (i,j), calculate covariance
	for i := 0; i < n; i++ {
		for j := i; j < n; j++ {
			// Extract columns
			colI := make([]float64, returnLength)
			colJ := make([]float64, returnLength)
			for k := 0; k < returnLength; k++ {
				colI[k] = data[k][i]
				colJ[k] = data[k][j]
			}

			// Calculate covariance (sample covariance, using N-1 denominator)
			cov := stat.Covariance(colI, colJ, nil)
			covMatrix[i][j] = cov
			if i != j {
				covMatrix[j][i] = cov // Symmetry
			}
		}
	}

	return covMatrix, nil
}

// applyLedoitWolfShrinkage applies Ledoit-Wolf shrinkage to a sample covariance matrix.
// The shrinkage estimator shrinks the sample covariance matrix towards a structured estimator
// (constant correlation model) to improve estimation quality, especially with limited data.
//
// Reference: Ledoit, O., & Wolf, M. (2004). "A well-conditioned estimator for large-dimensional covariance matrices"
func applyLedoitWolfShrinkage(sampleCov [][]float64) ([][]float64, error) {
	n := len(sampleCov)
	if n == 0 {
		return nil, fmt.Errorf("empty covariance matrix")
	}

	// Convert to gonum matrix for easier manipulation
	covMat := mat.NewDense(n, n, nil)
	for i := 0; i < n; i++ {
		for j := 0; j < n; j++ {
			covMat.Set(i, j, sampleCov[i][j])
		}
	}

	// Calculate shrinkage target: constant correlation model
	// Target = (average variance) * I + (average covariance - average variance) * (1/n) * ones
	var avgVar, avgCov float64
	for i := 0; i < n; i++ {
		avgVar += sampleCov[i][i]
		for j := 0; j < n; j++ {
			if i != j {
				avgCov += sampleCov[i][j]
			}
		}
	}
	avgVar /= float64(n)
	avgCov /= float64(n * (n - 1))

	// Build target matrix (constant correlation model)
	target := mat.NewDense(n, n, nil)
	for i := 0; i < n; i++ {
		for j := 0; j < n; j++ {
			if i == j {
				target.Set(i, j, avgVar)
			} else {
				// Constant correlation = avgCov / avgVar (if avgVar > 0)
				if avgVar > 0 {
					target.Set(i, j, avgCov)
				} else {
					target.Set(i, j, 0)
				}
			}
		}
	}

	// Calculate optimal shrinkage intensity
	// This is a simplified version - full Ledoit-Wolf requires more complex calculation
	// For now, use a reasonable shrinkage parameter
	// In practice, the shrinkage intensity should be calculated based on the data
	shrinkage := 0.2 // Default shrinkage (20% towards target)

	// Try to estimate optimal shrinkage if we have enough structure
	if n > 2 && avgVar > 0 {
		// Simplified shrinkage estimator
		// Calculate mean squared difference between sample and target
		var sumSqDiff float64
		for i := 0; i < n; i++ {
			for j := 0; j < n; j++ {
				diff := sampleCov[i][j] - target.At(i, j)
				sumSqDiff += diff * diff
			}
		}
		meanSqDiff := sumSqDiff / float64(n*n)

		// Calculate variance of sample covariance elements
		var sumSqSample float64
		var meanSample float64
		count := 0
		for i := 0; i < n; i++ {
			for j := 0; j < n; j++ {
				val := sampleCov[i][j]
				meanSample += val
				sumSqSample += val * val
				count++
			}
		}
		meanSample /= float64(count)
		varSample := (sumSqSample/float64(count) - meanSample*meanSample)

		if varSample > 0 && meanSqDiff > 0 {
			// Optimal shrinkage intensity (simplified)
			shrinkage = math.Min(0.5, math.Max(0.0, varSample/(varSample+meanSqDiff)))
		}
	}

	// Apply shrinkage: Σ_shrunk = (1-δ) * Σ_sample + δ * Σ_target
	result := mat.NewDense(n, n, nil)
	for i := 0; i < n; i++ {
		for j := 0; j < n; j++ {
			shrunkVal := (1-shrinkage)*sampleCov[i][j] + shrinkage*target.At(i, j)
			result.Set(i, j, shrunkVal)
		}
	}

	// Convert back to [][]float64
	shrunk := make([][]float64, n)
	for i := 0; i < n; i++ {
		shrunk[i] = make([]float64, n)
		for j := 0; j < n; j++ {
			shrunk[i][j] = result.At(i, j)
		}
	}

	return shrunk, nil
}

// calculateCovarianceLedoitWolf calculates the covariance matrix with Ledoit-Wolf shrinkage.
// First calculates sample covariance, then applies shrinkage.
// All parameters use ISIN keys (not Symbol keys).
func calculateCovarianceLedoitWolf(returns map[string][]float64, isins []string) ([][]float64, error) {
	// Calculate sample covariance
	sampleCov, err := calculateSampleCovariance(returns, isins)
	if err != nil {
		return nil, fmt.Errorf("failed to calculate sample covariance: %w", err)
	}

	// Apply Ledoit-Wolf shrinkage
	shrunkCov, err := applyLedoitWolfShrinkage(sampleCov)
	if err != nil {
		return nil, fmt.Errorf("failed to apply Ledoit-Wolf shrinkage: %w", err)
	}

	return shrunkCov, nil
}

// getMarketIndices returns market indices for regime calculation.
// If configDB is available, queries the market_indices table for enabled PRICE indices.
// Otherwise, falls back to known indices from the index discovery module.
func (rb *RiskModelBuilder) getMarketIndices() []indexSpec {
	// Try to get indices from config database first
	if rb.configDB != nil {
		indices, err := rb.getIndicesFromDB()
		if err == nil && len(indices) > 0 {
			rb.log.Debug().Int("count", len(indices)).Msg("Using market indices from database")
			return indices
		}
		if err != nil {
			rb.log.Warn().Err(err).Msg("Failed to get market indices from database, using fallback")
		}
	}

	// Fallback to known indices
	return rb.getFallbackIndices()
}

// getIndicesFromDB queries market_indices table for enabled PRICE indices
// Note: market_indices is in configDB, securities is in universeDB - separate queries required
func (rb *RiskModelBuilder) getIndicesFromDB() ([]indexSpec, error) {
	// Step 1: Get enabled PRICE indices from config DB
	query := `
		SELECT symbol, region
		FROM market_indices
		WHERE enabled = 1 AND index_type = 'PRICE'
	`

	rows, err := rb.configDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query market indices: %w", err)
	}
	defer rows.Close()

	// Collect symbols and regions
	type indexMeta struct {
		Symbol string
		Region string
	}
	var metas []indexMeta
	for rows.Next() {
		var m indexMeta
		if err := rows.Scan(&m.Symbol, &m.Region); err != nil {
			return nil, fmt.Errorf("failed to scan market index: %w", err)
		}
		metas = append(metas, m)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating market indices: %w", err)
	}

	// Step 2: Look up ISINs from universe DB for each index
	var indices []indexSpec
	for _, m := range metas {
		isin := rb.lookupISIN(m.Symbol)
		if isin == "" {
			rb.log.Debug().Str("symbol", m.Symbol).Msg("Index not found in securities table, skipping")
			continue
		}

		indices = append(indices, indexSpec{
			Symbol: m.Symbol,
			ISIN:   isin,
			Region: m.Region,
		})
	}

	return indices, nil
}

// getFallbackIndices returns hardcoded indices for when database is unavailable
// Uses the known indices from market_regime.GetKnownIndices()
func (rb *RiskModelBuilder) getFallbackIndices() []indexSpec {
	// Get known indices from the index discovery module
	knownIndices := market_regime.GetKnownIndices()

	var indices []indexSpec
	for _, ki := range knownIndices {
		// Only include PRICE indices, not VOLATILITY (like VIX)
		if ki.IndexType != market_regime.IndexTypePrice {
			continue
		}

		// Try to look up ISIN from universe database
		isin := rb.lookupISIN(ki.Symbol)
		if isin == "" {
			rb.log.Debug().Str("symbol", ki.Symbol).Msg("Index not found in universe, skipping")
			continue
		}

		indices = append(indices, indexSpec{
			Symbol: ki.Symbol,
			ISIN:   isin,
			Region: ki.Region,
		})
	}

	rb.log.Debug().Int("count", len(indices)).Msg("Using fallback market indices")
	return indices
}

// lookupISIN looks up the ISIN for a symbol via security provider
func (rb *RiskModelBuilder) lookupISIN(symbol string) string {
	if rb.securityProvider == nil {
		return ""
	}

	isin, err := rb.securityProvider.GetISINBySymbol(symbol)
	if err != nil {
		return ""
	}
	return isin
}

func effectiveSampleSize(weights []float64) float64 {
	sumSq := 0.0
	for _, w := range weights {
		sumSq += w * w
	}
	if sumSq <= 0 {
		return 0.0
	}
	return 1.0 / sumSq
}

// regimeTimeDecayWeights returns normalized observation weights (oldest -> newest) using
// an RBF kernel on regime score around currentRegime and an exponential time decay.
func regimeTimeDecayWeights(
	regimeScores []float64,
	currentRegime float64,
	halfLifeDays float64,
	bandwidth float64,
) ([]float64, error) {
	n := len(regimeScores)
	if n == 0 {
		return nil, fmt.Errorf("empty regimeScores")
	}
	if halfLifeDays <= 0 {
		return nil, fmt.Errorf("invalid halfLifeDays: %v", halfLifeDays)
	}
	if bandwidth <= 0 {
		return nil, fmt.Errorf("invalid bandwidth: %v", bandwidth)
	}

	lambda := math.Ln2 / halfLifeDays
	denomKernel := 2.0 * bandwidth * bandwidth

	weights := make([]float64, n)
	sum := 0.0
	for i := 0; i < n; i++ {
		age := float64((n - 1) - i) // 0 for newest
		wTime := math.Exp(-lambda * age)

		d := regimeScores[i] - currentRegime
		wReg := math.Exp(-(d * d) / denomKernel)

		w := wTime * wReg
		weights[i] = w
		sum += w
	}

	if sum <= 0 || math.IsNaN(sum) || math.IsInf(sum, 0) {
		return nil, fmt.Errorf("invalid weight sum: %v", sum)
	}
	for i := range weights {
		weights[i] /= sum
	}
	return weights, nil
}

// weightedCovariance computes a weighted covariance matrix (ISINs order, oldest->newest observations).
// Uses the effective-sample correction: denom = 1 - sum(w^2).
// All parameters use ISIN keys (not Symbol keys).
func weightedCovariance(
	returns map[string][]float64,
	isins []string, // ISIN array ✅ (renamed from symbols)
	weights []float64,
) ([][]float64, error) {
	n := len(isins)
	if n == 0 {
		return nil, fmt.Errorf("no ISINs provided")
	}
	if len(weights) == 0 {
		return nil, fmt.Errorf("no weights provided")
	}

	// Validate lengths and compute means.
	t := len(weights)
	mu := make([]float64, n)
	for i, isin := range isins {
		ri, ok := returns[isin]
		if !ok {
			return nil, fmt.Errorf("missing returns for ISIN %s", isin)
		}
		if len(ri) != t {
			return nil, fmt.Errorf("inconsistent return lengths")
		}
		sum := 0.0
		for k := 0; k < t; k++ {
			sum += weights[k] * ri[k]
		}
		mu[i] = sum
	}

	sumW2 := 0.0
	for _, w := range weights {
		sumW2 += w * w
	}
	denom := 1.0 - sumW2
	if denom <= 0 {
		return nil, fmt.Errorf("invalid effective-sample denominator: %v", denom)
	}

	cov := make([][]float64, n)
	for i := range cov {
		cov[i] = make([]float64, n)
	}

	for i := 0; i < n; i++ {
		ri := returns[isins[i]]
		for j := i; j < n; j++ {
			rj := returns[isins[j]]
			s := 0.0
			for k := 0; k < t; k++ {
				s += weights[k] * (ri[k] - mu[i]) * (rj[k] - mu[j])
			}
			val := s / denom
			cov[i][j] = val
			if i != j {
				cov[j][i] = val
			}
		}
	}

	return cov, nil
}
