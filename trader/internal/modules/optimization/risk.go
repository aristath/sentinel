package optimization

import (
	"database/sql"
	"fmt"
	"math"
	"time"

	"github.com/rs/zerolog"
)

// Constants for risk model configuration
const (
	DefaultLookbackDays      = 252  // 1 year of trading days
	HighCorrelationThreshold = 0.80 // 80% correlation is considered "high"
)

// RiskModelBuilder builds covariance matrices and risk models for optimization.
type RiskModelBuilder struct {
	db            *sql.DB
	pypfoptClient *PyPFOptClient
	log           zerolog.Logger
}

// NewRiskModelBuilder creates a new risk model builder.
func NewRiskModelBuilder(db *sql.DB, pypfoptClient *PyPFOptClient, log zerolog.Logger) *RiskModelBuilder {
	return &RiskModelBuilder{
		db:            db,
		pypfoptClient: pypfoptClient,
		log:           log.With().Str("component", "risk_model").Logger(),
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

	// 3. Call PyPFOpt microservice to calculate covariance matrix
	req := CovarianceRequest{
		Prices: filledData,
	}

	result, err := rb.pypfoptClient.CalculateCovariance(req)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to calculate covariance: %w", err)
	}

	rb.log.Info().
		Int("matrix_size", len(result.CovarianceMatrix)).
		Msg("Calculated covariance matrix")

	// 4. Calculate daily returns for reference
	returns := rb.calculateReturns(filledData)

	// 5. Extract high correlations from covariance matrix
	correlations := rb.getCorrelations(result.CovarianceMatrix, result.Symbols, HighCorrelationThreshold)

	rb.log.Info().
		Int("high_correlations", len(correlations)).
		Msg("Identified high correlation pairs")

	return result.CovarianceMatrix, returns, correlations, nil
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
		FROM price_history
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
