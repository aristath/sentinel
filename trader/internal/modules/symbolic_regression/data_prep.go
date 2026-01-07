// Package symbolic_regression provides symbolic regression for formula discovery.
package symbolic_regression

import (
	"database/sql"
	"fmt"
	"math"
	"time"

	"github.com/rs/zerolog"
)

// DataPrep extracts historical training examples for symbolic regression
type DataPrep struct {
	historyDB   *sql.DB // history.db - daily_prices, monthly_prices
	portfolioDB *sql.DB // portfolio.db - scores, calculated_metrics
	configDB    *sql.DB // config.db - market_regime_history
	universeDB  *sql.DB // universe.db - securities
	log         zerolog.Logger
}

// NewDataPrep creates a new data preparation service
func NewDataPrep(
	historyDB *sql.DB,
	portfolioDB *sql.DB,
	configDB *sql.DB,
	universeDB *sql.DB,
	log zerolog.Logger,
) *DataPrep {
	var logger zerolog.Logger
	if log.GetLevel() == zerolog.Disabled {
		logger = zerolog.Nop()
	} else {
		logger = log.With().Str("component", "symbolic_regression_data_prep").Logger()
	}

	return &DataPrep{
		historyDB:   historyDB,
		portfolioDB: portfolioDB,
		configDB:    configDB,
		universeDB:  universeDB,
		log:         logger,
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

// getAllSecurities retrieves all active securities from universe database
func (dp *DataPrep) getAllSecurities() ([]SecurityInfo, error) {
	query := `
		SELECT isin, symbol, product_type
		FROM securities
	`

	rows, err := dp.universeDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query securities: %w", err)
	}
	defer rows.Close()

	var securities []SecurityInfo
	for rows.Next() {
		var sec SecurityInfo
		err := rows.Scan(&sec.ISIN, &sec.Symbol, &sec.ProductType)
		if err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}
		securities = append(securities, sec)
	}

	return securities, nil
}

// hasSufficientHistory checks if security has data at both training and target dates
// Parameter isin is the ISIN identifier (daily_prices table uses isin column)
// Uses closest available date within ±5 days to handle weekends/holidays
func (dp *DataPrep) hasSufficientHistory(isin string, trainingDate, targetDate time.Time) (bool, error) {
	// Check if we have price data near training date (±5 days)
	var count int
	trainingDateStr := trainingDate.Format("2006-01-02")
	err := dp.historyDB.QueryRow(
		`SELECT COUNT(*) FROM daily_prices
		 WHERE isin = ? AND date BETWEEN date(?, '-5 days') AND date(?, '+5 days')`,
		isin, trainingDateStr, trainingDateStr,
	).Scan(&count)
	if err != nil {
		return false, fmt.Errorf("failed to check training date price: %w", err)
	}
	if count == 0 {
		return false, nil
	}

	// Check if we have price data near target date (±5 days)
	targetDateStr := targetDate.Format("2006-01-02")
	err = dp.historyDB.QueryRow(
		`SELECT COUNT(*) FROM daily_prices
		 WHERE isin = ? AND date BETWEEN date(?, '-5 days') AND date(?, '+5 days')`,
		isin, targetDateStr, targetDateStr,
	).Scan(&count)
	if err != nil {
		return false, fmt.Errorf("failed to check target date price: %w", err)
	}
	if count == 0 {
		return false, nil
	}

	return true, nil
}

// extractInputs extracts all input features for a security at a given date
func (dp *DataPrep) extractInputs(isin string, date time.Time) (*TrainingInputs, error) {
	inputs := &TrainingInputs{
		AdditionalMetrics: make(map[string]float64),
	}

	// Extract scores (use most recent score before or at date)
	var totalScore, longTerm, fundamentals, dividends, opportunity, shortTerm, technicals, opinion, diversification sql.NullFloat64
	err := dp.portfolioDB.QueryRow(`
		SELECT
			total_score,
			cagr_score,
			fundamental_score,
			dividend_bonus,
			opportunity_score,
			drawdown_score,
			technical_score,
			analyst_score,
			allocation_fit_score
		FROM scores
		WHERE isin = ? AND last_updated <= ?
		ORDER BY last_updated DESC
		LIMIT 1
	`, isin, date.Format("2006-01-02")).Scan(
		&totalScore, &longTerm, &fundamentals, &dividends, &opportunity,
		&shortTerm, &technicals, &opinion, &diversification,
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
	if fundamentals.Valid {
		inputs.FundamentalsScore = fundamentals.Float64
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
	if opinion.Valid {
		inputs.OpinionScore = opinion.Float64
	}
	if diversification.Valid {
		inputs.DiversificationScore = diversification.Float64
	}

	// Extract metrics from calculated_metrics (need symbol, not isin)
	// Get symbol from universe DB
	var symbol string
	err = dp.universeDB.QueryRow("SELECT symbol FROM securities WHERE isin = ?", isin).Scan(&symbol)
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
	if inputs.FundamentalsScore == 0 && !fundamentals.Valid {
		inputs.FundamentalsScore = 0.5
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

	// Lookup ISIN from symbol (if universeDB available)
	var isin string
	if dp.universeDB != nil {
		err := dp.universeDB.QueryRow("SELECT isin FROM securities WHERE symbol = ?", symbol).Scan(&isin)
		if err != nil {
			// Symbol not found or no ISIN - return empty map gracefully
			dp.log.Debug().Str("symbol", symbol).Err(err).Msg("Failed to lookup ISIN for symbol")
			return make(map[string]float64), nil
		}
		if isin == "" {
			return make(map[string]float64), nil
		}
	} else {
		// No universeDB - cannot lookup ISIN, return empty map
		dp.log.Debug().Str("symbol", symbol).Msg("UniverseDB not available, cannot lookup ISIN")
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
// Parameter isin is the ISIN identifier (daily_prices table uses isin column)
// Uses closest available date within ±5 days to handle weekends/holidays
func (dp *DataPrep) calculateTargetReturn(isin, startDate, endDate string) (float64, error) {
	// Get price at start date (use closest available date within ±5 days)
	var startPrice sql.NullFloat64
	err := dp.historyDB.QueryRow(
		`SELECT adjusted_close FROM daily_prices
		 WHERE isin = ? AND date BETWEEN date(?, '-5 days') AND date(?, '+5 days')
		 ORDER BY ABS(julianday(date) - julianday(?)) ASC
		 LIMIT 1`,
		isin, startDate, startDate, startDate,
	).Scan(&startPrice)
	if err != nil {
		return 0, fmt.Errorf("failed to get start price: %w", err)
	}
	if !startPrice.Valid || startPrice.Float64 <= 0 {
		return 0, fmt.Errorf("invalid start price for %s at %s", isin, startDate)
	}

	// Get price at end date (use closest available date within ±5 days)
	var endPrice sql.NullFloat64
	err = dp.historyDB.QueryRow(
		`SELECT adjusted_close FROM daily_prices
		 WHERE isin = ? AND date BETWEEN date(?, '-5 days') AND date(?, '+5 days')
		 ORDER BY ABS(julianday(date) - julianday(?)) ASC
		 LIMIT 1`,
		isin, endDate, endDate, endDate,
	).Scan(&endPrice)
	if err != nil {
		return 0, fmt.Errorf("failed to get end price: %w", err)
	}
	if !endPrice.Valid || endPrice.Float64 <= 0 {
		return 0, fmt.Errorf("invalid end price for %s at %s", isin, endDate)
	}

	// Calculate return: (end - start) / start
	returnVal := (endPrice.Float64 - startPrice.Float64) / startPrice.Float64

	// Annualize if needed (for 6 months, multiply by 2; for 12 months, already annual)
	// Actually, we'll keep it as simple return for now, can annualize later if needed
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
