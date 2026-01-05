package evaluation

import (
	"math"
)

// Scoring weight constants
const (
	// Diversification component weights
	GeoWeight      = 0.40 // Geographic diversification weight
	IndustryWeight = 0.30 // Industry diversification weight
	QualityWeight  = 0.30 // Quality/dividend score weight

	// Deviation scoring scale
	DeviationScale = 0.3 // Maximum deviation for 0 score (30%)

	// Quality scoring weights
	SecurityQualityWeight = 0.6 // Weight for security quality score
	DividendYieldWeight   = 0.4 // Weight for dividend yield
)

// CalculateTransactionCost calculates total transaction cost for a sequence.
//
// Args:
//   - sequence: List of actions in the sequence
//   - transactionCostFixed: Fixed cost per trade in EUR
//   - transactionCostPercent: Variable cost as fraction
//
// Returns:
//   - Total transaction cost in EUR
func CalculateTransactionCost(
	sequence []ActionCandidate,
	transactionCostFixed float64,
	transactionCostPercent float64,
) float64 {
	return CalculateTransactionCostEnhanced(
		sequence,
		transactionCostFixed,
		transactionCostPercent,
		0.001,  // Default spread cost: 0.1%
		0.0015, // Default slippage: 0.15%
		0.0,    // Market impact: disabled by default
	)
}

// CalculateTransactionCostEnhanced calculates total transaction cost with spread, slippage, and market impact.
//
// Args:
//   - sequence: List of actions in the sequence
//   - transactionCostFixed: Fixed cost per trade in EUR
//   - transactionCostPercent: Variable cost as fraction
//   - spreadCostPercent: Bid-ask spread cost as fraction (default 0.1%)
//   - slippagePercent: Slippage cost as fraction (default 0.15%)
//   - marketImpactPercent: Market impact cost as fraction (default 0.0, disabled)
//
// Returns:
//   - Total transaction cost in EUR
func CalculateTransactionCostEnhanced(
	sequence []ActionCandidate,
	transactionCostFixed float64,
	transactionCostPercent float64,
	spreadCostPercent float64,
	slippagePercent float64,
	marketImpactPercent float64,
) float64 {
	totalCost := 0.0
	for _, action := range sequence {
		// Base costs (fixed + variable)
		fixedCost := transactionCostFixed
		variableCost := math.Abs(action.ValueEUR) * transactionCostPercent

		// Spread cost (bid-ask spread)
		spreadCost := math.Abs(action.ValueEUR) * spreadCostPercent

		// Slippage (price movement between order and execution)
		slippageCost := math.Abs(action.ValueEUR) * slippagePercent

		// Market impact (for large trades)
		impactCost := math.Abs(action.ValueEUR) * marketImpactPercent

		// Total cost for this action
		tradeCost := fixedCost + variableCost + spreadCost + slippageCost + impactCost
		totalCost += tradeCost
	}
	return totalCost
}

// CalculateDiversificationScore calculates diversification score for a portfolio.
//
// This is a simplified version that calculates:
// - Geographic diversification (40%): How close to target country allocations
// - Industry diversification (30%): How close to target industry allocations
// - Quality/dividend diversification (30%): Weighted average of position quality
//
// Returns score on 0-1 scale (0=poor diversification, 1=perfect diversification)
func CalculateDiversificationScore(portfolioContext PortfolioContext) float64 {
	totalValue := portfolioContext.TotalValue
	if totalValue <= 0 {
		return 0.5 // Neutral score for empty portfolio
	}

	// Geographic diversification (40%)
	geoDivScore := calculateGeoDiversification(portfolioContext, totalValue)

	// Industry diversification (30%)
	indDivScore := calculateIndustryDiversification(portfolioContext, totalValue)

	// Quality/dividend score (30%)
	qualityScore := calculateQualityScore(portfolioContext, totalValue)

	// Combined score
	diversificationScore := geoDivScore*GeoWeight + indDivScore*IndustryWeight + qualityScore*QualityWeight

	return math.Min(1.0, diversificationScore)
}

// calculateGeoDiversification calculates geographic diversification score
func calculateGeoDiversification(portfolioContext PortfolioContext, totalValue float64) float64 {
	if portfolioContext.SecurityCountries == nil || len(portfolioContext.CountryWeights) == 0 {
		return 0.5 // Neutral if no country data
	}

	// Map individual countries to groups and aggregate by group
	countryToGroup := portfolioContext.CountryToGroup
	if countryToGroup == nil {
		countryToGroup = make(map[string]string)
	}

	groupValues := make(map[string]float64)
	for symbol, value := range portfolioContext.Positions {
		country, hasCountry := portfolioContext.SecurityCountries[symbol]
		if !hasCountry {
			country = "OTHER"
		}

		// Map to group
		group, hasGroup := countryToGroup[country]
		if !hasGroup {
			group = "OTHER"
		}

		groupValues[group] += value
	}

	// Calculate deviations from target weights
	deviations := make([]float64, 0, len(portfolioContext.CountryWeights))
	for group, targetWeight := range portfolioContext.CountryWeights {
		currentValue := groupValues[group]
		currentPct := currentValue / totalValue
		deviation := math.Abs(currentPct - targetWeight)
		deviations = append(deviations, deviation)
	}

	if len(deviations) == 0 {
		return 0.5
	}

	// Average deviation
	avgDeviation := sum(deviations) / float64(len(deviations))

	// Convert deviation to score (lower deviation = higher score)
	// Perfect alignment (0 deviation) = 1.0
	// 30% average deviation = 0.0
	geoScore := math.Max(0, 1.0-avgDeviation/DeviationScale)

	return geoScore
}

// calculateIndustryDiversification calculates industry diversification score
func calculateIndustryDiversification(portfolioContext PortfolioContext, totalValue float64) float64 {
	if portfolioContext.SecurityIndustries == nil || len(portfolioContext.IndustryWeights) == 0 {
		return 0.5 // Neutral if no industry data
	}

	// Map individual industries to groups and aggregate by group
	industryToGroup := portfolioContext.IndustryToGroup
	if industryToGroup == nil {
		industryToGroup = make(map[string]string)
	}

	groupValues := make(map[string]float64)
	for symbol, value := range portfolioContext.Positions {
		industry, hasIndustry := portfolioContext.SecurityIndustries[symbol]
		if !hasIndustry {
			industry = "OTHER"
		}

		// Map to group
		group, hasGroup := industryToGroup[industry]
		if !hasGroup {
			group = "OTHER"
		}

		groupValues[group] += value
	}

	// Calculate deviations from target weights
	deviations := make([]float64, 0, len(portfolioContext.IndustryWeights))
	for group, targetWeight := range portfolioContext.IndustryWeights {
		currentValue := groupValues[group]
		currentPct := currentValue / totalValue
		deviation := math.Abs(currentPct - targetWeight)
		deviations = append(deviations, deviation)
	}

	if len(deviations) == 0 {
		return 0.5
	}

	// Average deviation
	avgDeviation := sum(deviations) / float64(len(deviations))

	// Convert deviation to score (lower deviation = higher score)
	indScore := math.Max(0, 1.0-avgDeviation/DeviationScale)

	return indScore
}

// calculateQualityScore calculates weighted quality and dividend score
func calculateQualityScore(portfolioContext PortfolioContext, totalValue float64) float64 {
	if portfolioContext.SecurityScores == nil && portfolioContext.SecurityDividends == nil {
		return 0.5 // Neutral if no quality/dividend data
	}

	weightedQuality := 0.0
	weightedDividend := 0.0
	hasQuality := false
	hasDividend := false

	for symbol, value := range portfolioContext.Positions {
		weight := value / totalValue

		// Add quality score contribution
		if portfolioContext.SecurityScores != nil {
			if quality, hasQ := portfolioContext.SecurityScores[symbol]; hasQ {
				weightedQuality += quality * weight
				hasQuality = true
			}
		}

		// Add dividend contribution
		if portfolioContext.SecurityDividends != nil {
			if dividend, hasD := portfolioContext.SecurityDividends[symbol]; hasD {
				weightedDividend += dividend * weight
				hasDividend = true
			}
		}
	}

	// Combine quality and dividend scores
	qualityScore := 0.5
	if hasQuality && hasDividend {
		// Quality is 0-1, dividend is yield (normalize to 0-1 by capping at 10%)
		normalizedDividend := math.Min(1.0, weightedDividend*10)
		qualityScore = weightedQuality*SecurityQualityWeight + normalizedDividend*DividendYieldWeight
	} else if hasQuality {
		qualityScore = weightedQuality
	} else if hasDividend {
		// Normalize dividend yield to 0-1 scale
		qualityScore = math.Min(1.0, weightedDividend*10)
	}

	return qualityScore
}

// EvaluateEndState evaluates the end state of a portfolio after executing a sequence.
//
// This is the core single-objective evaluation function that:
// 1. Calculates diversification score
// 2. Calculates transaction cost penalty
// 3. Returns final score (0-1 scale)
//
// DEPRECATED: Use EvaluateEndStateEnhanced for multi-objective evaluation.
func EvaluateEndState(
	endContext PortfolioContext,
	sequence []ActionCandidate,
	transactionCostFixed float64,
	transactionCostPercent float64,
	costPenaltyFactor float64,
) float64 {
	return EvaluateEndStateEnhanced(endContext, sequence, transactionCostFixed, transactionCostPercent, costPenaltyFactor)
}

// EvaluateEndStateEnhanced evaluates the end state with multi-objective scoring.
//
// This enhanced evaluation function combines:
// 1. Diversification Score (30%): Geographic, industry, quality diversification
// 2. Optimizer Alignment (25%): How close portfolio is to optimizer target allocations
// 3. Expected Return Score (25%): Growth (CAGR) + dividends (total return)
// 4. Risk-Adjusted Return Score (10%): Portfolio-level risk metrics
// 5. Quality Score (10%): Weighted average of security quality scores
//
// Args:
//   - endContext: Final portfolio state after sequence execution
//   - sequence: The action sequence that was executed
//   - transactionCostFixed: Fixed cost per trade (EUR)
//   - transactionCostPercent: Variable cost as fraction
//   - costPenaltyFactor: Penalty factor for transaction costs (0.0 = no penalty)
//
// Returns:
//   - Final score (0-1 scale)
func EvaluateEndStateEnhanced(
	endContext PortfolioContext,
	sequence []ActionCandidate,
	transactionCostFixed float64,
	transactionCostPercent float64,
	costPenaltyFactor float64,
) float64 {
	// 1. Diversification Score (30%) - KEEP IMPORTANT
	divScore := CalculateDiversificationScore(endContext)

	// 2. Optimizer Alignment (25%) - how close portfolio is to optimizer targets
	alignmentScore := calculateOptimizerAlignment(endContext)

	// 3. Expected Return Score (25%) - accounts for growth + dividends
	expectedReturnScore := calculateExpectedReturnScore(endContext)

	// 4. Risk-Adjusted Return Score (10%) - portfolio-level Sharpe/Sortino
	riskAdjustedScore := calculateRiskAdjustedScore(endContext)

	// 5. Quality Score (10%) - weighted average of security quality scores
	qualityScore := calculatePortfolioQualityScore(endContext)

	// Combined score (all components important)
	endScore := divScore*0.30 +
		alignmentScore*0.25 +
		expectedReturnScore*0.25 +
		riskAdjustedScore*0.10 +
		qualityScore*0.10

	// Transaction cost penalty (subtractive)
	totalCost := CalculateTransactionCost(sequence, transactionCostFixed, transactionCostPercent)
	if costPenaltyFactor > 0.0 && endContext.TotalValue > 0 {
		costPenalty := (totalCost / endContext.TotalValue) * costPenaltyFactor
		endScore = math.Max(0.0, endScore-costPenalty)
	}

	return math.Min(1.0, endScore)
}

// EvaluateEndStateWithRegime evaluates the end state with regime-based risk adjustments.
//
// This function wraps EvaluateEndStateEnhanced and applies regime-specific adjustments:
// - Bear market: Reduce risk, favor quality, penalize volatility
// - Bull market: Allow more growth, slight boost for growth positions
// - Sideways: Neutral, favor value opportunities
//
// Args:
//   - endContext: Final portfolio state after sequence execution
//   - sequence: The action sequence that was executed
//   - regime: Current market regime (bull, bear, or sideways)
//   - transactionCostFixed: Fixed cost per trade (EUR)
//   - transactionCostPercent: Variable cost as fraction
//   - costPenaltyFactor: Penalty factor for transaction costs (0.0 = no penalty)
//
// Returns:
//   - Final score (0-1 scale) with regime adjustments
func EvaluateEndStateWithRegime(
	endContext PortfolioContext,
	sequence []ActionCandidate,
	regime string, // "bull", "bear", or "sideways"
	transactionCostFixed float64,
	transactionCostPercent float64,
	costPenaltyFactor float64,
) float64 {
	// Base evaluation
	baseScore := EvaluateEndStateEnhanced(endContext, sequence, transactionCostFixed, transactionCostPercent, costPenaltyFactor)

	// Regime adjustments
	switch regime {
	case "bear":
		// Bear market: Reduce risk, favor quality, penalize volatility
		// Calculate volatility penalty (simplified - based on quality scores)
		volatilityPenalty := calculateVolatilityPenalty(endContext)
		baseScore = baseScore * (1.0 - volatilityPenalty*0.2) // Up to 20% penalty

		// Boost quality score
		qualityBoost := calculateQualityBoost(endContext)
		baseScore = baseScore + qualityBoost*0.1 // Up to 10% boost

	case "bull":
		// Bull market: Allow more risk, favor growth
		// Slight boost for growth positions (based on expected return)
		growthBoost := calculateGrowthBoost(endContext)
		baseScore = baseScore + growthBoost*0.05 // Up to 5% boost

	case "sideways":
		// Sideways: Neutral, favor value opportunities
		// Slight boost for value positions (based on opportunity scores)
		valueBoost := calculateValueBoost(endContext)
		baseScore = baseScore + valueBoost*0.05 // Up to 5% boost

	default:
		// Unknown regime: no adjustment
	}

	return math.Min(1.0, math.Max(0.0, baseScore))
}

// calculateVolatilityPenalty calculates a penalty factor based on portfolio volatility.
// Returns 0.0 (no penalty) to 1.0 (maximum penalty).
func calculateVolatilityPenalty(ctx PortfolioContext) float64 {
	// Simplified: Use quality scores as proxy for volatility
	// Lower quality = higher volatility risk
	if len(ctx.SecurityScores) == 0 {
		return 0.5 // Neutral if no data
	}

	totalValue := ctx.TotalValue
	if totalValue <= 0 {
		return 0.5
	}

	weightedQuality := 0.0
	for symbol, value := range ctx.Positions {
		weight := value / totalValue
		if quality, ok := ctx.SecurityScores[symbol]; ok {
			weightedQuality += quality * weight
		}
	}

	// Lower quality = higher penalty
	// Quality 0.0 = penalty 1.0, quality 1.0 = penalty 0.0
	penalty := 1.0 - weightedQuality
	return math.Max(0.0, math.Min(1.0, penalty))
}

// calculateQualityBoost calculates a boost factor based on portfolio quality.
// Returns 0.0 (no boost) to 1.0 (maximum boost).
func calculateQualityBoost(ctx PortfolioContext) float64 {
	if len(ctx.SecurityScores) == 0 {
		return 0.0
	}

	totalValue := ctx.TotalValue
	if totalValue <= 0 {
		return 0.0
	}

	weightedQuality := 0.0
	for symbol, value := range ctx.Positions {
		weight := value / totalValue
		if quality, ok := ctx.SecurityScores[symbol]; ok {
			weightedQuality += quality * weight
		}
	}

	// Higher quality = higher boost
	// Quality 0.5 = boost 0.0, quality 1.0 = boost 1.0
	boost := (weightedQuality - 0.5) * 2.0
	return math.Max(0.0, math.Min(1.0, boost))
}

// calculateGrowthBoost calculates a boost factor based on portfolio growth potential.
// Returns 0.0 (no boost) to 1.0 (maximum boost).
func calculateGrowthBoost(ctx PortfolioContext) float64 {
	// Simplified: Use expected return proxy (CAGR from security scores)
	// In a real implementation, this would use actual CAGR data
	if len(ctx.SecurityScores) == 0 {
		return 0.0
	}

	totalValue := ctx.TotalValue
	if totalValue <= 0 {
		return 0.0
	}

	weightedScore := 0.0
	for symbol, value := range ctx.Positions {
		weight := value / totalValue
		if score, ok := ctx.SecurityScores[symbol]; ok {
			weightedScore += score * weight
		}
	}

	// Higher score = higher growth potential
	// Score 0.5 = boost 0.0, score 1.0 = boost 1.0
	boost := (weightedScore - 0.5) * 2.0
	return math.Max(0.0, math.Min(1.0, boost))
}

// calculateValueBoost calculates a boost factor based on portfolio value opportunities.
// Returns 0.0 (no boost) to 1.0 (maximum boost).
func calculateValueBoost(ctx PortfolioContext) float64 {
	// Simplified: Use quality scores as proxy for value
	// In a real implementation, this would use opportunity scores or P/E ratios
	if len(ctx.SecurityScores) == 0 {
		return 0.0
	}

	totalValue := ctx.TotalValue
	if totalValue <= 0 {
		return 0.0
	}

	weightedScore := 0.0
	for symbol, value := range ctx.Positions {
		weight := value / totalValue
		if score, ok := ctx.SecurityScores[symbol]; ok {
			weightedScore += score * weight
		}
	}

	// Higher quality = better value opportunities
	// Score 0.5 = boost 0.0, score 1.0 = boost 1.0
	boost := (weightedScore - 0.5) * 2.0
	return math.Max(0.0, math.Min(1.0, boost))
}

// calculateOptimizerAlignment scores how close portfolio is to optimizer target allocations.
//
// The optimizer creates target allocations (strategy), and the planner implements them.
// This function scores how well the portfolio aligns with those targets.
//
// Algorithm:
//   - Calculates weight deviations for each security with a target
//   - Averages deviations across all targets
//   - Scores: 0 deviation = 1.0, 10% avg deviation = 0.5, 20%+ = 0.0
//
// Args:
//   - ctx: Portfolio context with current positions and optimizer targets
//
// Returns:
//   - Score from 0.0 to 1.0 based on alignment with optimizer targets
func calculateOptimizerAlignment(ctx PortfolioContext) float64 {
	totalValue := ctx.TotalValue
	if totalValue <= 0 {
		return 0.5 // Neutral score for empty portfolio
	}

	// If no optimizer targets available, return neutral score
	if len(ctx.OptimizerTargetWeights) == 0 {
		return 0.5 // No targets = neutral (can't measure alignment)
	}

	var deviations []float64
	for symbol, targetWeight := range ctx.OptimizerTargetWeights {
		// Get current position value
		currentValue, hasPosition := ctx.Positions[symbol]
		currentWeight := 0.0
		if hasPosition {
			currentWeight = currentValue / totalValue
		}

		// Calculate deviation from target
		deviation := math.Abs(currentWeight - targetWeight)
		deviations = append(deviations, deviation)
	}

	if len(deviations) == 0 {
		return 0.5 // No targets to compare
	}

	// Average deviation across all targets
	avgDeviation := sum(deviations) / float64(len(deviations))

	// Score: 0 deviation = 1.0, 10% avg deviation = 0.5, 20%+ = 0.0
	// Formula: 1.0 - (avgDeviation / 0.20)
	// This allows some deviation (not strict) but rewards alignment
	alignmentScore := math.Max(0.0, 1.0-avgDeviation/0.20)

	return alignmentScore
}

// EvaluateSequence evaluates a complete sequence: simulate + score
//
// This is the main entry point for sequence evaluation that:
// 1. Simulates the sequence to get end state
// 2. Evaluates the end state to get a score
// 3. Returns the result
func EvaluateSequence(
	sequence []ActionCandidate,
	context EvaluationContext,
) SequenceEvaluationResult {
	// Check feasibility first (fast pre-filter)
	feasible := CheckSequenceFeasibility(
		sequence,
		context.AvailableCashEUR,
		context.PortfolioContext,
	)

	if !feasible {
		// Calculate transaction costs even for infeasible sequences (useful for debugging)
		txCosts := CalculateTransactionCost(
			sequence,
			context.TransactionCostFixed,
			context.TransactionCostPercent,
		)

		return SequenceEvaluationResult{
			Sequence:         sequence,
			Score:            0.0,
			EndCashEUR:       context.AvailableCashEUR,
			EndPortfolio:     context.PortfolioContext,
			TransactionCosts: txCosts,
			Feasible:         false,
		}
	}

	// Simulate sequence to get end state
	endPortfolio, endCash := SimulateSequenceWithContext(sequence, context)

	// Calculate transaction costs
	txCosts := CalculateTransactionCost(
		sequence,
		context.TransactionCostFixed,
		context.TransactionCostPercent,
	)

	// Evaluate end state to get score
	score := EvaluateEndState(
		endPortfolio,
		sequence,
		context.TransactionCostFixed,
		context.TransactionCostPercent,
		context.CostPenaltyFactor,
	)

	return SequenceEvaluationResult{
		Sequence:         sequence,
		Score:            score,
		EndCashEUR:       endCash,
		EndPortfolio:     endPortfolio,
		TransactionCosts: txCosts,
		Feasible:         true,
	}
}

// calculateExpectedReturnScore calculates expected return for portfolio.
// Accounts for BOTH growth (CAGR) AND dividends for total return perspective.
//
// Uses SecurityScores as proxy for expected CAGR (long-term component).
// If ExpectedReturns map is added to PortfolioContext in future, use that instead.
//
// Returns:
//   - Score from 0.0 to 1.0 based on total return (growth + dividend)
func calculateExpectedReturnScore(ctx PortfolioContext) float64 {
	totalValue := ctx.TotalValue
	if totalValue <= 0 {
		return 0.5 // Neutral score for empty portfolio
	}

	weightedReturn := 0.0
	weightedDividend := 0.0

	for symbol, value := range ctx.Positions {
		weight := value / totalValue

		// Get expected CAGR from security scores (proxy for long-term return)
		// SecurityScores represents overall quality, which correlates with expected return
		// In future, we can add ExpectedReturns map to PortfolioContext for more accuracy
		if ctx.SecurityScores != nil {
			if score, hasScore := ctx.SecurityScores[symbol]; hasScore {
				// Convert quality score (0-1) to expected CAGR estimate
				// High quality (0.8+) ≈ 11%+ CAGR, medium (0.6) ≈ 8%, low (0.4) ≈ 5%
				estimatedCAGR := score * 0.15 // Scale quality to CAGR estimate (0-15%)
				weightedReturn += estimatedCAGR * weight
			}
		}

		// Get dividend yield
		if ctx.SecurityDividends != nil {
			if dividendYield, hasDiv := ctx.SecurityDividends[symbol]; hasDiv {
				weightedDividend += dividendYield * weight
			}
		}
	}

	// Total return = growth + dividend
	totalReturn := weightedReturn + weightedDividend

	// Score based on target (11% minimum)
	// 11% = 0.6, 15% = 0.8, 20%+ = 1.0 (capped)
	if totalReturn >= 0.20 {
		return 1.0
	} else if totalReturn >= 0.15 {
		return 0.8 + (totalReturn-0.15)/0.05*0.2
	} else if totalReturn >= 0.11 {
		return 0.6 + (totalReturn-0.11)/0.04*0.2
	} else if totalReturn >= 0.05 {
		return 0.3 + (totalReturn-0.05)/0.06*0.3
	} else {
		return totalReturn / 0.05 * 0.3
	}
}

// calculateRiskAdjustedScore calculates portfolio-level risk-adjusted return score.
//
// Uses weighted average of security quality scores as proxy for risk-adjusted returns.
// High quality scores indicate good risk-adjusted returns (good Sharpe/Sortino).
//
// In future, we can calculate actual portfolio Sharpe/Sortino from historical returns.
//
// Returns:
//   - Score from 0.0 to 1.0 based on portfolio risk-adjusted return
func calculateRiskAdjustedScore(ctx PortfolioContext) float64 {
	totalValue := ctx.TotalValue
	if totalValue <= 0 {
		return 0.5 // Neutral score for empty portfolio
	}

	// Use weighted average of security quality scores as proxy for risk-adjusted return
	// High quality = good risk-adjusted returns (good Sharpe/Sortino)
	weightedQuality := 0.0
	hasQuality := false

	for symbol, value := range ctx.Positions {
		weight := value / totalValue

		if ctx.SecurityScores != nil {
			if quality, hasQ := ctx.SecurityScores[symbol]; hasQ {
				weightedQuality += quality * weight
				hasQuality = true
			}
		}
	}

	if !hasQuality {
		return 0.5 // Neutral if no quality data
	}

	// Quality score (0-1) maps directly to risk-adjusted return score
	// High quality (0.8+) = excellent risk-adjusted returns
	// Medium quality (0.6) = good risk-adjusted returns
	// Low quality (0.4) = poor risk-adjusted returns
	return weightedQuality
}

// calculatePortfolioQualityScore calculates weighted average quality score for portfolio.
//
// This is separate from the quality component in diversification score.
// This focuses purely on security quality, not diversification.
//
// Returns:
//   - Score from 0.0 to 1.0 based on weighted average security quality
func calculatePortfolioQualityScore(ctx PortfolioContext) float64 {
	totalValue := ctx.TotalValue
	if totalValue <= 0 {
		return 0.5 // Neutral score for empty portfolio
	}

	// Use the existing calculateQualityScore function
	// It already calculates weighted average of security quality scores
	return calculateQualityScore(ctx, totalValue)
}

// Helper function to sum a slice of floats
func sum(values []float64) float64 {
	total := 0.0
	for _, v := range values {
		total += v
	}
	return total
}
