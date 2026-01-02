package optimization

import (
	"database/sql"
	"fmt"
	"math"

	"github.com/aristath/arduino-trader/internal/clients/yahoo"
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
	db          *sql.DB
	yahooClient *yahoo.Client
	log         zerolog.Logger
}

// NewReturnsCalculator creates a new returns calculator.
func NewReturnsCalculator(db *sql.DB, yahooClient *yahoo.Client, log zerolog.Logger) *ReturnsCalculator {
	return &ReturnsCalculator{
		db:          db,
		yahooClient: yahooClient,
		log:         log.With().Str("component", "returns").Logger(),
	}
}

// CalculateExpectedReturns calculates expected returns for all securities.
func (rc *ReturnsCalculator) CalculateExpectedReturns(
	securities []Security,
	regime string,
	dividendBonuses map[string]float64,
) (map[string]float64, error) {
	expectedReturns := make(map[string]float64)

	// Calculate forward-looking market indicator adjustment
	forwardAdjustment := rc.calculateForwardAdjustment()

	targetReturn := OptimizerTargetReturn

	for _, security := range securities {
		expReturn, err := rc.calculateSingle(
			security,
			targetReturn,
			dividendBonuses[security.Symbol],
			regime,
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
			expectedReturns[security.Symbol] = *expReturn
		}
	}

	rc.log.Info().
		Int("num_securities", len(expectedReturns)).
		Str("regime", regime).
		Float64("forward_adjustment", forwardAdjustment).
		Msg("Calculated expected returns")

	return expectedReturns, nil
}

// calculateForwardAdjustment calculates forward-looking market indicator adjustment.
// Combines adjustments from VIX, yield curve, and market P/E.
// Returns adjustment factor (e.g., -0.05 = reduce by 5%).
func (rc *ReturnsCalculator) calculateForwardAdjustment() float64 {
	var totalAdjustment float64

	// 1. VIX adjustment (volatility/fear indicator)
	vixPrice, err := rc.yahooClient.GetCurrentPrice("^VIX", nil, 2)
	if err == nil && vixPrice != nil {
		vix := *vixPrice
		var vixAdj float64

		if vix >= VIXHigh { // >= 25 (high volatility)
			// Very high volatility: reduce by up to 10%
			normalized := math.Min(1.0, (vix-VIXHigh)/20.0)
			vixAdj = -VIXAdjustmentMax * normalized
		} else if vix <= VIXLow { // <= 12 (low volatility)
			// Low volatility: increase by up to 5%
			normalized := 1.0 - (vix / VIXLow)
			vixAdj = VIXAdjustmentMax * 0.5 * normalized
		} else {
			// Normal range: no adjustment
			vixAdj = 0.0
		}

		totalAdjustment += vixAdj
		rc.log.Debug().
			Float64("vix", vix).
			Float64("vix_adjustment", vixAdj).
			Msg("VIX adjustment calculated")
	} else {
		rc.log.Debug().Msg("VIX not available, skipping VIX adjustment")
	}

	// 2. Market P/E adjustment (valuation indicator)
	fundamentals, err := rc.yahooClient.GetFundamentalData("^GSPC", nil)
	if err == nil && fundamentals != nil && fundamentals.PERatio != nil {
		marketPE := *fundamentals.PERatio
		var peAdj float64

		if marketPE >= PEExpensive { // >= 25 (expensive market)
			// Expensive market: reduce by up to 10%
			normalized := math.Min(1.0, (marketPE-PEExpensive)/(PEExpensive*0.5))
			peAdj = -PEAdjustmentMax * normalized
		} else if marketPE <= PECheap { // <= 15 (cheap market)
			// Cheap market: increase by up to 5%
			normalized := 1.0 - ((marketPE - PECheap) / (PEFair - PECheap))
			peAdj = PEAdjustmentMax * 0.5 * normalized
		} else {
			// Fair value range: no adjustment
			peAdj = 0.0
		}

		totalAdjustment += peAdj
		rc.log.Debug().
			Float64("market_pe", marketPE).
			Float64("pe_adjustment", peAdj).
			Msg("Market P/E adjustment calculated")
	} else {
		rc.log.Debug().Msg("Market P/E not available, skipping P/E adjustment")
	}

	// 3. Yield curve adjustment (recession signal)
	// Note: Treasury yields would require an external API (not implemented yet)
	// When implemented, this would fetch 3M and 10Y yields and calculate slope
	rc.log.Debug().Msg("Yield curve adjustment not implemented, skipping")

	// Cap total adjustment at ±20%
	totalAdjustment = math.Max(-0.20, math.Min(0.20, totalAdjustment))

	rc.log.Info().
		Float64("total_adjustment", totalAdjustment).
		Msg("Calculated forward-looking market adjustment")

	return totalAdjustment
}

// calculateSingle calculates expected return for a single security.
func (rc *ReturnsCalculator) calculateSingle(
	security Security,
	targetReturn float64,
	dividendBonus float64,
	regime string,
	forwardAdjustment float64,
) (*float64, error) {
	symbol := security.Symbol

	// Get CAGR (prefer 5Y, fallback to 10Y)
	cagr, dividendYield, err := rc.getCAGRAndDividend(symbol)
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
	score, err := rc.getScore(symbol)
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

	// Adjust weights based on market regime
	var cagrWeight, scoreWeight, regimelReduction float64
	switch regime {
	case "bull":
		// Bull market: 80% CAGR, 20% score-adjusted (more optimistic)
		cagrWeight = 0.80
		scoreWeight = 0.20
		regimelReduction = 1.0 // No reduction
	case "bear":
		// Bear market: 70% CAGR, 30% score-adjusted, then reduce by 25%
		cagrWeight = ExpectedReturnsCAGRWeight   // 0.70
		scoreWeight = ExpectedReturnsScoreWeight // 0.30
		regimelReduction = 0.75                  // Reduce by 25%
	default:
		// Sideways or default: 70% CAGR, 30% score-adjusted
		cagrWeight = ExpectedReturnsCAGRWeight   // 0.70
		scoreWeight = ExpectedReturnsScoreWeight // 0.30
		regimelReduction = 1.0                   // No reduction
	}

	// Calculate base expected return
	baseReturn := (totalReturnCAGR * cagrWeight) + (targetReturn * scoreFactor * scoreWeight)

	// Apply regime reduction (for bear markets)
	baseReturn = baseReturn * regimelReduction

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

	rc.log.Debug().
		Str("symbol", symbol).
		Float64("cagr", *cagr).
		Float64("dividend_yield", dividendYield).
		Float64("score", score).
		Float64("multiplier", multiplier).
		Str("regime", regime).
		Float64("regime_reduction", regimelReduction).
		Float64("forward_adjustment", forwardAdjustment).
		Float64("dividend_bonus", dividendBonus).
		Float64("expected_return", clamped).
		Msg("Calculated expected return")

	return &clamped, nil
}

// getCAGRAndDividend fetches CAGR and dividend yield from database.
func (rc *ReturnsCalculator) getCAGRAndDividend(symbol string) (*float64, float64, error) {
	query := `
		SELECT
			COALESCE(MAX(CASE WHEN metric_name = 'CAGR_5Y' THEN value END),
			         MAX(CASE WHEN metric_name = 'CAGR_10Y' THEN value END)) as cagr,
			COALESCE(MAX(CASE WHEN metric_name = 'DIVIDEND_YIELD' THEN value END), 0.0) as dividend_yield
		FROM calculations
		WHERE symbol = ?
			AND metric_name IN ('CAGR_5Y', 'CAGR_10Y', 'DIVIDEND_YIELD')
	`

	var cagr sql.NullFloat64
	var dividendYield float64

	err := rc.db.QueryRow(query, symbol).Scan(&cagr, &dividendYield)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, 0.0, nil
		}
		return nil, 0.0, fmt.Errorf("failed to query CAGR: %w", err)
	}

	if !cagr.Valid {
		return nil, 0.0, nil
	}

	cagrValue := cagr.Float64
	return &cagrValue, dividendYield, nil
}

// getScore fetches security score from database.
func (rc *ReturnsCalculator) getScore(symbol string) (float64, error) {
	query := `
		SELECT total_score
		FROM scores
		WHERE symbol = ?
		ORDER BY timestamp DESC
		LIMIT 1
	`

	var score sql.NullFloat64
	err := rc.db.QueryRow(query, symbol).Scan(&score)
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

// Helper functions

// clamp restricts a value to a given range.
func clamp(value, min, max float64) float64 {
	return math.Max(min, math.Min(max, value))
}
