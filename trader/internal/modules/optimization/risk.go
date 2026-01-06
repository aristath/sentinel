package optimization

import (
	"database/sql"
	"fmt"
	"math"
	"time"

	"gonum.org/v1/gonum/mat"
	"gonum.org/v1/gonum/stat"

	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/rs/zerolog"
)

// Constants for risk model configuration
const (
	DefaultLookbackDays      = 252  // 1 year of trading days
	HighCorrelationThreshold = 0.80 // 80% correlation is considered "high"
)

// RiskModelBuilder builds covariance matrices and risk models for optimization.
type RiskModelBuilder struct {
	db  *sql.DB
	log zerolog.Logger
}

type marketIndexSpec struct {
	Symbol string
	Weight float64
}

type RegimeAwareRiskOptions struct {
	RegimeWindowDays int
	HalfLifeDays     float64
	Bandwidth        float64
}

// NewRiskModelBuilder creates a new risk model builder.
func NewRiskModelBuilder(db *sql.DB, log zerolog.Logger) *RiskModelBuilder {
	return &RiskModelBuilder{
		db:  db,
		log: log.With().Str("component", "risk_model").Logger(),
	}
}

// BuildCovarianceMatrix builds a covariance matrix from historical prices.
func (rb *RiskModelBuilder) BuildCovarianceMatrix(
	symbols []string,
	lookbackDays int,
) ([][]float64, map[string][]float64, []CorrelationPair, error) {
	if lookbackDays <= 0 {
		lookbackDays = DefaultLookbackDays
	}

	rb.log.Info().
		Int("num_symbols", len(symbols)).
		Int("lookback_days", lookbackDays).
		Msg("Building covariance matrix")

	// 1. Fetch price history from database
	priceData, err := rb.fetchPriceHistory(symbols, lookbackDays)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to fetch price history: %w", err)
	}

	if len(priceData.Dates) < 30 {
		return nil, nil, nil, fmt.Errorf("insufficient price history: only %d days available (need at least 30)", len(priceData.Dates))
	}

	rb.log.Debug().
		Int("num_dates", len(priceData.Dates)).
		Int("num_symbols", len(priceData.Data)).
		Msg("Fetched price history")

	// 2. Handle missing data (forward-fill and back-fill)
	filledData := rb.handleMissingData(priceData)

	// 3. Calculate daily returns
	returns := rb.calculateReturns(filledData)

	// 4. Calculate covariance matrix with Ledoit-Wolf shrinkage using native Go implementation
	covMatrix, err := calculateCovarianceLedoitWolf(returns, symbols)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to calculate covariance: %w", err)
	}

	rb.log.Info().
		Int("matrix_size", len(covMatrix)).
		Msg("Calculated covariance matrix with Ledoit-Wolf shrinkage")

	// 5. Extract high correlations from covariance matrix
	correlations := rb.getCorrelations(covMatrix, symbols, HighCorrelationThreshold)

	rb.log.Info().
		Int("high_correlations", len(correlations)).
		Msg("Identified high correlation pairs")

	return covMatrix, returns, correlations, nil
}

// BuildRegimeAwareCovarianceMatrix builds a covariance matrix from historical prices using
// regime-weighted observations (kernel on regime score + time decay).
//
// The regime score series is derived from a fixed set of market indices in history DB.
func (rb *RiskModelBuilder) BuildRegimeAwareCovarianceMatrix(
	symbols []string,
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

	rb.log.Info().
		Int("num_symbols", len(symbols)).
		Int("lookback_days", lookbackDays).
		Float64("current_regime_score", currentRegimeScore).
		Int("regime_window_days", regimeWindowDays).
		Float64("half_life_days", halfLifeDays).
		Float64("bandwidth", bandwidth).
		Msg("Building regime-aware covariance matrix")

	// 1. Fetch price history for assets.
	assetPriceData, err := rb.fetchPriceHistory(symbols, lookbackDays)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to fetch price history: %w", err)
	}
	if len(assetPriceData.Dates) < 30 {
		return nil, nil, nil, fmt.Errorf("insufficient price history: only %d days available (need at least 30)", len(assetPriceData.Dates))
	}

	assetFilled := rb.handleMissingData(assetPriceData)
	assetReturns := rb.calculateReturns(assetFilled)

	// 2. Build a regime score series aligned to asset returns observations.
	indices := []marketIndexSpec{
		{Symbol: "SPX.US", Weight: 0.20},
		{Symbol: "STOXX600.EU", Weight: 0.50},
		{Symbol: "MSCIASIA.ASIA", Weight: 0.30},
	}
	indexSymbols := make([]string, 0, len(indices))
	for _, idx := range indices {
		indexSymbols = append(indexSymbols, idx.Symbol)
	}

	indexPriceData, err := rb.fetchPriceHistory(indexSymbols, lookbackDays)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to fetch index price history: %w", err)
	}

	alignedIndex := rb.alignToDates(indexPriceData, assetFilled.Dates)
	alignedIndexFilled := rb.handleMissingData(alignedIndex)
	indexReturns := rb.calculateReturns(alignedIndexFilled)

	// Composite market returns (aligned to asset returns length).
	numObs := len(assetFilled.Dates) - 1
	marketReturns := make([]float64, numObs)
	totalWeight := 0.0
	for _, idx := range indices {
		totalWeight += idx.Weight
	}
	if totalWeight <= 0 {
		return nil, nil, nil, fmt.Errorf("invalid market index weights")
	}

	for t := 0; t < numObs; t++ {
		composite := 0.0
		usedWeight := 0.0
		for _, idx := range indices {
			r, ok := indexReturns[idx.Symbol]
			if !ok || len(r) != numObs {
				continue
			}
			composite += r[t] * idx.Weight
			usedWeight += idx.Weight
		}
		if usedWeight > 0 {
			marketReturns[t] = composite / usedWeight
		} else {
			marketReturns[t] = 0.0
		}
	}

	// Regime score series per observation: use rolling window of market returns.
	regimeScores := make([]float64, numObs)
	detector := portfolio.NewMarketRegimeDetector(rb.log)
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

	weightedCov, err := weightedCovariance(assetReturns, symbols, obsWeights)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to calculate weighted covariance: %w", err)
	}

	// 4. Apply shrinkage for conditioning.
	covMatrix, err := applyLedoitWolfShrinkage(weightedCov)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to apply shrinkage: %w", err)
	}

	// 5. Correlation diagnostics.
	correlations := rb.getCorrelations(covMatrix, symbols, HighCorrelationThreshold)

	rb.log.Info().
		Float64("effective_sample_size", effectiveSampleSize(obsWeights)).
		Int("high_correlations", len(correlations)).
		Msg("Built regime-aware covariance matrix")

	return covMatrix, assetReturns, correlations, nil
}

// fetchPriceHistory fetches historical prices from the database.
func (rb *RiskModelBuilder) fetchPriceHistory(symbols []string, days int) (TimeSeriesData, error) {
	// Calculate start date
	startDate := time.Now().AddDate(0, 0, -days).Format("2006-01-02")

	rb.log.Debug().
		Str("start_date", startDate).
		Int("num_symbols", len(symbols)).
		Msg("Fetching price history from database")

	// Query to get price history for all symbols
	query := `
		SELECT
			symbol,
			date,
			close
		FROM daily_prices
		WHERE symbol IN (` + rb.buildPlaceholders(len(symbols)) + `)
			AND date >= ?
		ORDER BY date ASC
	`

	// Build args: symbols + startDate
	args := make([]interface{}, 0, len(symbols)+1)
	for _, symbol := range symbols {
		args = append(args, symbol)
	}
	args = append(args, startDate)

	rows, err := rb.db.Query(query, args...)
	if err != nil {
		return TimeSeriesData{}, fmt.Errorf("failed to query price history: %w", err)
	}
	defer rows.Close()

	// Build time series data structure
	pricesBySymbol := make(map[string]map[string]float64) // symbol -> date -> price
	dateSet := make(map[string]bool)

	for rows.Next() {
		var symbol, date string
		var price float64

		if err := rows.Scan(&symbol, &date, &price); err != nil {
			return TimeSeriesData{}, fmt.Errorf("failed to scan row: %w", err)
		}

		if pricesBySymbol[symbol] == nil {
			pricesBySymbol[symbol] = make(map[string]float64)
		}
		pricesBySymbol[symbol][date] = price
		dateSet[date] = true
	}

	if err := rows.Err(); err != nil {
		return TimeSeriesData{}, fmt.Errorf("error iterating rows: %w", err)
	}

	// Convert dateSet to sorted slice
	dates := make([]string, 0, len(dateSet))
	for date := range dateSet {
		dates = append(dates, date)
	}

	// Sort dates (they should already be sorted from ORDER BY, but ensure it)
	// Simple bubble sort for date strings in YYYY-MM-DD format
	for i := 0; i < len(dates)-1; i++ {
		for j := i + 1; j < len(dates); j++ {
			if dates[i] > dates[j] {
				dates[i], dates[j] = dates[j], dates[i]
			}
		}
	}

	// Build final data structure
	data := make(map[string][]float64)
	for _, symbol := range symbols {
		prices := make([]float64, len(dates))
		for i, date := range dates {
			if price, ok := pricesBySymbol[symbol][date]; ok {
				prices[i] = price
			} else {
				// Mark missing data as NaN
				prices[i] = math.NaN()
			}
		}
		data[symbol] = prices
	}

	rb.log.Debug().
		Int("num_dates", len(dates)).
		Int("symbols_with_data", len(data)).
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
func (rb *RiskModelBuilder) getCorrelations(
	covMatrix [][]float64,
	symbols []string,
	threshold float64,
) []CorrelationPair {
	if len(covMatrix) == 0 || len(symbols) == 0 {
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
						Symbol1:     symbols[i],
						Symbol2:     symbols[j],
						Correlation: correlation,
					})

					rb.log.Debug().
						Str("symbol1", symbols[i]).
						Str("symbol2", symbols[j]).
						Float64("correlation", correlation).
						Msg("High correlation detected")
				}
			}
		}
	}

	return correlations
}

// BuildCorrelationMap converts a slice of CorrelationPair to a map for efficient lookups.
// The map uses keys in "SYMBOL1:SYMBOL2" format and stores both orderings for symmetric access.
// This format matches the Python implementation and enables O(1) correlation lookups.
func BuildCorrelationMap(pairs []CorrelationPair) map[string]float64 {
	correlationMap := make(map[string]float64, len(pairs)*2)

	for _, pair := range pairs {
		// Store both orderings for symmetric lookup
		key1 := pair.Symbol1 + ":" + pair.Symbol2
		key2 := pair.Symbol2 + ":" + pair.Symbol1

		correlationMap[key1] = pair.Correlation
		correlationMap[key2] = pair.Correlation
	}

	return correlationMap
}

// buildPlaceholders builds SQL placeholders for IN clause.
func (rb *RiskModelBuilder) buildPlaceholders(n int) string {
	if n == 0 {
		return ""
	}

	placeholders := "?"
	for i := 1; i < n; i++ {
		placeholders += ", ?"
	}
	return placeholders
}

// calculateSampleCovariance calculates the sample covariance matrix from returns.
// Returns a symmetric matrix where element (i,j) is the covariance between symbols[i] and symbols[j].
func calculateSampleCovariance(returns map[string][]float64, symbols []string) ([][]float64, error) {
	if len(symbols) == 0 {
		return nil, fmt.Errorf("no symbols provided")
	}

	// Find the length of returns (should be same for all symbols)
	var returnLength int
	for _, symbol := range symbols {
		ret, ok := returns[symbol]
		if !ok {
			return nil, fmt.Errorf("missing returns for symbol %s", symbol)
		}
		if returnLength == 0 {
			returnLength = len(ret)
		}
		if len(ret) != returnLength {
			return nil, fmt.Errorf("inconsistent return lengths: expected %d, got %d for symbol %s", returnLength, len(ret), symbol)
		}
	}

	if returnLength < 2 {
		return nil, fmt.Errorf("insufficient data: need at least 2 observations, got %d", returnLength)
	}

	n := len(symbols)
	covMatrix := make([][]float64, n)
	for i := range covMatrix {
		covMatrix[i] = make([]float64, n)
	}

	// Build data matrix: each column is a symbol's returns
	data := make([][]float64, returnLength)
	for i := 0; i < returnLength; i++ {
		data[i] = make([]float64, n)
		for j, symbol := range symbols {
			data[i][j] = returns[symbol][i]
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
	var shrinkage float64 = 0.2 // Default shrinkage (20% towards target)

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
func calculateCovarianceLedoitWolf(returns map[string][]float64, symbols []string) ([][]float64, error) {
	// Calculate sample covariance
	sampleCov, err := calculateSampleCovariance(returns, symbols)
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

// weightedCovariance computes a weighted covariance matrix (symbols order, oldest->newest observations).
// Uses the effective-sample correction: denom = 1 - sum(w^2).
func weightedCovariance(
	returns map[string][]float64,
	symbols []string,
	weights []float64,
) ([][]float64, error) {
	n := len(symbols)
	if n == 0 {
		return nil, fmt.Errorf("no symbols provided")
	}
	if len(weights) == 0 {
		return nil, fmt.Errorf("no weights provided")
	}

	// Validate lengths and compute means.
	t := len(weights)
	mu := make([]float64, n)
	for i, sym := range symbols {
		ri, ok := returns[sym]
		if !ok {
			return nil, fmt.Errorf("missing returns for symbol %s", sym)
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
		ri := returns[symbols[i]]
		for j := i; j < n; j++ {
			rj := returns[symbols[j]]
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
