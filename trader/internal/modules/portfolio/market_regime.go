package portfolio

import (
	"fmt"
	"math"

	"github.com/rs/zerolog"
)

// MarketRegimeScore represents market condition as continuous score
// Range: -1.0 (extreme bear) to +1.0 (extreme bull)
// 0.0 = neutral/sideways
// Allows gradual transitions: 0.3 = "bull-ish", -0.2 = "bear-ish"
type MarketRegimeScore float64

// Helper constants for reference (but use continuous score)
const (
	ExtremeBearScore MarketRegimeScore = -1.0
	BearScore        MarketRegimeScore = -0.5
	NeutralScore     MarketRegimeScore = 0.0
	BullScore        MarketRegimeScore = 0.5
	ExtremeBullScore MarketRegimeScore = 1.0
)

// MarketRegimeDetector analyzes market conditions to determine regime
type MarketRegimeDetector struct {
	log               zerolog.Logger
	indexService      *MarketIndexService // Market index service for market-wide detection
	regimePersistence *RegimePersistence  // Regime persistence for smoothing
	// Smoothing parameters
	smoothingAlpha float64 // Exponential moving average alpha (default 0.1)
}

// TanhCompressionFactor controls the compression of extremes in tanh transformation
// Higher values = more compression, lower values = more linear
const TanhCompressionFactor = 2.0

// NewMarketRegimeDetector creates a new market regime detector
func NewMarketRegimeDetector(log zerolog.Logger) *MarketRegimeDetector {
	return &MarketRegimeDetector{
		log:            log.With().Str("component", "market_regime_detector").Logger(),
		smoothingAlpha: 0.1, // Default: slow adaptation (matches slow-growth strategy)
	}
}

// SetMarketIndexService sets the market index service for market-wide detection
func (d *MarketRegimeDetector) SetMarketIndexService(service *MarketIndexService) {
	d.indexService = service
}

// SetRegimePersistence sets the regime persistence for smoothing
func (d *MarketRegimeDetector) SetRegimePersistence(persistence *RegimePersistence) {
	d.regimePersistence = persistence
}

// CalculateRegimeScoreFromMetrics calculates continuous regime score from raw metrics
func (d *MarketRegimeDetector) CalculateRegimeScoreFromMetrics(portfolioReturn, volatility, maxDrawdown float64) MarketRegimeScore {
	// Normalize components
	returnComp := d.NormalizeReturn(portfolioReturn)
	volComp := d.NormalizeVolatility(volatility)
	ddComp := d.NormalizeDrawdown(maxDrawdown)

	// Special case: Original logic had OR condition for bear
	// Bear if: (return < -0.0005) OR (vol > 0.03) OR (DD < -0.12)
	// If any condition is met, ensure score is negative enough to be classified as bear
	// Check raw thresholds first before normalization
	isBearByReturn := portfolioReturn < -0.0005
	isBearByVol := volatility > 0.03
	isBearByDD := maxDrawdown < -0.12

	if isBearByReturn || isBearByVol || isBearByDD {
		// At least one bear condition is met - ensure score reflects this
		// Calculate score normally first
		score := d.CalculateRegimeScore(returnComp, volComp, ddComp)

		// If the score is not negative enough to be bear (< -0.15), force it more negative
		// This ensures OR logic is preserved: any condition alone can trigger bear
		if float64(score) > -0.15 {
			// Force score negative based on which condition triggered
			// Use the most negative of the condition-specific scores
			var forcedScore float64 = -1.0 // Start with most negative possible

			if isBearByDD {
				// Drawdown alone can trigger bear - use drawdown-dominated score
				ddDominantScore := returnComp*0.05 + ddComp*0.95
				ddScore := math.Tanh(ddDominantScore * TanhCompressionFactor)
				if ddScore < forcedScore {
					forcedScore = ddScore
				}
			}
			if isBearByVol {
				// Volatility alone can trigger bear - use volatility-dominated score
				volDominantScore := returnComp*0.05 + volComp*0.95
				volScore := math.Tanh(volDominantScore * TanhCompressionFactor)
				if volScore < forcedScore {
					forcedScore = volScore
				}
			}
			if isBearByReturn {
				// Negative return alone can trigger bear
				returnScore := math.Tanh(returnComp * TanhCompressionFactor)
				if returnScore < forcedScore {
					forcedScore = returnScore
				}
			}

			// Always return the forced score (it will be negative enough for bear)
			return MarketRegimeScore(forcedScore)
		}

		return score
	}

	// No bear conditions met - calculate normally
	return d.CalculateRegimeScore(returnComp, volComp, ddComp)
}

// Helper functions

func calculateMean(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}

	sum := 0.0
	for _, v := range values {
		sum += v
	}
	return sum / float64(len(values))
}

func calculateStdDev(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}

	mean := calculateMean(values)
	sumSquaredDiff := 0.0
	for _, v := range values {
		diff := v - mean
		sumSquaredDiff += diff * diff
	}
	variance := sumSquaredDiff / float64(len(values))
	return sqrt(variance)
}

func sqrt(x float64) float64 {
	// Simple Newton's method for square root
	if x == 0 {
		return 0
	}
	z := x
	for i := 0; i < 10; i++ {
		z = (z + x/z) / 2
	}
	return z
}

func calculateMaxDrawdown(returns []float64) float64 {
	if len(returns) == 0 {
		return 0
	}

	// Calculate cumulative returns
	cumulative := 1.0
	peak := 1.0
	maxDrawdown := 0.0

	for _, r := range returns {
		cumulative *= (1 + r)
		if cumulative > peak {
			peak = cumulative
		}
		drawdown := (cumulative - peak) / peak
		if drawdown < maxDrawdown {
			maxDrawdown = drawdown
		}
	}

	return maxDrawdown
}

// CalculateRegimeScore calculates continuous regime score from normalized components
// Uses tanh transformation for non-linear compression
//
// Parameters:
//   - returnComponent: Normalized return component (-1.0 to +1.0)
//   - volComponent: Normalized volatility component (-1.0 to +1.0, inverted: high vol = negative)
//   - ddComponent: Normalized drawdown component (-1.0 to +1.0, inverted: large DD = negative)
//
// Returns: Continuous regime score (-1.0 to +1.0) after tanh transformation
//
// Note: This function works with normalized components only. OR logic for raw metrics
// is handled in CalculateRegimeScoreFromMetrics, which has access to raw thresholds.
func (d *MarketRegimeDetector) CalculateRegimeScore(returnComponent, volComponent, ddComponent float64) MarketRegimeScore {
	// Weighted combination of normalized components
	rawScore := (returnComponent * 0.50) + (volComponent * 0.25) + (ddComponent * 0.25)

	// Apply tanh transformation for non-linear compression
	// Tanh compresses extremes, more sensitive in middle range
	regimeScore := math.Tanh(rawScore * TanhCompressionFactor)

	return MarketRegimeScore(regimeScore)
}

// NormalizeReturn normalizes daily return to -1.0 to +1.0 range
// Positive returns → positive component, negative returns → negative component
// Adjusted to better match original discrete thresholds:
// - Bull: return > 0.0005 → should give positive score
// - Bear: return < -0.0005 → should give negative score
func (d *MarketRegimeDetector) NormalizeReturn(dailyReturn float64) float64 {
	// Normalize: 0.0005 (0.05% daily, bull threshold) → ~0.3
	// Use a scaling factor that maps 0.0005 to ~0.3
	scale := 600.0 // 0.0005 * 600 = 0.3
	normalized := dailyReturn * scale

	// Clamp to -1.0 to +1.0
	if normalized > 1.0 {
		return 1.0
	}
	if normalized < -1.0 {
		return -1.0
	}
	return normalized
}

// NormalizeVolatility normalizes volatility to -1.0 to +1.0 range (inverted)
// High volatility → negative component, low volatility → positive component
// Adjusted to better match original thresholds: bear if vol > 0.03 (3% daily)
func (d *MarketRegimeDetector) NormalizeVolatility(volatility float64) float64 {
	// Inverted: lower volatility is better (positive), higher is worse (negative)
	// Normalize: 0.03 (3% daily, bear threshold) → ~-0.4
	// Use a scaling factor that maps 0.03 to ~-0.4
	scale := 15.0   // Adjusted for better threshold matching
	baseVol := 0.02 // 2% daily as neutral point

	// Invert: subtract from base and negate
	normalized := -(volatility - baseVol) * scale

	// Clamp to -1.0 to +1.0
	if normalized > 1.0 {
		return 1.0
	}
	if normalized < -1.0 {
		return -1.0
	}
	return normalized
}

// NormalizeDrawdown normalizes drawdown to -1.0 to +1.0 range (inverted)
// Large drawdown → negative component, small drawdown → positive component
// Note: drawdown is already negative (e.g., -0.15 for 15% drawdown)
// Adjusted to better match original thresholds: bear if DD < -0.12 (12% drawdown)
func (d *MarketRegimeDetector) NormalizeDrawdown(drawdown float64) float64 {
	// Inverted: smaller drawdown is better (positive), larger is worse (negative)
	// Drawdown is negative, so we need to handle it carefully
	// Normalize: -0.12 (12% DD, bear threshold) → ~-0.35, -0.15 (15% DD) → ~-0.5
	// Use a scaling factor that makes -0.12 map to around -0.35 (just below OR threshold)
	scale := 5.8    // Adjusted to make -0.12 map to ~-0.35
	baseDD := -0.05 // -5% as neutral point (adjusted for better threshold matching)

	// Invert: subtract from base and negate
	// Since drawdown is negative, we want: smaller (less negative) = better (positive)
	// Formula: -(drawdown - baseDD) * scale
	// Example: -(-0.15 - (-0.05)) * 5.8 = -(-0.10) * 5.8 = -0.58
	normalized := -(drawdown - baseDD) * scale

	// Clamp to -1.0 to +1.0
	if normalized > 1.0 {
		return 1.0
	}
	if normalized < -1.0 {
		return -1.0
	}
	return normalized
}

// ApplySmoothing applies exponential moving average smoothing to prevent rapid oscillation
// Formula: smoothed = alpha * current + (1 - alpha) * lastSmoothed
func (d *MarketRegimeDetector) ApplySmoothing(currentScore, lastSmoothed, alpha float64) float64 {
	// If no previous value, return current (first time)
	if lastSmoothed == 0.0 && currentScore != 0.0 {
		return currentScore
	}

	smoothed := alpha*currentScore + (1.0-alpha)*lastSmoothed

	// Clamp to valid range
	if smoothed > 1.0 {
		return 1.0
	}
	if smoothed < -1.0 {
		return -1.0
	}
	return smoothed
}

// CalculateRegimeScoreFromReturns calculates regime score from raw daily returns
func (d *MarketRegimeDetector) CalculateRegimeScoreFromReturns(returns []float64) MarketRegimeScore {
	if len(returns) == 0 {
		return NeutralScore
	}

	// Calculate metrics
	avgReturn := calculateMean(returns)
	volatility := calculateStdDev(returns)
	drawdown := calculateMaxDrawdown(returns)

	// Normalize components
	returnComp := d.NormalizeReturn(avgReturn)
	volComp := d.NormalizeVolatility(volatility)
	ddComp := d.NormalizeDrawdown(drawdown)

	// Calculate score
	return d.CalculateRegimeScore(returnComp, volComp, ddComp)
}

// CalculateRegimeScoreFromMarketIndices calculates regime score from market indices
// This is the primary method for market-wide regime detection
func (d *MarketRegimeDetector) CalculateRegimeScoreFromMarketIndices(windowDays int) (MarketRegimeScore, error) {
	if d.indexService == nil {
		return NeutralScore, fmt.Errorf("market index service not set")
	}

	// Get market returns from indices
	returns, err := d.indexService.GetMarketReturns(windowDays)
	if err != nil {
		return NeutralScore, fmt.Errorf("failed to get market returns: %w", err)
	}

	if len(returns) == 0 {
		return NeutralScore, fmt.Errorf("no market returns available")
	}

	// Calculate regime score from returns
	score := d.CalculateRegimeScoreFromReturns(returns)

	// Apply smoothing if persistence is available
	if d.regimePersistence != nil {
		// Record raw score
		err = d.regimePersistence.RecordRegimeScore(score)
		if err != nil {
			d.log.Warn().Err(err).Msg("Failed to record regime score")
		}

		// Get smoothed score
		smoothed, err := d.regimePersistence.GetSmoothedScore()
		if err != nil {
			d.log.Warn().Err(err).Msg("Failed to get smoothed score, using raw score")
			return score, nil
		}

		return smoothed, nil
	}

	return score, nil
}

// GetRegimeScore returns the current smoothed regime score
// This is the main method to get the current regime state
func (d *MarketRegimeDetector) GetRegimeScore() (MarketRegimeScore, error) {
	if d.regimePersistence != nil {
		return d.regimePersistence.GetCurrentRegimeScore()
	}

	// Fallback: calculate from market indices if available
	if d.indexService != nil {
		return d.CalculateRegimeScoreFromMarketIndices(30) // Default 30-day window
	}

	return NeutralScore, fmt.Errorf("no data source available")
}
