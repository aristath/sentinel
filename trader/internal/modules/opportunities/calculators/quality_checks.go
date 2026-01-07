package calculators

import (
	"math"

	"github.com/aristath/portfolioManager/internal/modules/planning/domain"
	"github.com/aristath/portfolioManager/internal/modules/quantum"
)

// QualityCheckResult contains the result of quality checks
type QualityCheckResult struct {
	PassesQualityGate  bool
	IsValueTrap        bool
	IsBubbleRisk       bool
	BelowMinimumReturn bool
	QualityGateReason  string

	// Quantum detection results
	QuantumValueTrapProb float64 // Quantum probability (0-1)
	IsQuantumValueTrap   bool    // Quantum detected trap (>0.7)
	IsQuantumWarning     bool    // Quantum early warning (0.5-0.7)
	IsEnsembleValueTrap  bool    // Ensemble decision (classical OR quantum)
}

// CheckQualityGates performs quality gate checks using scores when tags are disabled.
// This ensures financial theories (quality gates, value trap detection, bubble detection)
// continue to work even when tag filtering is disabled.
func CheckQualityGates(
	ctx *domain.OpportunityContext,
	symbol string,
	isNewPosition bool,
	config *domain.PlannerConfiguration,
) QualityCheckResult {
	result := QualityCheckResult{
		PassesQualityGate:    true, // Default: pass if we can't check
		IsValueTrap:          false,
		IsBubbleRisk:         false,
		BelowMinimumReturn:   false,
		QuantumValueTrapProb: 0.0,
		IsQuantumValueTrap:   false,
		IsQuantumWarning:     false,
		IsEnsembleValueTrap:  false,
	}

	// If tag filtering is enabled, we rely on tags (checked elsewhere)
	// This function is only for when tags are disabled
	if config != nil && config.EnableTagFiltering {
		return result // Tags will be checked elsewhere
	}

	// Get scores from context
	fundamentalsScore := GetScoreFromContext(ctx, symbol, ctx.FundamentalsScores)
	longTermScore := GetScoreFromContext(ctx, symbol, ctx.LongTermScores)
	cagr := GetScoreFromContext(ctx, symbol, ctx.CAGRs)

	// Quality Gate Check (for new positions)
	if isNewPosition {
		// Default thresholds (same as tag_assigner.go)
		fundamentalsThreshold := 0.6
		longTermThreshold := 0.5

		// Check if we have both scores
		if fundamentalsScore > 0 && longTermScore > 0 {
			if fundamentalsScore >= fundamentalsThreshold && longTermScore >= longTermThreshold {
				result.PassesQualityGate = true
				result.QualityGateReason = "quality_gate_pass"
			} else {
				result.PassesQualityGate = false
				result.QualityGateReason = "quality_gate_fail"
			}
		} else {
			// If scores not available, be conservative: fail quality gate
			result.PassesQualityGate = false
			result.QualityGateReason = "quality_gate_unknown"
		}
	}

	// Value Trap Detection (Classical + Quantum)
	// Logic from tag_assigner.go: cheap but declining
	// Must be cheap first (P/E 20%+ below market), then check declining quality
	peRatio := GetScoreFromContext(ctx, symbol, ctx.PERatios)
	if peRatio > 0 && ctx.MarketAvgPE > 0 {
		peVsMarket := (peRatio - ctx.MarketAvgPE) / ctx.MarketAvgPE

		// Must be cheap first (20%+ below market)
		if peVsMarket < -0.20 {
			// Get momentum and volatility (optional)
			momentumScore := GetScoreFromContext(ctx, symbol, ctx.MomentumScores)
			volatility := GetScoreFromContext(ctx, symbol, ctx.Volatility)

			// Classical value trap detection
			// Check declining quality: poor fundamentals OR poor long-term OR negative momentum OR high volatility
			if fundamentalsScore < 0.6 || longTermScore < 0.5 {
				result.IsValueTrap = true
			}
			// Also check momentum and volatility if available
			if momentumScore < -0.05 || volatility > 0.35 {
				result.IsValueTrap = true
			}

			// Quantum value trap detection (only if regime score is available)
			// Note: Regime score can legitimately be 0.0 (neutral), so we check if it was populated
			// by checking if it's within valid range [-1, 1] and not the default uninitialized value
			// We use a sentinel value check: if RegimeScore is exactly 0.0, we still allow quantum detection
			// because 0.0 is a valid neutral regime score. The check here is mainly to avoid running
			// quantum detection when the score hasn't been populated at all.
			// Since we can't distinguish uninitialized 0.0 from neutral 0.0, we always run quantum detection
			// if we have the other required data (P/E and market avg P/E are already checked above)
			if ctx.RegimeScore >= -1.0 && ctx.RegimeScore <= 1.0 {
				quantumCalc := quantum.NewQuantumProbabilityCalculator()
				// Use defaults if momentum/volatility not available
				momentumForQuantum := momentumScore
				volatilityForQuantum := volatility
				// momentumForQuantum defaults to 0.0 (neutral) if not available, which is already the case
				if volatilityForQuantum == 0.0 {
					volatilityForQuantum = 0.20 // Default moderate volatility
				}

				result.QuantumValueTrapProb = quantumCalc.CalculateValueTrapProbability(
					peVsMarket,
					fundamentalsScore,
					longTermScore,
					momentumForQuantum,
					volatilityForQuantum,
					ctx.RegimeScore,
				)

				// Quantum decision logic (matches tag_assigner.go)
				if result.QuantumValueTrapProb > 0.7 {
					result.IsQuantumValueTrap = true
					result.IsEnsembleValueTrap = true
				} else if result.QuantumValueTrapProb > 0.5 {
					result.IsQuantumWarning = true
				}
			}

			// Ensemble decision: classical OR quantum
			if result.IsValueTrap || result.IsQuantumValueTrap {
				result.IsEnsembleValueTrap = true
			}
		}
	} else {
		// Fallback: If P/E data not available, use opportunity score as proxy
		// This is less accurate but better than nothing
		opportunityScore := GetScoreFromContext(ctx, symbol, ctx.OpportunityScores)
		// Don't fall back to total score - it's not a good proxy for opportunity
		// If opportunity score is not available, skip value trap detection for this security

		if opportunityScore > 0.7 {
			// High opportunity but low quality = potential value trap
			if fundamentalsScore > 0 && longTermScore > 0 {
				if fundamentalsScore < 0.6 || longTermScore < 0.5 {
					result.IsValueTrap = true
					result.IsEnsembleValueTrap = true
				}
			}
		}
	}

	// Below Minimum Return Check
	// Logic from tag_assigner.go: absoluteMinCAGR = max(0.06, targetReturn * 0.50)
	if cagr > 0 {
		targetReturn := ctx.TargetReturn
		if targetReturn == 0 {
			targetReturn = 0.11 // Default 11%
		}
		absoluteMinCAGR := math.Max(0.06, targetReturn*0.50)
		if cagr < absoluteMinCAGR {
			result.BelowMinimumReturn = true
		}
	}

	// Bubble Risk Detection
	// Logic from tag_assigner.go: High CAGR (>16.5%) with poor risk metrics
	// Note: We don't have direct access to Sharpe/Sortino in context, so we use a simplified check
	// High CAGR with low quality = potential bubble
	if cagr > 0.165 { // 16.5% for 11% target (1.5x target)
		if fundamentalsScore > 0 && fundamentalsScore < 0.6 {
			// High CAGR but poor fundamentals = bubble risk
			result.IsBubbleRisk = true
		}
	}

	return result
}

// GetScoreFromContext safely retrieves a score from context maps
// Tries ISIN first, then symbol as fallback
// Exported for use in calculators that need direct score access
func GetScoreFromContext(ctx *domain.OpportunityContext, symbol string, scoreMap map[string]float64) float64 {
	if scoreMap == nil {
		return 0.0
	}

	// Try to get security to find ISIN
	security, ok := ctx.StocksBySymbol[symbol]
	if ok && security.ISIN != "" {
		if score, hasScore := scoreMap[security.ISIN]; hasScore {
			return score
		}
	}

	// Fallback to symbol
	if score, hasScore := scoreMap[symbol]; hasScore {
		return score
	}

	return 0.0
}
