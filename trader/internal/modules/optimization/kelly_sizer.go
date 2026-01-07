package optimization

import (
	"fmt"
	"math"

	"github.com/aristath/portfolioManager/internal/modules/portfolio"
	"github.com/rs/zerolog"
)

// KellyPositionSizer calculates optimal position sizes using the Kelly Criterion
// with constraints and adaptive fractional Kelly based on regime and confidence.
type KellyPositionSizer struct {
	riskFreeRate    float64
	fixedFractional float64
	minPositionSize float64
	maxPositionSize float64
	fractionalMode  string // "fixed" or "adaptive"
	returnsCalc     *ReturnsCalculator
	riskBuilder     *RiskModelBuilder
	regimeDetector  *portfolio.MarketRegimeDetector
	log             zerolog.Logger
}

// KellySizeResult contains the result of Kelly sizing calculation.
type KellySizeResult struct {
	KellyFraction        float64
	ConstrainedFraction  float64
	FractionalMultiplier float64
	RegimeAdjustment     float64
	FinalSize            float64
}

// NewKellyPositionSizer creates a new Kelly position sizer.
func NewKellyPositionSizer(
	riskFreeRate float64,
	fixedFractional float64,
	minPositionSize float64,
	maxPositionSize float64,
	returnsCalc *ReturnsCalculator,
	riskBuilder *RiskModelBuilder,
	regimeDetector *portfolio.MarketRegimeDetector,
) *KellyPositionSizer {
	log := zerolog.Nop()
	if returnsCalc != nil {
		log = returnsCalc.log
	}

	return &KellyPositionSizer{
		riskFreeRate:    riskFreeRate,
		fixedFractional: fixedFractional,
		minPositionSize: minPositionSize,
		maxPositionSize: maxPositionSize,
		fractionalMode:  "adaptive", // Default to adaptive
		returnsCalc:     returnsCalc,
		riskBuilder:     riskBuilder,
		regimeDetector:  regimeDetector,
		log:             log.With().Str("component", "kelly_sizer").Logger(),
	}
}

// SetFractionalMode sets the fractional Kelly mode.
func (ks *KellyPositionSizer) SetFractionalMode(mode string) {
	if mode == "fixed" || mode == "adaptive" {
		ks.fractionalMode = mode
	}
}

// CalculateOptimalSize calculates the optimal position size using Kelly Criterion
// with constraints and adaptive adjustments.
//
// Args:
//   - expectedReturn: Expected return for the security (annualized)
//   - variance: Variance of returns (annualized)
//   - confidence: Confidence level in the expected return (0.0 to 1.0)
//   - regimeScore: Current market regime score (-1.0 to +1.0)
//
// Returns:
//   - Optimal position size as fraction of portfolio (0.0 to 1.0)
func (ks *KellyPositionSizer) CalculateOptimalSize(
	expectedReturn float64,
	variance float64,
	confidence float64,
	regimeScore float64,
) float64 {
	// Step 1: Calculate raw Kelly fraction
	kellyFraction := ks.calculateKellyFraction(expectedReturn, ks.riskFreeRate, variance)

	// Step 2: Apply fractional Kelly (adaptive or fixed)
	fractionalMultiplier := ks.getFractionalMultiplier(regimeScore, confidence)
	fractionalKelly := kellyFraction * fractionalMultiplier

	// Step 3: Apply regime adjustment (more conservative in bear markets)
	regimeAdjusted := ks.applyRegimeAdjustment(fractionalKelly, regimeScore)

	// Step 4: Apply constraints (min/max bounds)
	finalSize := ks.applyConstraints(regimeAdjusted)

	return finalSize
}

// CalculateOptimalSizeForSymbol calculates optimal size for a security by symbol.
// This is a convenience method that looks up expected return and variance.
func (ks *KellyPositionSizer) CalculateOptimalSizeForSymbol(
	symbol string,
	expectedReturns map[string]float64,
	covMatrix [][]float64,
	symbols []string,
	confidence float64,
	regimeScore float64,
) (float64, error) {
	// Get expected return
	expectedReturn, hasReturn := expectedReturns[symbol]
	if !hasReturn {
		return ks.minPositionSize, fmt.Errorf("no expected return for symbol %s", symbol)
	}

	// Get variance from covariance matrix diagonal
	variance, err := ks.getVarianceFromCovMatrix(symbol, covMatrix, symbols)
	if err != nil {
		return ks.minPositionSize, fmt.Errorf("failed to get variance for %s: %w", symbol, err)
	}

	// Calculate optimal size
	optimalSize := ks.CalculateOptimalSize(expectedReturn, variance, confidence, regimeScore)

	return optimalSize, nil
}

// calculateKellyFraction calculates the raw Kelly fraction.
// Formula: (expectedReturn - riskFreeRate) / variance
func (ks *KellyPositionSizer) calculateKellyFraction(expectedReturn, riskFreeRate, variance float64) float64 {
	// Edge = expected return - risk-free rate
	edge := expectedReturn - riskFreeRate

	// If no edge or negative edge, return 0
	if edge <= 0 {
		return 0.0
	}

	// If variance is zero or very small, return 0 (division by zero protection)
	if variance <= 1e-10 {
		return 0.0
	}

	// Kelly fraction = edge / variance
	kellyFraction := edge / variance

	// Ensure non-negative
	if kellyFraction < 0 {
		return 0.0
	}

	return kellyFraction
}

// applyConstraints applies min/max constraints to Kelly fraction.
func (ks *KellyPositionSizer) applyConstraints(kellyFraction float64) float64 {
	// Floor at minimum position size
	if kellyFraction < ks.minPositionSize {
		return ks.minPositionSize
	}

	// Cap at maximum position size
	if kellyFraction > ks.maxPositionSize {
		return ks.maxPositionSize
	}

	return kellyFraction
}

// applyFractionalKelly applies fractional Kelly multiplier.
func (ks *KellyPositionSizer) applyFractionalKelly(kellyFraction float64, regimeScore float64, confidence float64) float64 {
	multiplier := ks.getFractionalMultiplier(regimeScore, confidence)
	return kellyFraction * multiplier
}

// getFractionalMultiplier returns the fractional Kelly multiplier based on mode.
func (ks *KellyPositionSizer) getFractionalMultiplier(regimeScore float64, confidence float64) float64 {
	if ks.fractionalMode == "fixed" {
		return ks.fixedFractional
	}

	// Adaptive mode: multiplier based on regime and confidence
	// Range: 0.25 (very conservative) to 0.75 (moderate)
	// Base: 0.5 (half-Kelly)
	baseMultiplier := 0.5

	// Confidence adjustment: ±0.15 based on confidence (0.0 to 1.0)
	// High confidence (0.8+) → +0.15, Low confidence (0.3-) → -0.15
	confidenceAdjustment := (confidence - 0.5) * 0.3 // Maps 0.0-1.0 to -0.15 to +0.15

	// Regime adjustment: ±0.10 based on regime
	// Bull (0.5+) → +0.10, Bear (-0.5-) → -0.10
	regimeAdjustment := 0.0
	if regimeScore > 0.5 {
		regimeAdjustment = 0.10 // Bull market: more aggressive
	} else if regimeScore < -0.5 {
		regimeAdjustment = -0.10 // Bear market: more conservative
	}

	// Calculate final multiplier
	multiplier := baseMultiplier + confidenceAdjustment + regimeAdjustment

	// Clamp to range [0.25, 0.75]
	if multiplier < 0.25 {
		multiplier = 0.25
	}
	if multiplier > 0.75 {
		multiplier = 0.75
	}

	return multiplier
}

// applyRegimeAdjustment applies regime-based adjustment to Kelly fraction.
// More conservative in bear markets.
func (ks *KellyPositionSizer) applyRegimeAdjustment(kellyFraction float64, regimeScore float64) float64 {
	// Only reduce in bear markets (regimeScore < 0)
	if regimeScore >= 0 {
		return kellyFraction
	}

	// Reduction factor: 1.0 (no reduction) to 0.75 (25% reduction) as regime goes 0 to -1.0
	// Formula: 1.0 - 0.25 * |regimeScore| for negative regime scores
	reductionFactor := 1.0 - 0.25*math.Abs(regimeScore)

	// Clamp reduction factor to [0.75, 1.0]
	if reductionFactor < 0.75 {
		reductionFactor = 0.75
	}

	return kellyFraction * reductionFactor
}

// getVarianceFromCovMatrix extracts variance for a symbol from covariance matrix.
func (ks *KellyPositionSizer) getVarianceFromCovMatrix(symbol string, covMatrix [][]float64, symbols []string) (float64, error) {
	// Find symbol index
	symbolIndex := -1
	for i, s := range symbols {
		if s == symbol {
			symbolIndex = i
			break
		}
	}

	if symbolIndex < 0 {
		return 0.0, fmt.Errorf("symbol %s not found in symbols list", symbol)
	}

	if symbolIndex >= len(covMatrix) {
		return 0.0, fmt.Errorf("symbol index %d out of bounds for covariance matrix", symbolIndex)
	}

	if symbolIndex >= len(covMatrix[symbolIndex]) {
		return 0.0, fmt.Errorf("covariance matrix row %d has insufficient columns", symbolIndex)
	}

	// Variance is the diagonal element
	variance := covMatrix[symbolIndex][symbolIndex]

	if variance < 0 {
		return 0.0, fmt.Errorf("negative variance for symbol %s: %f", symbol, variance)
	}

	return variance, nil
}

// CalculateOptimalSizesForAll calculates optimal sizes for all securities.
func (ks *KellyPositionSizer) CalculateOptimalSizesForAll(
	expectedReturns map[string]float64,
	covMatrix [][]float64,
	symbols []string,
	confidences map[string]float64,
	regimeScore float64,
) (map[string]float64, error) {
	result := make(map[string]float64, len(symbols))

	for _, symbol := range symbols {
		// Get confidence (default to 0.5 if not provided)
		confidence := 0.5
		if conf, hasConf := confidences[symbol]; hasConf {
			confidence = conf
		}

		optimalSize, err := ks.CalculateOptimalSizeForSymbol(
			symbol,
			expectedReturns,
			covMatrix,
			symbols,
			confidence,
			regimeScore,
		)
		if err != nil {
			ks.log.Warn().
				Str("symbol", symbol).
				Err(err).
				Msg("Failed to calculate Kelly size, using min size")
			optimalSize = ks.minPositionSize
		}

		result[symbol] = optimalSize
	}

	return result, nil
}
