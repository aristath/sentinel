package calculators

import (
	"math"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
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
	stabilityScore := GetScoreFromContext(ctx, isin, ctx.StabilityScores)
	longTermScore := GetScoreFromContext(ctx, isin, ctx.LongTermScores)
	cagr := GetScoreFromContext(ctx, isin, ctx.CAGRs)

	// Quality Gate Check (for new positions) - Multi-Path System
	if isNewPosition {
		// Default relaxed thresholds for Path 1 (no adaptive support in score-based fallback)
		stabilityThreshold := 0.55 // Relaxed from 0.6
		longTermThreshold := 0.45  // Relaxed from 0.5

		// Extract additional scores for multi-path evaluation
		opportunityScore := GetScoreFromContext(ctx, isin, ctx.OpportunityScores)
		dividendScore := 0.0 // DividendScores map removed - not used
		volatility := GetScoreFromContext(ctx, isin, ctx.Volatility)

		// Get dividend yield from securities
		dividendYield := 0.0
		// Look up security by ISIN - O(1) lookup
		if sec, ok := ctx.StocksByISIN[isin]; ok {
			// Dividend yield would come from security if it had that field
			// Currently universe.Security doesn't have DividendYield field
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
		if stabilityScore > 0 && longTermScore > 0 {
			if evaluatePath1Balanced(stabilityScore, longTermScore, stabilityThreshold, longTermThreshold) {
				passes = true
				passedPath = "balanced"
			}
		}

		// Path 2: Exceptional Excellence
		if !passes && stabilityScore > 0 && longTermScore > 0 {
			if evaluatePath2ExceptionalExcellence(stabilityScore, longTermScore) {
				passes = true
				passedPath = "exceptional_excellence"
			}
		}

		// Path 3: Quality Value Play
		if !passes && stabilityScore > 0 && opportunityScore > 0 && longTermScore > 0 {
			if evaluatePath3QualityValuePlay(stabilityScore, opportunityScore, longTermScore) {
				passes = true
				passedPath = "quality_value"
			}
		}

		// Path 4: Dividend Income Play
		if !passes && stabilityScore > 0 && dividendScore > 0 && dividendYield > 0 {
			if evaluatePath4DividendIncomePlay(stabilityScore, dividendScore, dividendYield) {
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
		if !passes && stabilityScore > 0 && longTermScore > 0 {
			if evaluatePath6CompositeMinimum(stabilityScore, longTermScore) {
				passes = true
				passedPath = "composite"
			}
		}

		// Path 7: Growth Opportunity
		if !passes && cagr > 0 && stabilityScore > 0 && volatility > 0 {
			if evaluatePath7GrowthOpportunity(cagr, stabilityScore, volatility) {
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
			if stabilityScore > 0 || longTermScore > 0 || cagr > 0 {
				result.PassesQualityGate = false
				result.QualityGateReason = "quality_gate_fail_all_paths"
			} else {
				// If no scores available, be conservative: fail quality gate
				result.PassesQualityGate = false
				result.QualityGateReason = "quality_gate_unknown"
			}
		}
	}

	// Value Trap Detection
	// Uses opportunity score (based on 52-week high distance) + quality scores
	// P/E-based detection removed - no external data sources available
	opportunityScore := GetScoreFromContext(ctx, isin, ctx.OpportunityScores)

	// High opportunity (cheap based on 52-week high) but low quality = potential value trap
	if opportunityScore > 0.7 {
		if stabilityScore > 0 && longTermScore > 0 {
			if stabilityScore < 0.55 || longTermScore < 0.45 {
				result.IsValueTrap = true
				result.IsEnsembleValueTrap = true
			}

			// Also check momentum and volatility if available
			momentumScore := GetScoreFromContext(ctx, isin, ctx.MomentumScores)
			volatility := GetScoreFromContext(ctx, isin, ctx.Volatility)
			if momentumScore < -0.05 || volatility > 0.35 {
				result.IsValueTrap = true
				result.IsEnsembleValueTrap = true
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
		if stabilityScore > 0 && stabilityScore < 0.55 {
			// High CAGR but poor stability = bubble risk (aligned with tag_assigner.go line 464)
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
func evaluatePath1Balanced(stability, longTerm, stabilityThreshold, longTermThreshold float64) bool {
	return stability >= stabilityThreshold && longTerm >= longTermThreshold
}

// evaluatePath2ExceptionalExcellence checks for 75%+ in either dimension
func evaluatePath2ExceptionalExcellence(stability, longTerm float64) bool {
	return stability >= 0.75 || longTerm >= 0.75
}

// evaluatePath3QualityValuePlay checks quality value play path
func evaluatePath3QualityValuePlay(stability, opportunity, longTerm float64) bool {
	return stability >= 0.60 && opportunity >= 0.65 && longTerm >= 0.30
}

// evaluatePath4DividendIncomePlay checks dividend income play path
func evaluatePath4DividendIncomePlay(stability, dividendScore, dividendYield float64) bool {
	return stability >= 0.55 && dividendScore >= 0.65 && dividendYield >= 0.035
}

// evaluatePath5RiskAdjustedExcellence checks risk-adjusted excellence path
func evaluatePath5RiskAdjustedExcellence(longTerm, sharpe, sortino, volatility float64) bool {
	return longTerm >= 0.55 && (sharpe >= 0.9 || sortino >= 0.9) && volatility <= 0.35
}

// evaluatePath6CompositeMinimum checks composite minimum path
func evaluatePath6CompositeMinimum(stability, longTerm float64) bool {
	compositeScore := 0.6*stability + 0.4*longTerm
	return compositeScore >= 0.52 && stability >= 0.45
}

// evaluatePath7GrowthOpportunity checks growth opportunity path
func evaluatePath7GrowthOpportunity(cagrRaw, stability, volatility float64) bool {
	return cagrRaw >= 0.13 && stability >= 0.50 && volatility <= 0.40
}
