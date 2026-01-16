// Package symbolic_regression provides symbolic regression for formula discovery.
package symbolic_regression

import (
	"database/sql"
	"fmt"
	"math"
	"time"

	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// SecurityProvider provides read-only access to securities for ISIN/symbol conversions and listing.
type SecurityProvider interface {
	GetISINBySymbol(symbol string) (string, error)
	GetSymbolByISIN(isin string) (string, error)
	GetAll() ([]SecurityInfo, error)
}

// DataPrep extracts historical training examples for symbolic regression
type DataPrep struct {
	historyDB        universe.HistoryDBInterface // history.db - filtered daily prices
	portfolioDB      *sql.DB                     // portfolio.db - scores, calculated_metrics
	configDB         *sql.DB                     // config.db - market_regime_history
	securityProvider SecurityProvider            // For ISIN/symbol lookups
	log              zerolog.Logger
}

// NewDataPrep creates a new data preparation service
func NewDataPrep(
	historyDB universe.HistoryDBInterface,
	portfolioDB *sql.DB,
	configDB *sql.DB,
	securityProvider SecurityProvider,
	log zerolog.Logger,
) *DataPrep {
	var logger zerolog.Logger
	if log.GetLevel() == zerolog.Disabled {
		logger = zerolog.Nop()
	} else {
		logger = log.With().Str("component", "symbolic_regression_data_prep").Logger()
	}

	return &DataPrep{
		historyDB:        historyDB,
		portfolioDB:      portfolioDB,
		configDB:         configDB,
		securityProvider: securityProvider,
		log:              logger,
	}
}

// ExtractTrainingExamples extracts training examples for a given training date
// forwardMonths: number of months forward for target return (6 or 12)
func (dp *DataPrep) ExtractTrainingExamples(
	trainingDate time.Time,
	forwardMonths int,
) ([]TrainingExample, error) {
	// Calculate target date
	targetDate := trainingDate.AddDate(0, forwardMonths, 0)

	// Get all active securities
	securities, err := dp.getAllSecurities()
	if err != nil {
		return nil, fmt.Errorf("failed to get securities: %w", err)
	}

	var examples []TrainingExample

	for _, sec := range securities {
		// Check if security has sufficient history (use ISIN for daily_prices table)
		hasData, err := dp.hasSufficientHistory(sec.ISIN, trainingDate, targetDate)
		if err != nil {
			dp.log.Debug().
				Str("isin", sec.ISIN).
				Str("symbol", sec.Symbol).
				Err(err).
				Msg("Failed to check history, skipping")
			continue
		}

		if !hasData {
			dp.log.Debug().
				Str("isin", sec.ISIN).
				Str("symbol", sec.Symbol).
				Str("training_date", trainingDate.Format("2006-01-02")).
				Msg("Insufficient history, skipping")
			continue
		}

		// Extract inputs at training date
		inputs, err := dp.extractInputs(sec.ISIN, trainingDate)
		if err != nil {
			dp.log.Debug().
				Str("isin", sec.ISIN).
				Err(err).
				Msg("Failed to extract inputs, skipping")
			continue
		}

		// Calculate target return (use ISIN for daily_prices table)
		targetReturn, err := dp.calculateTargetReturn(sec.ISIN, trainingDate.Format("2006-01-02"), targetDate.Format("2006-01-02"))
		if err != nil {
			dp.log.Debug().
				Str("isin", sec.ISIN).
				Err(err).
				Msg("Failed to calculate target return, skipping")
			continue
		}

		// Filter outliers (extreme returns likely data errors)
		if targetReturn > 1.0 || targetReturn < -0.5 {
			dp.log.Debug().
				Str("isin", sec.ISIN).
				Float64("target_return", targetReturn).
				Msg("Filtered outlier return, skipping")
			continue
		}

		example := TrainingExample{
			SecurityISIN:   sec.ISIN,
			SecuritySymbol: sec.Symbol,
			ProductType:    sec.ProductType,
			Date:           trainingDate.Format("2006-01-02"),
			TargetDate:     targetDate.Format("2006-01-02"),
			Inputs:         *inputs,
			TargetReturn:   targetReturn,
		}

		examples = append(examples, example)
	}

	dp.log.Info().
		Str("training_date", trainingDate.Format("2006-01-02")).
		Int("forward_months", forwardMonths).
		Int("examples_extracted", len(examples)).
		Msg("Extracted training examples")

	return examples, nil
}

// SecurityInfo represents basic security information
type SecurityInfo struct {
	ISIN        string
	Symbol      string
	ProductType string
}

// getAllSecurities retrieves all securities from security provider
func (dp *DataPrep) getAllSecurities() ([]SecurityInfo, error) {
	return dp.securityProvider.GetAll()
}

// hasSufficientHistory checks if security has data at both training and target dates
// Parameter isin is the ISIN identifier
// Uses closest available date within ±5 days to handle weekends/holidays
func (dp *DataPrep) hasSufficientHistory(isin string, trainingDate, targetDate time.Time) (bool, error) {
	// Get all filtered prices for this security (uses cache)
	prices, err := dp.historyDB.GetDailyPrices(isin, 0) // 0 = no limit
	if err != nil {
		return false, fmt.Errorf("failed to get prices: %w", err)
	}

	if len(prices) == 0 {
		return false, nil
	}

	// Check if we have price data near training date (±5 days)
	trainingPrice := dp.findPriceNearDate(prices, trainingDate)
	if trainingPrice == nil {
		return false, nil
	}

	// Check if we have price data near target date (±5 days)
	targetPrice := dp.findPriceNearDate(prices, targetDate)
	if targetPrice == nil {
		return false, nil
	}

	return true, nil
}

// findPriceNearDate finds the closest price within ±5 days of the given date
// Returns nil if no price found within the window
func (dp *DataPrep) findPriceNearDate(prices []universe.DailyPrice, targetDate time.Time) *universe.DailyPrice {
	targetStr := targetDate.Format("2006-01-02")

	var bestMatch *universe.DailyPrice
	var minDiff int64 = 6 * 24 * 60 * 60 // Start with > 5 days (in seconds)

	for i := range prices {
		priceDate, err := time.Parse("2006-01-02", prices[i].Date)
		if err != nil {
			continue
		}

		diff := targetDate.Unix() - priceDate.Unix()
		if diff < 0 {
			diff = -diff
		}

		// Within ±5 days and closer than previous best
		if diff <= 5*24*60*60 && diff < minDiff {
			minDiff = diff
			bestMatch = &prices[i]

			// Exact match - no need to continue
			if prices[i].Date == targetStr {
				break
			}
		}
	}

	return bestMatch
}

// extractInputs extracts all input features for a security at a given date
func (dp *DataPrep) extractInputs(isin string, date time.Time) (*TrainingInputs, error) {
	inputs := &TrainingInputs{
		AdditionalMetrics: make(map[string]float64),
	}

	// Extract scores (use most recent score before or at date)
	// Note: stability_score column now stores stability score (internal price-based calculation)
	// analyst_score is no longer used (external analyst data removed)
	var totalScore, longTerm, stability, dividends, opportunity, shortTerm, technicals, diversification sql.NullFloat64
	err := dp.portfolioDB.QueryRow(`
		SELECT
			total_score,
			cagr_score,
			stability_score,
			dividend_bonus,
			opportunity_score,
			drawdown_score,
			technical_score,
			allocation_fit_score
		FROM scores
		WHERE isin = ? AND last_updated <= ?
		ORDER BY last_updated DESC
		LIMIT 1
	`, isin, date.Format("2006-01-02")).Scan(
		&totalScore, &longTerm, &stability, &dividends, &opportunity,
		&shortTerm, &technicals, &diversification,
	)
	if err != nil && err != sql.ErrNoRows {
		return nil, fmt.Errorf("failed to query scores: %w", err)
	}

	if totalScore.Valid {
		inputs.TotalScore = totalScore.Float64
	}
	if longTerm.Valid {
		inputs.LongTermScore = longTerm.Float64
	}
	if stability.Valid {
		inputs.StabilityScore = stability.Float64
	}
	if dividends.Valid {
		inputs.DividendsScore = dividends.Float64
	}
	if opportunity.Valid {
		inputs.OpportunityScore = opportunity.Float64
	}
	if shortTerm.Valid {
		inputs.ShortTermScore = shortTerm.Float64
	}
	if technicals.Valid {
		inputs.TechnicalsScore = technicals.Float64
	}
	if diversification.Valid {
		inputs.DiversificationScore = diversification.Float64
	}

	// Extract metrics from calculated_metrics (need symbol, not isin)
	// Get symbol from security provider
	symbol, err := dp.securityProvider.GetSymbolByISIN(isin)
	if err != nil {
		dp.log.Debug().Str("isin", isin).Err(err).Msg("Failed to get symbol, skipping metrics")
		symbol = "" // Will cause metrics extraction to fail gracefully
	}

	metrics, err := dp.extractMetrics(symbol, date)
	if err != nil {
		dp.log.Debug().Err(err).Msg("Failed to extract metrics, using defaults")
	} else {
		if cagr, ok := metrics["CAGR_5Y"]; ok {
			inputs.CAGR = cagr
		} else if cagr, ok := metrics["CAGR_10Y"]; ok {
			inputs.CAGR = cagr
		}
		if div, ok := metrics["DIVIDEND_YIELD"]; ok {
			inputs.DividendYield = div
		}
		if vol, ok := metrics["VOLATILITY"]; ok {
			inputs.Volatility = vol
		}
		if sharpe, ok := metrics["SHARPE_RATIO"]; ok {
			inputs.SharpeRatio = &sharpe
		}
		if sortino, ok := metrics["SORTINO_RATIO"]; ok {
			inputs.SortinoRatio = &sortino
		}
		if rsi, ok := metrics["RSI_14"]; ok {
			inputs.RSI = &rsi
		}
		if dd, ok := metrics["MAX_DRAWDOWN"]; ok {
			inputs.MaxDrawdown = &dd
		}

		// Store all additional metrics
		inputs.AdditionalMetrics = metrics
	}

	// Extract regime score (use most recent before or at date)
	var regimeScore sql.NullFloat64
	err = dp.configDB.QueryRow(`
		SELECT smoothed_score
		FROM market_regime_history
		WHERE recorded_at <= ?
		ORDER BY recorded_at DESC
		LIMIT 1
	`, date.Format("2006-01-02")).Scan(&regimeScore)
	if err != nil && err != sql.ErrNoRows {
		return nil, fmt.Errorf("failed to query regime score: %w", err)
	}
	if regimeScore.Valid {
		inputs.RegimeScore = regimeScore.Float64
	} else {
		// Default to neutral if no regime data
		inputs.RegimeScore = 0.0
	}

	// Use defaults for missing values
	if inputs.TotalScore == 0 && !totalScore.Valid {
		inputs.TotalScore = 0.5 // Neutral default
	}
	if inputs.LongTermScore == 0 && !longTerm.Valid {
		inputs.LongTermScore = 0.5
	}
	if inputs.StabilityScore == 0 && !stability.Valid {
		inputs.StabilityScore = 0.5
	}

	return inputs, nil
}

// extractMetrics extracts calculated metrics for a security
// Note: calculated_metrics table doesn't exist, so we extract from scores table instead
// Uses positions table to map symbol -> ISIN, then queries scores table
func (dp *DataPrep) extractMetrics(symbol string, date time.Time) (map[string]float64, error) {
	if symbol == "" {
		return make(map[string]float64), nil // Return empty map if no symbol
	}

	// Lookup ISIN from symbol via security provider
	isin, err := dp.securityProvider.GetISINBySymbol(symbol)
	if err != nil {
		// Symbol not found or no ISIN - return empty map gracefully
		dp.log.Debug().Str("symbol", symbol).Err(err).Msg("Failed to lookup ISIN for symbol")
		return make(map[string]float64), nil
	}
	if isin == "" {
		return make(map[string]float64), nil
	}

	// Query metrics from scores table directly by ISIN (PRIMARY KEY - fastest)
	query := `
		SELECT
			cagr_score,
			dividend_bonus,
			volatility,
			rsi,
			drawdown_score,
			sharpe_score
		FROM scores
		WHERE isin = ? AND last_updated <= ?
		ORDER BY last_updated DESC
		LIMIT 1
	`

	rows, err := dp.portfolioDB.Query(query, isin, date.Format("2006-01-02"))
	if err != nil {
		// Table might not exist or no data - return empty map gracefully
		dp.log.Debug().Str("symbol", symbol).Err(err).Msg("Failed to query metrics from scores table")
		return make(map[string]float64), nil
	}
	defer rows.Close()

	metrics := make(map[string]float64)
	if rows.Next() {
		var cagrScore, dividendBonus, volatility, rsi, drawdownScore, sharpeScore sql.NullFloat64
		if err := rows.Scan(&cagrScore, &dividendBonus, &volatility, &rsi, &drawdownScore, &sharpeScore); err != nil {
			dp.log.Debug().Str("symbol", symbol).Err(err).Msg("Failed to scan metrics")
			return metrics, nil
		}

		// Convert normalized scores to approximate raw values
		if cagrScore.Valid && cagrScore.Float64 > 0 {
			// Convert cagr_score (0-1) to approximate CAGR percentage
			cagrValue := convertCAGRScoreToCAGR(cagrScore.Float64)
			if cagrValue > 0 {
				metrics["CAGR_5Y"] = cagrValue  // Use as 5Y approximation
				metrics["CAGR_10Y"] = cagrValue // Use as 10Y approximation
			}
		}
		if dividendBonus.Valid {
			metrics["DIVIDEND_YIELD"] = dividendBonus.Float64
		}
		if volatility.Valid {
			metrics["VOLATILITY"] = volatility.Float64
		}
		if rsi.Valid {
			metrics["RSI_14"] = rsi.Float64
		}
		if drawdownScore.Valid {
			// drawdown_score is normalized, approximate as percentage
			metrics["MAX_DRAWDOWN"] = drawdownScore.Float64 * 0.5 // Rough approximation
		}
		if sharpeScore.Valid {
			// sharpe_score is normalized, approximate as ratio
			metrics["SHARPE_RATIO"] = sharpeScore.Float64 * 2.0 // Rough approximation
		}
	}

	return metrics, nil
}

// convertCAGRScoreToCAGR converts normalized cagr_score (0-1) back to approximate CAGR percentage.
func convertCAGRScoreToCAGR(cagrScore float64) float64 {
	if cagrScore <= 0 {
		return 0.0
	}

	var cagrValue float64
	if cagrScore >= 0.8 {
		// Above target: 0.8 (11%) to 1.0 (20%)
		cagrValue = 0.11 + (cagrScore-0.8)*(0.20-0.11)/(1.0-0.8)
	} else if cagrScore >= 0.15 {
		// Below target: 0.15 (0%) to 0.8 (11%)
		cagrValue = 0.0 + (cagrScore-0.15)*(0.11-0.0)/(0.8-0.15)
	} else {
		// At or below floor
		cagrValue = 0.0
	}

	return cagrValue
}

// calculateTargetReturn calculates the actual return from startDate to endDate
// Parameter isin is the ISIN identifier
// startDate and endDate are in YYYY-MM-DD format
// Uses closest available date within ±5 days to handle weekends/holidays
// Uses filtered prices via HistoryDBInterface for clean ML training data
func (dp *DataPrep) calculateTargetReturn(isin, startDate, endDate string) (float64, error) {
	// Parse dates
	startTime, err := time.Parse("2006-01-02", startDate)
	if err != nil {
		return 0, fmt.Errorf("invalid start_date format (expected YYYY-MM-DD): %w", err)
	}

	endTime, err := time.Parse("2006-01-02", endDate)
	if err != nil {
		return 0, fmt.Errorf("invalid end_date format (expected YYYY-MM-DD): %w", err)
	}

	// Get all filtered prices for this security (uses cache)
	prices, err := dp.historyDB.GetDailyPrices(isin, 0) // 0 = no limit
	if err != nil {
		return 0, fmt.Errorf("failed to get prices: %w", err)
	}

	if len(prices) == 0 {
		return 0, fmt.Errorf("no price data for %s", isin)
	}

	// Find price at start date (±5 days)
	startPriceData := dp.findPriceNearDate(prices, startTime)
	if startPriceData == nil {
		return 0, fmt.Errorf("no price found near start date %s for %s", startDate, isin)
	}

	// Find price at end date (±5 days)
	endPriceData := dp.findPriceNearDate(prices, endTime)
	if endPriceData == nil {
		return 0, fmt.Errorf("no price found near end date %s for %s", endDate, isin)
	}

	// Use adjusted close for return calculation (accounts for dividends/splits)
	// Fall back to close if adjusted_close not available
	startPrice := startPriceData.Close
	if startPriceData.AdjustedClose != nil && *startPriceData.AdjustedClose > 0 {
		startPrice = *startPriceData.AdjustedClose
	}

	endPrice := endPriceData.Close
	if endPriceData.AdjustedClose != nil && *endPriceData.AdjustedClose > 0 {
		endPrice = *endPriceData.AdjustedClose
	}

	if startPrice <= 0 {
		return 0, fmt.Errorf("invalid start price for %s at %s", isin, startDate)
	}
	if endPrice <= 0 {
		return 0, fmt.Errorf("invalid end price for %s at %s", isin, endDate)
	}

	// Calculate return: (end - start) / start
	returnVal := (endPrice - startPrice) / startPrice

	return returnVal, nil
}

// ExtractAllTrainingExamples extracts training examples for multiple dates
// Returns examples grouped by date
func (dp *DataPrep) ExtractAllTrainingExamples(
	startDate time.Time,
	endDate time.Time,
	intervalMonths int, // Extract every N months
	forwardMonths int, // Target return horizon
) (map[string][]TrainingExample, error) {
	result := make(map[string][]TrainingExample)

	currentDate := startDate
	for currentDate.Before(endDate) || currentDate.Equal(endDate) {
		examples, err := dp.ExtractTrainingExamples(currentDate, forwardMonths)
		if err != nil {
			return nil, fmt.Errorf("failed to extract examples for %s: %w", currentDate.Format("2006-01-02"), err)
		}

		if len(examples) > 0 {
			result[currentDate.Format("2006-01-02")] = examples
		}

		// Move to next interval
		currentDate = currentDate.AddDate(0, intervalMonths, 0)
	}

	return result, nil
}

// FilterBySecurityType filters examples by security type
func FilterBySecurityType(examples []TrainingExample, securityType SecurityType) []TrainingExample {
	var filtered []TrainingExample
	for _, ex := range examples {
		// Map product types to security types
		var secType SecurityType
		if ex.ProductType == "EQUITY" {
			secType = SecurityTypeStock
		} else if ex.ProductType == "ETF" || ex.ProductType == "MUTUALFUND" {
			secType = SecurityTypeETF
		} else {
			continue // Skip unknown types
		}

		if secType == securityType {
			filtered = append(filtered, ex)
		}
	}
	return filtered
}

// ValidateTrainingExamples validates training examples and filters invalid ones
func ValidateTrainingExamples(examples []TrainingExample) []TrainingExample {
	var valid []TrainingExample
	for _, ex := range examples {
		// Check for NaN or Inf values
		if math.IsNaN(ex.TargetReturn) || math.IsInf(ex.TargetReturn, 0) {
			continue
		}
		if math.IsNaN(ex.Inputs.TotalScore) || math.IsInf(ex.Inputs.TotalScore, 0) {
			continue
		}
		if math.IsNaN(ex.Inputs.RegimeScore) || math.IsInf(ex.Inputs.RegimeScore, 0) {
			continue
		}

		// Check regime score is in valid range
		if ex.Inputs.RegimeScore < -1.0 || ex.Inputs.RegimeScore > 1.0 {
			continue
		}

		valid = append(valid, ex)
	}
	return valid
}
