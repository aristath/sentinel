package optimization

import (
	"fmt"
	"math"

	"github.com/aristath/portfolioManager/internal/modules/portfolio"
	"github.com/aristath/portfolioManager/pkg/formulas"
	"github.com/rs/zerolog"
)

// CVaRCalculator calculates Conditional Value at Risk for portfolios and securities.
type CVaRCalculator struct {
	riskBuilder    *RiskModelBuilder
	regimeDetector *portfolio.MarketRegimeDetector
	log            zerolog.Logger
}

// NewCVaRCalculator creates a new CVaR calculator.
func NewCVaRCalculator(
	riskBuilder *RiskModelBuilder,
	regimeDetector *portfolio.MarketRegimeDetector,
	log zerolog.Logger,
) *CVaRCalculator {
	if log.GetLevel() == zerolog.Disabled {
		log = zerolog.Nop()
	}
	return &CVaRCalculator{
		riskBuilder:    riskBuilder,
		regimeDetector: regimeDetector,
		log:            log.With().Str("component", "cvar_calculator").Logger(),
	}
}

// CalculatePortfolioCVaR calculates portfolio-level CVaR from historical returns.
func (c *CVaRCalculator) CalculatePortfolioCVaR(
	weights map[string]float64,
	returns map[string][]float64,
	confidence float64,
) float64 {
	return formulas.CalculatePortfolioCVaR(weights, returns, confidence)
}

// CalculateSecurityCVaR calculates CVaR for a single security.
func (c *CVaRCalculator) CalculateSecurityCVaR(returns []float64, confidence float64) float64 {
	return formulas.CalculateCVaR(returns, confidence)
}

// CalculateFromCovariance calculates CVaR using Monte Carlo simulation from covariance matrix.
func (c *CVaRCalculator) CalculateFromCovariance(
	covMatrix [][]float64,
	expectedReturns map[string]float64,
	weights map[string]float64,
	symbols []string,
	numSimulations int,
	confidence float64,
) float64 {
	return formulas.MonteCarloCVaRWithWeights(
		covMatrix,
		expectedReturns,
		weights,
		symbols,
		numSimulations,
		confidence,
	)
}

// ApplyRegimeAdjustment applies regime-based adjustment to CVaR.
// In bear markets, CVaR limits are tightened (more conservative).
func (c *CVaRCalculator) ApplyRegimeAdjustment(cvar float64, regimeScore float64) float64 {
	// Only adjust in bear markets (regimeScore < 0)
	if regimeScore >= 0 {
		return cvar
	}

	// Increase CVaR (make it more negative/worse) in bear markets
	// Adjustment factor: 1.0 (no change) to 1.3 (30% worse) as regime goes 0 to -1.0
	adjustmentFactor := 1.0 + 0.3*math.Abs(regimeScore)

	// Clamp adjustment factor to [1.0, 1.3]
	if adjustmentFactor > 1.3 {
		adjustmentFactor = 1.3
	}

	return cvar * adjustmentFactor
}

// CalculatePortfolioCVaRWithRegime calculates portfolio CVaR with regime adjustment.
func (c *CVaRCalculator) CalculatePortfolioCVaRWithRegime(
	weights map[string]float64,
	returns map[string][]float64,
	confidence float64,
	regimeScore float64,
) float64 {
	baseCVaR := c.CalculatePortfolioCVaR(weights, returns, confidence)
	return c.ApplyRegimeAdjustment(baseCVaR, regimeScore)
}

// GetSecurityCVaRContributions calculates individual security contributions to portfolio CVaR.
func (c *CVaRCalculator) GetSecurityCVaRContributions(
	weights map[string]float64,
	returns map[string][]float64,
	confidence float64,
) (map[string]float64, error) {
	if len(weights) == 0 {
		return nil, fmt.Errorf("weights cannot be empty")
	}

	contributions := make(map[string]float64, len(weights))

	// Calculate CVaR for each security
	for symbol, weight := range weights {
		securityReturns, hasReturns := returns[symbol]
		if !hasReturns || len(securityReturns) == 0 {
			continue
		}

		securityCVaR := c.CalculateSecurityCVaR(securityReturns, confidence)
		// Contribution = weight * security CVaR
		contributions[symbol] = weight * securityCVaR
	}

	return contributions, nil
}
