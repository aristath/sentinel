package optimization

import (
	"database/sql"
	"fmt"
	"math"

	"github.com/aristath/sentinel/internal/modules/symbolic_regression"
	"github.com/rs/zerolog"
)

// Constants (from Python scoring module)
const (
	ExpectedReturnMin          = -0.10 // -10% min
	ExpectedReturnMax          = 0.30  // 30% max
	ExpectedReturnsCAGRWeight  = 0.70  // 70% weight on CAGR
	ExpectedReturnsScoreWeight = 0.30  // 30% weight on score
	OptimizerTargetReturn      = 0.11  // 11% default target

	// Forward-looking adjustment limits
	VIXAdjustmentMax        = 0.10 // ±10%
	YieldCurveAdjustmentMax = 0.15 // ±15%
	PEAdjustmentMax         = 0.10 // ±10%

	// Market indicator thresholds
	VIXHigh            = 25.0
	VIXLow             = 12.0
	YieldCurveInverted = -0.005 // -0.5%
	YieldCurveNormal   = 0.015  // 1.5%
	PECheap            = 15.0
	PEFair             = 20.0
	PEExpensive        = 25.0
)

// ReturnsCalculator calculates expected returns for portfolio optimization.
type ReturnsCalculator struct {
	db               *sql.DB // portfolio.db
	securityProvider SecurityProvider
	formulaStorage   *symbolic_regression.FormulaStorage
	log              zerolog.Logger
}

// NewReturnsCalculator creates a new returns calculator.
func NewReturnsCalculator(db *sql.DB, securityProvider SecurityProvider, log zerolog.Logger) *ReturnsCalculator {
	formulaStorage := symbolic_regression.NewFormulaStorage(db, log)
	return &ReturnsCalculator{
		db:               db,
		securityProvider: securityProvider,
		formulaStorage:   formulaStorage,
		log:              log.With().Str("component", "returns").Logger(),
	}
}

// CalculateExpectedReturns calculates expected returns for all securities.
func (rc *ReturnsCalculator) CalculateExpectedReturns(
	securities []Security,
	regimeScore float64,
	dividendBonuses map[string]float64,
	targetReturn float64,
	targetReturnThresholdPct float64,
) (map[string]float64, error) {
	expectedReturns := make(map[string]float64)

	// Calculate forward-looking market indicator adjustment
	forwardAdjustment := rc.calculateForwardAdjustment()

	// Default threshold if not provided (0.80 = 80%)
	if targetReturnThresholdPct <= 0 {
		targetReturnThresholdPct = 0.80
	}

	for _, security := range securities {
		expReturn, err := rc.calculateSingle(
			security,
			targetReturn,
			targetReturnThresholdPct,
			dividendBonuses[security.Symbol],
			regimeScore,
			forwardAdjustment,
		)
		if err != nil {
			rc.log.Warn().
				Str("symbol", security.Symbol).
				Err(err).
				Msg("Failed to calculate expected return")
			continue
		}

		if expReturn != nil {
			expectedReturns[security.ISIN] = *expReturn
		}
	}

	rc.log.Info().
		Int("num_securities", len(expectedReturns)).
		Float64("regime_score", regimeScore).
		Float64("forward_adjustment", forwardAdjustment).
		Msg("Calculated expected returns")

	return expectedReturns, nil
}

// calculateForwardAdjustment calculates forward-looking market indicator adjustment.
// Returns 0 since external market data sources (VIX, P/E) have been removed.
// Market regime adjustments are now handled via internal regime score.
func (rc *ReturnsCalculator) calculateForwardAdjustment() float64 {
	// Forward-looking adjustments disabled - external data sources removed
	// Market regime scoring now handles risk/return adjustments internally
	rc.log.Debug().Msg("Forward adjustment disabled (external data sources removed)")
	return 0.0
}

// calculateSingle calculates expected return for a single security.
func (rc *ReturnsCalculator) calculateSingle(
	security Security,
	targetReturn float64,
	targetReturnThresholdPct float64,
	dividendBonus float64,
	regimeScore float64,
	forwardAdjustment float64,
) (*float64, error) {
	symbol := security.Symbol
	isin := security.ISIN

	// Get CAGR (prefer 5Y, fallback to 10Y)
	// Use ISIN directly (preferred) or lookup from symbol
	cagr, dividendYield, err := rc.getCAGRAndDividend(isin, symbol)
	if err != nil {
		return nil, err
	}
	if cagr == nil {
		rc.log.Debug().
			Str("symbol", symbol).
			Msg("No CAGR data available")
		return nil, nil
	}

	// Add dividend yield to CAGR for total return
	totalReturnCAGR := *cagr + dividendYield

	// Get security score (0-1 range)
	score, err := rc.getScore(isin, symbol)
	if err != nil {
		rc.log.Warn().
			Str("symbol", symbol).
			Err(err).
			Msg("Failed to get score, using 0.5")
		score = 0.5
	}

	// Score factor: score=0.5 means neutral, higher means boost
	// score=1.0 → factor=2.0 (double the target contribution)
	// score=0.5 → factor=1.0 (neutral)
	// score=0.0 → factor=0.0 (no target contribution)
	var scoreFactor float64
	if score <= 0 {
		scoreFactor = 0.0
	} else {
		scoreFactor = score / 0.5
	}

	// Try to use discovered formula first
	securityType := symbolic_regression.SecurityTypeStock
	if security.ProductType == "ETF" || security.ProductType == "MUTUALFUND" {
		securityType = symbolic_regression.SecurityTypeETF
	}

	regimePtr := &regimeScore
	discoveredFormula, err := rc.formulaStorage.GetActiveFormula(
		symbolic_regression.FormulaTypeExpectedReturn,
		securityType,
		regimePtr,
	)

	var baseReturn float64
	if err == nil && discoveredFormula != nil {
		// Use discovered formula
		parsedFormula, parseErr := symbolic_regression.ParseFormula(discoveredFormula.FormulaExpression)
		if parseErr == nil {
			// Build training inputs for formula evaluation
			inputs := symbolic_regression.TrainingInputs{
				CAGR:          totalReturnCAGR,
				TotalScore:    score,
				RegimeScore:   regimeScore,
				DividendYield: dividendYield,
			}

			// Evaluate formula
			formulaFn := symbolic_regression.FormulaToFunction(parsedFormula)
			baseReturn = formulaFn(inputs)

			rc.log.Debug().
				Str("symbol", symbol).
				Str("formula", discoveredFormula.FormulaExpression).
				Float64("base_return", baseReturn).
				Msg("Used discovered formula for expected return")
		} else {
			rc.log.Warn().
				Str("symbol", symbol).
				Err(parseErr).
				Msg("Failed to parse discovered formula, falling back to static formula")
			// Fall through to static formula
			baseReturn = rc.calculateStaticExpectedReturn(
				totalReturnCAGR,
				targetReturn,
				scoreFactor,
				regimeScore,
			)
		}
	} else {
		// No discovered formula, use static formula
		baseReturn = rc.calculateStaticExpectedReturn(
			totalReturnCAGR,
			targetReturn,
			scoreFactor,
			regimeScore,
		)
	}

	// Apply regime reduction (for bear markets) - keep this logic
	regime := math.Max(-1.0, math.Min(1.0, regimeScore))
	regimeReduction := 1.0
	if regime < 0 {
		// reduction 1.00 -> 0.75 as score goes 0 -> -1
		regimeReduction = 1.0 - 0.25*math.Abs(regime)
	}

	// Apply regime reduction (for bear markets)
	baseReturn = baseReturn * regimeReduction

	// Apply forward-looking market indicator adjustment
	baseReturn = baseReturn * (1.0 + forwardAdjustment)

	// Apply user preference multiplier
	multiplier := security.PriorityMultiplier
	if multiplier <= 0 {
		multiplier = 1.0
	}
	adjustedReturn := baseReturn * multiplier

	// Add pending dividend bonus (DRIP fallback)
	finalReturn := adjustedReturn + dividendBonus

	// Clamp to reasonable range
	clamped := clamp(finalReturn, ExpectedReturnMin, ExpectedReturnMax)

	// Apply target return filtering with absolute minimum guardrail
	// Absolute minimum: Never allow below 6% or 50% of target (whichever is higher)
	absoluteMinReturn := math.Max(0.06, targetReturn*0.50)
	if clamped < absoluteMinReturn {
		rc.log.Debug().
			Str("symbol", symbol).
			Float64("expected_return", clamped).
			Float64("absolute_min", absoluteMinReturn).
			Msg("Filtered out: below absolute minimum return (hard filter)")
		return nil, nil // Hard filter: exclude regardless of quality
	}

	// Flexible penalty system: Apply penalty if below threshold, but allow quality to overcome it
	// Minimum threshold: target * threshold_pct (default 80% of target)
	minExpectedReturnThreshold := targetReturn * targetReturnThresholdPct
	if clamped < minExpectedReturnThreshold {
		// Calculate penalty based on how far below threshold
		// Penalty increases as return gets further below threshold
		// Max penalty: 30% reduction
		shortfallRatio := (minExpectedReturnThreshold - clamped) / minExpectedReturnThreshold
		penalty := math.Min(0.3, shortfallRatio*0.5) // Up to 30% penalty

		// Quality override: Get quality scores for penalty reduction
		longTermScore, stabilityScore := rc.getQualityScores(isin, symbol)
		qualityScore := 0.0
		if longTermScore != nil && stabilityScore != nil {
			qualityScore = (*longTermScore + *stabilityScore) / 2.0
		} else if longTermScore != nil {
			qualityScore = *longTermScore
		} else if stabilityScore != nil {
			qualityScore = *stabilityScore
		}

		// Apply quality override: Only exceptional quality gets significant reduction
		if qualityScore > 0.80 {
			penalty *= 0.65 // Reduce penalty by 35% for exceptional quality (0.80+)
		} else if qualityScore > 0.75 {
			penalty *= 0.80 // Reduce penalty by 20% for high quality (0.75-0.80)
		}
		// Quality below 0.75 gets no override (full penalty applies)

		// Apply penalty to expected return
		clamped = clamped * (1.0 - penalty)

		rc.log.Debug().
			Str("symbol", symbol).
			Float64("expected_return_before_penalty", finalReturn).
			Float64("expected_return_after_penalty", clamped).
			Float64("min_threshold", minExpectedReturnThreshold).
			Float64("penalty", penalty).
			Float64("quality_score", qualityScore).
			Msg("Applied flexible penalty (quality-aware)")
	}

	rc.log.Debug().
		Str("symbol", symbol).
		Float64("cagr", *cagr).
		Float64("dividend_yield", dividendYield).
		Float64("score", score).
		Float64("multiplier", multiplier).
		Float64("regime_score", regimeScore).
		Float64("regime_reduction", regimeReduction).
		Float64("forward_adjustment", forwardAdjustment).
		Float64("dividend_bonus", dividendBonus).
		Float64("expected_return", clamped).
		Msg("Calculated expected return")

	return &clamped, nil
}

// getCAGRAndDividend fetches CAGR and dividend yield from database.
// CAGR is stored in scores.cagr_score (normalized 0-1), dividend yield in scores.dividend_bonus.
// Uses ISIN directly (preferred) or looks up ISIN from symbol if not available.
func (rc *ReturnsCalculator) getCAGRAndDividend(isin string, symbol string) (*float64, float64, error) {
	var queryISIN string

	if isin != "" {
		// Use ISIN directly (PRIMARY KEY lookup - fastest)
		queryISIN = isin
	} else if rc.securityProvider != nil {
		// Lookup ISIN from securities table via provider
		var err error
		queryISIN, err = rc.securityProvider.GetISINBySymbol(symbol)
		if err != nil {
			return nil, 0.0, nil // Security not found
		}
		if queryISIN == "" {
			return nil, 0.0, nil // No ISIN found
		}
	} else {
		// No ISIN and no securityProvider - cannot query
		return nil, 0.0, fmt.Errorf("ISIN required but not available and securityProvider not provided")
	}

	// Query scores directly by ISIN (PRIMARY KEY - fastest)
	query := `
		SELECT
			cagr_score,
			COALESCE(dividend_bonus, 0.0) as dividend_yield
		FROM scores
		WHERE isin = ?
		ORDER BY last_updated DESC
		LIMIT 1
	`

	var cagr sql.NullFloat64
	var dividendYield float64

	err := rc.db.QueryRow(query, queryISIN).Scan(&cagr, &dividendYield)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, 0.0, nil
		}
		return nil, 0.0, fmt.Errorf("failed to query CAGR: %w", err)
	}

	if !cagr.Valid || cagr.Float64 <= 0 {
		return nil, dividendYield, nil
	}

	// cagr_score is normalized 0-1, convert back to approximate CAGR percentage
	// Reverse mapping based on scoreCAGRWithBubbleDetection logic:
	// - cagr_score 1.0 → ~20% CAGR (excellent)
	// - cagr_score 0.8 → ~11% CAGR (target)
	// - cagr_score 0.5 → ~6-8% CAGR (below target)
	// - cagr_score 0.15 → 0% CAGR (floor)
	// Linear interpolation between key points
	cagrScore := cagr.Float64
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

	return &cagrValue, dividendYield, nil
}

// convertCAGRScoreToCAGR converts normalized cagr_score (0-1) back to approximate CAGR percentage.
// Reverse mapping based on scoreCAGRWithBubbleDetection logic:
// - cagr_score 1.0 → ~20% CAGR (excellent)
// - cagr_score 0.8 → ~11% CAGR (target)
// - cagr_score 0.5 → ~6-8% CAGR (below target)
// - cagr_score 0.15 → 0% CAGR (floor)
// Linear interpolation between key points
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

// getScore fetches security score from database.
// Uses ISIN directly (preferred) or looks up ISIN from symbol if not available.
func (rc *ReturnsCalculator) getScore(isin string, symbol string) (float64, error) {
	var queryISIN string

	if isin != "" {
		// Use ISIN directly (PRIMARY KEY lookup - fastest)
		queryISIN = isin
	} else if rc.securityProvider != nil {
		// Lookup ISIN from securities table via provider
		var err error
		queryISIN, err = rc.securityProvider.GetISINBySymbol(symbol)
		if err != nil {
			return 0.5, nil // Security not found, default to neutral
		}
		if queryISIN == "" {
			return 0.5, nil // No ISIN found, default to neutral
		}
	} else {
		// No ISIN and no securityProvider - cannot query
		return 0.5, fmt.Errorf("ISIN required but not available and securityProvider not provided")
	}

	// Query scores directly by ISIN (PRIMARY KEY - fastest)
	query := `SELECT total_score FROM scores WHERE isin = ? ORDER BY last_updated DESC LIMIT 1`

	var score sql.NullFloat64
	err := rc.db.QueryRow(query, queryISIN).Scan(&score)
	if err != nil {
		if err == sql.ErrNoRows {
			return 0.5, nil // Default to neutral
		}
		return 0.5, fmt.Errorf("failed to query score: %w", err)
	}

	if !score.Valid {
		return 0.5, nil
	}

	return score.Float64, nil
}

// getQualityScores fetches long-term and stability scores for quality override calculation.
// Uses cagr_score as proxy for long-term and stability_score for stability.
// Uses ISIN directly (preferred) or looks up ISIN from symbol if not available.
func (rc *ReturnsCalculator) getQualityScores(isin string, symbol string) (*float64, *float64) {
	var queryISIN string

	if isin != "" {
		// Use ISIN directly (PRIMARY KEY lookup - fastest)
		queryISIN = isin
	} else if rc.securityProvider != nil {
		// Lookup ISIN from securities table via provider
		var err error
		queryISIN, err = rc.securityProvider.GetISINBySymbol(symbol)
		if err != nil {
			return nil, nil // Security not found
		}
		if queryISIN == "" {
			return nil, nil // No ISIN found
		}
	} else {
		// No ISIN and no securityProvider - cannot query
		rc.log.Debug().
			Str("symbol", symbol).
			Msg("ISIN required but not available and securityProvider not provided")
		return nil, nil
	}

	// Query scores directly by ISIN (PRIMARY KEY - fastest)
	query := `SELECT cagr_score, stability_score FROM scores WHERE isin = ? ORDER BY last_updated DESC LIMIT 1`

	var cagrScore, stabilityScore sql.NullFloat64
	err := rc.db.QueryRow(query, queryISIN).Scan(&cagrScore, &stabilityScore)
	if err != nil {
		if err != sql.ErrNoRows {
			rc.log.Debug().
				Str("isin", isin).
				Str("symbol", symbol).
				Err(err).
				Msg("Failed to query quality scores")
		}
		return nil, nil
	}

	var longTermPtr, stabilityPtr *float64
	if cagrScore.Valid {
		// Use cagr_score as proxy for long-term (normalize to 0-1 range)
		// CAGR scores are typically in 0-1 range already, but normalize if needed
		normalized := math.Max(0.0, math.Min(1.0, cagrScore.Float64))
		longTermPtr = &normalized
	}
	if stabilityScore.Valid {
		normalized := math.Max(0.0, math.Min(1.0, stabilityScore.Float64))
		stabilityPtr = &normalized
	}

	return longTermPtr, stabilityPtr
}

// calculateStaticExpectedReturn calculates expected return using the static formula
// This is the fallback when no discovered formula is available
func (rc *ReturnsCalculator) calculateStaticExpectedReturn(
	totalReturnCAGR float64,
	targetReturn float64,
	scoreFactor float64,
	regimeScore float64,
) float64 {
	regime := math.Max(-1.0, math.Min(1.0, regimeScore))

	// Continuous regime adjustment:
	// - Bull (score→+1): tilt more toward CAGR (0.80/0.20)
	// - Neutral (score=0): baseline (0.70/0.30)
	// - Bear (score→-1): keep weights, but apply a continuous reduction up to 25%
	cagrWeight := ExpectedReturnsCAGRWeight   // 0.70 baseline
	scoreWeight := ExpectedReturnsScoreWeight // 0.30 baseline

	if regime >= 0 {
		// interpolate 0.70 -> 0.80 as score goes 0 -> 1
		cagrWeight = ExpectedReturnsCAGRWeight + (0.80-ExpectedReturnsCAGRWeight)*regime
		scoreWeight = 1.0 - cagrWeight
	}

	// Calculate base expected return using static formula
	return (totalReturnCAGR * cagrWeight) + (targetReturn * scoreFactor * scoreWeight)
}

// Helper functions

// clamp restricts a value to a given range.
func clamp(value, min, max float64) float64 {
	return math.Max(min, math.Min(max, value))
}
