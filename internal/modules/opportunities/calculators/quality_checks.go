package calculators

import (
	"math"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/quantum"
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
// Accepts ISIN as PRIMARY identifier for efficient O(1) lookups
func CheckQualityGates(
	ctx *domain.OpportunityContext,
	isin string,
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

	// Get scores from context (ISIN-based lookups - O(1))
	fundamentalsScore := GetScoreFromContext(ctx, isin, ctx.FundamentalsScores)
	longTermScore := GetScoreFromContext(ctx, isin, ctx.LongTermScores)
	cagr := GetScoreFromContext(ctx, isin, ctx.CAGRs)

	// Quality Gate Check (for new positions) - Multi-Path System
	if isNewPosition {
		// Default relaxed thresholds for Path 1 (no adaptive support in score-based fallback)
		fundamentalsThreshold := 0.55 // Relaxed from 0.6
		longTermThreshold := 0.45     // Relaxed from 0.5

		// Extract additional scores for multi-path evaluation
		opportunityScore := GetScoreFromContext(ctx, isin, ctx.OpportunityScores)
		dividendScore := 0.0 // DividendScores map removed - not used
		volatility := GetScoreFromContext(ctx, isin, ctx.Volatility)

		// Get dividend yield from securities
		dividendYield := 0.0
		// Look up security by ISIN - O(1) lookup
		if sec, ok := ctx.StocksByISIN[isin]; ok {
			// Dividend yield would come from security if it had that field
			// Currently domain.Security doesn't have DividendYield field
			_ = sec // Use sec if DividendYield field is added later
			dividendYield = 0.0
		}

		// Get Sharpe and Sortino ratios (approximations from available data)
		sharpe := 0.0
		sortino := 0.0
		if cagr > 0 && volatility > 0 {
			// Approximate Sharpe: (CAGR - RiskFreeRate) / Volatility
			riskFreeRate := 0.04 // Assume 4% risk-free rate
			sharpe = (cagr - riskFreeRate) / volatility
			// Approximate Sortino: similar to Sharpe but typically ~1.5x higher
			sortino = sharpe * 1.5
		}

		// Evaluate all 7 paths - ANY path passes
		passes := false
		passedPath := ""

		// Path 1: Balanced (no adaptive in score-based fallback)
		if fundamentalsScore > 0 && longTermScore > 0 {
			if evaluatePath1Balanced(fundamentalsScore, longTermScore, fundamentalsThreshold, longTermThreshold) {
				passes = true
				passedPath = "balanced"
			}
		}

		// Path 2: Exceptional Excellence
		if !passes && fundamentalsScore > 0 && longTermScore > 0 {
			if evaluatePath2ExceptionalExcellence(fundamentalsScore, longTermScore) {
				passes = true
				passedPath = "exceptional_excellence"
			}
		}

		// Path 3: Quality Value Play
		if !passes && fundamentalsScore > 0 && opportunityScore > 0 && longTermScore > 0 {
			if evaluatePath3QualityValuePlay(fundamentalsScore, opportunityScore, longTermScore) {
				passes = true
				passedPath = "quality_value"
			}
		}

		// Path 4: Dividend Income Play
		if !passes && fundamentalsScore > 0 && dividendScore > 0 && dividendYield > 0 {
			if evaluatePath4DividendIncomePlay(fundamentalsScore, dividendScore, dividendYield) {
				passes = true
				passedPath = "dividend_income"
			}
		}

		// Path 5: Risk-Adjusted Excellence
		if !passes && longTermScore > 0 && volatility > 0 {
			if evaluatePath5RiskAdjustedExcellence(longTermScore, sharpe, sortino, volatility) {
				passes = true
				passedPath = "risk_adjusted"
			}
		}

		// Path 6: Composite Minimum
		if !passes && fundamentalsScore > 0 && longTermScore > 0 {
			if evaluatePath6CompositeMinimum(fundamentalsScore, longTermScore) {
				passes = true
				passedPath = "composite"
			}
		}

		// Path 7: Growth Opportunity
		if !passes && cagr > 0 && fundamentalsScore > 0 && volatility > 0 {
			if evaluatePath7GrowthOpportunity(cagr, fundamentalsScore, volatility) {
				passes = true
				passedPath = "growth"
			}
		}

		// Set result based on whether any path passed
		if passes {
			result.PassesQualityGate = true
			result.QualityGateReason = passedPath // Just the path name, cleaner
		} else {
			// Check if we have minimum data to evaluate
			if fundamentalsScore > 0 || longTermScore > 0 || cagr > 0 {
				result.PassesQualityGate = false
				result.QualityGateReason = "quality_gate_fail_all_paths"
			} else {
				// If no scores available, be conservative: fail quality gate
				result.PassesQualityGate = false
				result.QualityGateReason = "quality_gate_unknown"
			}
		}
	}

	// Value Trap Detection (Classical + Quantum)
	// Logic from tag_assigner.go: cheap but declining
	// Must be cheap first (P/E 20%+ below market), then check declining quality
	peRatio := GetScoreFromContext(ctx, isin, ctx.PERatios)
	if peRatio > 0 && ctx.MarketAvgPE > 0 {
		peVsMarket := (peRatio - ctx.MarketAvgPE) / ctx.MarketAvgPE

		// Must be cheap first (20%+ below market)
		if peVsMarket < -0.20 {
			// Get momentum and volatility (optional)
			momentumScore := GetScoreFromContext(ctx, isin, ctx.MomentumScores)
			volatility := GetScoreFromContext(ctx, isin, ctx.Volatility)

			// Classical value trap detection
			// Check declining quality: poor fundamentals OR poor long-term OR negative momentum OR high volatility
			if fundamentalsScore < 0.55 || longTermScore < 0.45 {
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
		opportunityScore := GetScoreFromContext(ctx, isin, ctx.OpportunityScores)
		// Don't fall back to total score - it's not a good proxy for opportunity
		// If opportunity score is not available, skip value trap detection for this security

		if opportunityScore > 0.7 {
			// High opportunity but low quality = potential value trap
			if fundamentalsScore > 0 && longTermScore > 0 {
				if fundamentalsScore < 0.55 || longTermScore < 0.45 {
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
	// Logic from tag_assigner.go: High CAGR (>15%) with poor risk metrics
	// Note: We don't have direct access to Sharpe/Sortino in context, so we use a simplified check
	// High CAGR with low quality = potential bubble
	if cagr > 0.15 { // 15% for 11% target (1.36x target, aligned with tag_assigner)
		if fundamentalsScore > 0 && fundamentalsScore < 0.55 {
			// High CAGR but poor fundamentals = bubble risk (aligned with tag_assigner.go line 464)
			result.IsBubbleRisk = true
		}
	}

	return result
}

// GetScoreFromContext safely retrieves a score from context maps by ISIN
// Exported for use in calculators that need direct score access
func GetScoreFromContext(ctx *domain.OpportunityContext, isin string, scoreMap map[string]float64) float64 {
	if scoreMap == nil || isin == "" {
		return 0.0
	}

	// Direct ISIN lookup - O(1) instead of O(n) iteration
	if score, hasScore := scoreMap[isin]; hasScore {
		return score
	}

	return 0.0
}

// ============================================================================
// MULTI-PATH QUALITY GATE HELPERS
// These match the logic in tag_assigner.go for consistency when tags disabled
// ============================================================================

// evaluatePath1Balanced checks balanced path with adaptive thresholds
func evaluatePath1Balanced(fundamentals, longTerm, fundamentalsThreshold, longTermThreshold float64) bool {
	return fundamentals >= fundamentalsThreshold && longTerm >= longTermThreshold
}

// evaluatePath2ExceptionalExcellence checks for 75%+ in either dimension
func evaluatePath2ExceptionalExcellence(fundamentals, longTerm float64) bool {
	return fundamentals >= 0.75 || longTerm >= 0.75
}

// evaluatePath3QualityValuePlay checks quality value play path
func evaluatePath3QualityValuePlay(fundamentals, opportunity, longTerm float64) bool {
	return fundamentals >= 0.60 && opportunity >= 0.65 && longTerm >= 0.30
}

// evaluatePath4DividendIncomePlay checks dividend income play path
func evaluatePath4DividendIncomePlay(fundamentals, dividendScore, dividendYield float64) bool {
	return fundamentals >= 0.55 && dividendScore >= 0.65 && dividendYield >= 0.035
}

// evaluatePath5RiskAdjustedExcellence checks risk-adjusted excellence path
func evaluatePath5RiskAdjustedExcellence(longTerm, sharpe, sortino, volatility float64) bool {
	return longTerm >= 0.55 && (sharpe >= 0.9 || sortino >= 0.9) && volatility <= 0.35
}

// evaluatePath6CompositeMinimum checks composite minimum path
func evaluatePath6CompositeMinimum(fundamentals, longTerm float64) bool {
	compositeScore := 0.6*fundamentals + 0.4*longTerm
	return compositeScore >= 0.52 && fundamentals >= 0.45
}

// evaluatePath7GrowthOpportunity checks growth opportunity path
func evaluatePath7GrowthOpportunity(cagrRaw, fundamentals, volatility float64) bool {
	return cagrRaw >= 0.13 && fundamentals >= 0.50 && volatility <= 0.40
}
