package evaluation

import (
	"math"

	"github.com/aristath/sentinel/internal/evaluation/models"
	"github.com/aristath/sentinel/internal/utils"
)

// =============================================================================
// UNIFIED EVALUATION WEIGHTS
// =============================================================================
// These weights implement pure end-state scoring for retirement investing.
// Scoring is based ONLY on the quality of the final portfolio state,
// NOT on action characteristics like priority or count.
//
// Philosophy:
// - Portfolio Quality (35%): Quality compounding over 15 years matters
// - Diversification & Alignment (30%): Geographic, industry, optimizer alignment
// - Risk-Adjusted Metrics (25%): Risk-AWARE not risk-AVERSE
// - End-State Improvement (10%): Reward progress toward better portfolio

const (
	// Main evaluation component weights (must sum to 1.0)
	// ALL components measure END STATE QUALITY, not action characteristics
	WeightPortfolioQuality         = 0.35 // End state quality (total return, promise, stability)
	WeightDiversificationAlignment = 0.30 // Geographic, industry, optimizer alignment
	WeightRiskAdjustedMetrics      = 0.25 // Sharpe, volatility, drawdown
	WeightEndStateImprovement      = 0.10 // Improvement from start to end state

	// Sub-weights for Portfolio Quality (35%)
	QualityWeightTotalReturn     = 0.40 // CAGR + Dividends
	QualityWeightLongTermPromise = 0.35 // Consistency, financial strength
	QualityWeightStability       = 0.25 // Low volatility, minimal drawdown

	// Sub-weights for Diversification & Alignment (30%)
	DiversificationWeightGeographic = 0.35 // Geographic allocation fit
	DiversificationWeightIndustry   = 0.30 // Industry/sector allocation fit
	DiversificationWeightOptimizer  = 0.35 // Optimizer target weight alignment

	// Sub-weights for Risk-Adjusted Metrics (25%)
	RiskWeightSharpe     = 0.40 // Risk-adjusted return (Sharpe)
	RiskWeightVolatility = 0.35 // Portfolio volatility
	RiskWeightDrawdown   = 0.25 // Maximum drawdown impact

	// Deviation scoring scale
	DeviationScale = 0.3 // Maximum deviation for 0 score (30%)
)

// =============================================================================
// REGIME-ADAPTIVE WEIGHTS
// =============================================================================
// Weights shift based on market conditions while maintaining overall philosophy.
// With pure end-state scoring, regime adaptation is simpler and focuses on
// risk vs quality trade-offs.

// GetRegimeAdaptiveWeights returns evaluation weights adjusted for market regime.
// Uses default hardcoded weights. For temperament-adjusted weights, use getWeightsWithConfig.
func GetRegimeAdaptiveWeights(regimeScore float64) map[string]float64 {
	return getWeightsWithConfig(regimeScore, nil)
}

// getWeightsWithConfig returns evaluation weights adjusted for market regime,
// using temperament-adjusted base weights if a config is provided.
func getWeightsWithConfig(regimeScore float64, config *models.ScoringConfig) map[string]float64 {
	// Clamp regime score to valid range
	score := math.Max(-1.0, math.Min(1.0, regimeScore))

	// Get base weights from config or use defaults
	var baseQuality, baseDiversification, baseRisk, baseImprovement float64
	var bullThreshold, bearThreshold float64

	if config != nil {
		baseQuality = config.WeightPortfolioQuality
		baseDiversification = config.WeightDiversificationAlignment
		baseRisk = config.WeightRiskAdjustedMetrics
		baseImprovement = WeightEndStateImprovement // Use constant for improvement
		bullThreshold = config.RegimeBullThreshold
		bearThreshold = config.RegimeBearThreshold
	} else {
		// Default hardcoded values
		baseQuality = WeightPortfolioQuality
		baseDiversification = WeightDiversificationAlignment
		baseRisk = WeightRiskAdjustedMetrics
		baseImprovement = WeightEndStateImprovement
		bullThreshold = 0.3
		bearThreshold = -0.3
	}

	// Start with base weights
	weights := map[string]float64{
		"quality":         baseQuality,
		"diversification": baseDiversification,
		"risk":            baseRisk,
		"improvement":     baseImprovement,
	}

	// Adjust based on regime - pure end-state adjustments
	if score > bullThreshold { // Bull market
		// In bull markets: emphasize quality and diversification
		bullFactor := (score - bullThreshold) / (1.0 - bullThreshold) // 0 to 1
		weights["quality"] = baseQuality + 0.03*bullFactor
		weights["risk"] = baseRisk - 0.03*bullFactor
	} else if score < bearThreshold { // Bear market
		// In bear markets: emphasize risk management and diversification
		bearFactor := (bearThreshold - score) / (bearThreshold - (-1.0)) // 0 to 1
		weights["risk"] = baseRisk + 0.08*bearFactor
		weights["diversification"] = baseDiversification + 0.02*bearFactor
		weights["quality"] = baseQuality - 0.05*bearFactor
		weights["improvement"] = baseImprovement - 0.05*bearFactor
	}

	return weights
}

// =============================================================================
// MAIN EVALUATION FUNCTION
// =============================================================================

// EvaluateEndState evaluates the end state of a portfolio after executing a sequence.
//
// This is the UNIFIED evaluation function using PURE END-STATE scoring:
// 1. Portfolio Quality (35%): Total return, long-term promise, stability
// 2. Diversification & Alignment (30%): Geographic, industry, optimizer alignment
// 3. Risk-Adjusted Metrics (25%): Sharpe, volatility, drawdown
// 4. End-State Improvement (10%): How much the portfolio improved from start
//
// IMPORTANT: This function scores based ONLY on end portfolio state.
// It does NOT consider action characteristics like priority or count.
//
// Args:
//   - startContext: Portfolio state BEFORE sequence execution
//   - endContext: Portfolio state AFTER sequence execution
//   - sequence: The action sequence (only used for transaction cost calculation)
//   - transactionCostFixed: Fixed cost per trade (EUR)
//   - transactionCostPercent: Variable cost as fraction
//   - costPenaltyFactor: Penalty factor for transaction costs (0.0 = no penalty)
//   - scoringConfig: Optional temperament-adjusted scoring parameters (nil uses defaults)
//
// Returns:
//   - Final score (0-1 scale)
func EvaluateEndState(
	startContext models.PortfolioContext,
	endContext models.PortfolioContext,
	sequence []models.ActionCandidate,
	transactionCostFixed float64,
	transactionCostPercent float64,
	costPenaltyFactor float64,
	scoringConfig *models.ScoringConfig,
) float64 {
	// Get regime-adaptive weights (uses config if provided, defaults otherwise)
	weights := getWeightsWithConfig(endContext.MarketRegimeScore, scoringConfig)

	// 1. PORTFOLIO QUALITY (35% default)
	qualityScore := calculatePortfolioQualityScore(endContext)

	// 2. DIVERSIFICATION & ALIGNMENT (30% default)
	diversificationScore := calculateDiversificationAlignmentScore(endContext)

	// 3. RISK-ADJUSTED METRICS (25% default)
	riskScore := calculateRiskAdjustedScore(endContext)

	// 4. END-STATE IMPROVEMENT (10% default)
	improvementScore := calculateEndStateImprovementScore(startContext, endContext)

	// Combine scores with regime-adaptive weights
	endScore := qualityScore*weights["quality"] +
		diversificationScore*weights["diversification"] +
		riskScore*weights["risk"] +
		improvementScore*weights["improvement"]

	// Apply transaction cost penalty
	totalCost := CalculateTransactionCost(sequence, transactionCostFixed, transactionCostPercent)
	if costPenaltyFactor > 0.0 && endContext.TotalValue > 0 {
		costPenalty := (totalCost / endContext.TotalValue) * costPenaltyFactor
		endScore = math.Max(0.0, endScore-costPenalty)
	}

	return math.Min(1.0, math.Max(0.0, endScore))
}

// =============================================================================
// COMPONENT 1: END-STATE IMPROVEMENT (10%)
// =============================================================================
// Measures how much the portfolio improved from start to end state.
// Rewards sequences that move the portfolio closer to targets.

// calculateEndStateImprovementScore measures portfolio improvement from start to end.
// Returns 0.5 for no change, higher for improvement, lower for degradation.
func calculateEndStateImprovementScore(start, end models.PortfolioContext) float64 {
	if start.TotalValue <= 0 || end.TotalValue <= 0 {
		return 0.5 // Neutral if no valid data
	}

	// Calculate component scores for both states
	startDiv := calculateDiversificationAlignmentScore(start)
	endDiv := calculateDiversificationAlignmentScore(end)

	startRisk := calculateRiskAdjustedScore(start)
	endRisk := calculateRiskAdjustedScore(end)

	startQuality := calculatePortfolioQualityScore(start)
	endQuality := calculatePortfolioQualityScore(end)

	// Calculate improvements (positive = better)
	divImprovement := endDiv - startDiv
	riskImprovement := endRisk - startRisk
	qualityImprovement := endQuality - startQuality

	// Average improvement, scaled to 0-1 range
	// Improvements range from -1 to +1, so map to 0-1
	avgImprovement := (divImprovement + riskImprovement + qualityImprovement) / 3.0
	score := 0.5 + (avgImprovement * 0.5) // Maps [-1,1] to [0,1]

	return math.Min(1.0, math.Max(0.0, score))
}

// =============================================================================
// COMPONENT 2: PORTFOLIO QUALITY (35%)
// =============================================================================
// Quality compounding over 15 years matters.
// Quality compounding over 15 years matters.

func calculatePortfolioQualityScore(ctx models.PortfolioContext) float64 {
	totalValue := ctx.TotalValue
	if totalValue <= 0 {
		return 0.5
	}

	// Calculate sub-scores
	totalReturnScore := calculateTotalReturnScore(ctx)
	longTermPromiseScore := calculateLongTermPromiseScore(ctx)
	stabilityScore := calculateStabilityScore(ctx)

	// Combine with sub-weights
	return totalReturnScore*QualityWeightTotalReturn +
		longTermPromiseScore*QualityWeightLongTermPromise +
		stabilityScore*QualityWeightStability
}

// calculateTotalReturnScore evaluates expected total return (CAGR + dividends)
func calculateTotalReturnScore(ctx models.PortfolioContext) float64 {
	totalValue := ctx.TotalValue
	if totalValue <= 0 {
		return 0.5
	}

	weightedCAGR := 0.0
	weightedDividend := 0.0

	for isin, value := range ctx.Positions {
		weight := value / totalValue

		// CAGR contribution
		if cagr, hasCagr := ctx.SecurityCAGRs[isin]; hasCagr {
			weightedCAGR += cagr * weight
		} else if score, hasScore := ctx.SecurityScores[isin]; hasScore {
			// Estimate CAGR from quality score
			weightedCAGR += score * 0.15 * weight // Quality -> estimated CAGR
		}

		// Dividend contribution
		if dividend, hasDiv := ctx.SecurityDividends[isin]; hasDiv {
			weightedDividend += dividend * weight
		}
	}

	// Total return = growth + dividend
	totalReturn := weightedCAGR + weightedDividend

	// Score based on target (11% optimal for retirement)
	// Using asymmetric bell curve
	target := 0.11
	var score float64
	if totalReturn >= 0.20 {
		score = 0.95 // Excellent but cap to avoid chasing extreme returns
	} else if totalReturn >= target {
		// Above target: gentle slope down
		score = 1.0 - (totalReturn-target)/0.09*0.15
	} else if totalReturn >= 0.05 {
		// Below target but positive
		score = 0.5 + (totalReturn-0.05)/0.06*0.5
	} else if totalReturn >= 0 {
		score = totalReturn / 0.05 * 0.5
	} else {
		score = 0.1 // Negative return floor
	}

	return score
}

// calculateLongTermPromiseScore evaluates consistency and financial strength
func calculateLongTermPromiseScore(ctx models.PortfolioContext) float64 {
	totalValue := ctx.TotalValue
	if totalValue <= 0 {
		return 0.5
	}

	// Use quality scores as proxy for long-term promise
	weightedQuality := 0.0
	hasQuality := false

	for isin, value := range ctx.Positions {
		weight := value / totalValue
		if quality, hasQ := ctx.SecurityScores[isin]; hasQ {
			weightedQuality += quality * weight
			hasQuality = true
		}
	}

	if !hasQuality {
		return 0.5
	}

	return weightedQuality
}

// calculateStabilityScore evaluates volatility and drawdown
func calculateStabilityScore(ctx models.PortfolioContext) float64 {
	totalValue := ctx.TotalValue
	if totalValue <= 0 {
		return 0.5
	}

	// Calculate weighted volatility
	weightedVol := 0.0
	weightedDD := 0.0
	hasVol := false
	hasDD := false

	for isin, value := range ctx.Positions {
		weight := value / totalValue

		if vol, hasV := ctx.SecurityVolatility[isin]; hasV && vol > 0 {
			weightedVol += vol * weight
			hasVol = true
		}

		if dd, hasD := ctx.SecurityMaxDrawdown[isin]; hasD {
			weightedDD += math.Abs(dd) * weight
			hasDD = true
		}
	}

	// Convert to scores
	volScore := 0.5
	if hasVol {
		// Lower volatility = higher score
		if weightedVol <= 0.15 {
			volScore = 1.0
		} else if weightedVol <= 0.25 {
			volScore = 1.0 - (weightedVol-0.15)/0.10*0.3
		} else if weightedVol <= 0.40 {
			volScore = 0.7 - (weightedVol-0.25)/0.15*0.4
		} else {
			volScore = math.Max(0.1, 0.3-(weightedVol-0.40))
		}
	}

	ddScore := 0.5
	if hasDD {
		// Lower drawdown = higher score
		if weightedDD <= 0.10 {
			ddScore = 1.0
		} else if weightedDD <= 0.20 {
			ddScore = 0.8 + (0.20-weightedDD)*2
		} else if weightedDD <= 0.30 {
			ddScore = 0.6 + (0.30-weightedDD)*2
		} else {
			ddScore = math.Max(0.1, 0.6-(weightedDD-0.30)*2)
		}
	}

	// Combine volatility and drawdown
	return volScore*0.6 + ddScore*0.4
}

// =============================================================================
// COMPONENT 3: DIVERSIFICATION & ALIGNMENT (30%)
// =============================================================================
// Geographic, industry, and optimizer alignment.

func calculateDiversificationAlignmentScore(ctx models.PortfolioContext) float64 {
	totalValue := ctx.TotalValue
	if totalValue <= 0 {
		return 0.5
	}

	// Calculate sub-scores
	geoScore := calculateGeoDiversification(ctx, totalValue)
	indScore := calculateIndustryDiversification(ctx, totalValue)
	alignmentScore := calculateOptimizerAlignment(ctx, totalValue)

	// Combine with sub-weights
	return geoScore*DiversificationWeightGeographic +
		indScore*DiversificationWeightIndustry +
		alignmentScore*DiversificationWeightOptimizer
}

// calculateGeoDiversification calculates geographic diversification score
func calculateGeoDiversification(ctx models.PortfolioContext, totalValue float64) float64 {
	if ctx.SecurityGeographies == nil || len(ctx.GeographyWeights) == 0 {
		return 0.5
	}

	// Aggregate position values by geography (direct, no groups)
	// Parse comma-separated geographies and distribute value equally across them
	geographyValues := make(map[string]float64)
	for isin, value := range ctx.Positions {
		geoStr, hasGeography := ctx.SecurityGeographies[isin]
		if !hasGeography {
			geoStr = "OTHER"
		}

		geographies := utils.ParseCSV(geoStr)
		if len(geographies) == 0 {
			geographies = []string{"OTHER"}
		}

		valuePerGeo := value / float64(len(geographies))
		for _, geo := range geographies {
			geographyValues[geo] += valuePerGeo
		}
	}

	var deviations []float64
	for geography, targetWeight := range ctx.GeographyWeights {
		currentValue := geographyValues[geography]
		currentPct := currentValue / totalValue
		deviation := math.Abs(currentPct - targetWeight)
		deviations = append(deviations, deviation)
	}

	if len(deviations) == 0 {
		return 0.5
	}

	avgDeviation := sum(deviations) / float64(len(deviations))
	return math.Max(0, 1.0-avgDeviation/DeviationScale)
}

// calculateIndustryDiversification calculates industry diversification score
func calculateIndustryDiversification(ctx models.PortfolioContext, totalValue float64) float64 {
	if ctx.SecurityIndustries == nil || len(ctx.IndustryWeights) == 0 {
		return 0.5
	}

	// Aggregate position values by industry (direct, no groups)
	// Parse comma-separated industries and distribute value equally across them
	industryValues := make(map[string]float64)
	for isin, value := range ctx.Positions {
		indStr, hasIndustry := ctx.SecurityIndustries[isin]
		if !hasIndustry {
			indStr = "OTHER"
		}

		industries := utils.ParseCSV(indStr)
		if len(industries) == 0 {
			industries = []string{"OTHER"}
		}

		valuePerInd := value / float64(len(industries))
		for _, industry := range industries {
			industryValues[industry] += valuePerInd
		}
	}

	var deviations []float64
	for industry, targetWeight := range ctx.IndustryWeights {
		currentValue := industryValues[industry]
		currentPct := currentValue / totalValue
		deviation := math.Abs(currentPct - targetWeight)
		deviations = append(deviations, deviation)
	}

	if len(deviations) == 0 {
		return 0.5
	}

	avgDeviation := sum(deviations) / float64(len(deviations))
	return math.Max(0, 1.0-avgDeviation/DeviationScale)
}

// calculateOptimizerAlignment scores alignment with optimizer target weights
func calculateOptimizerAlignment(ctx models.PortfolioContext, totalValue float64) float64 {
	if len(ctx.OptimizerTargetWeights) == 0 {
		return 0.5
	}

	var deviations []float64
	for isin, targetWeight := range ctx.OptimizerTargetWeights {
		currentValue, hasPosition := ctx.Positions[isin]
		currentWeight := 0.0
		if hasPosition {
			currentWeight = currentValue / totalValue
		}

		deviation := math.Abs(currentWeight - targetWeight)
		deviations = append(deviations, deviation)
	}

	if len(deviations) == 0 {
		return 0.5
	}

	avgDeviation := sum(deviations) / float64(len(deviations))
	// Score: 0 deviation = 1.0, 20% avg deviation = 0.0
	return math.Max(0.0, 1.0-avgDeviation/0.20)
}

// =============================================================================
// COMPONENT 4: RISK-ADJUSTED METRICS (25%)
// =============================================================================
// Risk-AWARE not risk-AVERSE.

func calculateRiskAdjustedScore(ctx models.PortfolioContext) float64 {
	totalValue := ctx.TotalValue
	if totalValue <= 0 {
		return 0.5
	}

	// Calculate weighted Sharpe ratio
	sharpeScore := calculateWeightedSharpeScore(ctx, totalValue)

	// Calculate weighted volatility score (inverse - lower is better)
	volScore := calculateWeightedVolatilityScore(ctx, totalValue)

	// Calculate weighted drawdown score
	drawdownScore := calculateWeightedDrawdownScore(ctx, totalValue)

	// Combine with sub-weights
	return sharpeScore*RiskWeightSharpe +
		volScore*RiskWeightVolatility +
		drawdownScore*RiskWeightDrawdown
}

// calculateWeightedSharpeScore calculates weighted Sharpe score
func calculateWeightedSharpeScore(ctx models.PortfolioContext, totalValue float64) float64 {
	weightedSharpe := 0.0
	hasSharpe := false

	for isin, value := range ctx.Positions {
		weight := value / totalValue
		if sharpe, hasS := ctx.SecuritySharpe[isin]; hasS {
			weightedSharpe += sharpe * weight
			hasSharpe = true
		}
	}

	if !hasSharpe {
		return 0.5
	}

	// Convert Sharpe to score
	if weightedSharpe >= 2.0 {
		return 1.0
	} else if weightedSharpe >= 1.0 {
		return 0.7 + (weightedSharpe-1.0)*0.3
	} else if weightedSharpe >= 0.5 {
		return 0.4 + (weightedSharpe-0.5)*0.6
	} else if weightedSharpe >= 0 {
		return weightedSharpe * 0.8
	}
	return 0.0
}

// calculateWeightedVolatilityScore calculates inverse volatility score
func calculateWeightedVolatilityScore(ctx models.PortfolioContext, totalValue float64) float64 {
	weightedVol := 0.0
	hasVol := false

	for isin, value := range ctx.Positions {
		weight := value / totalValue
		if vol, hasV := ctx.SecurityVolatility[isin]; hasV && vol > 0 {
			weightedVol += vol * weight
			hasVol = true
		}
	}

	if !hasVol {
		return 0.5
	}

	// Lower volatility = higher score
	if weightedVol <= 0.15 {
		return 1.0
	} else if weightedVol <= 0.25 {
		return 0.8 + (0.25-weightedVol)*2
	} else if weightedVol <= 0.40 {
		return 0.5 + (0.40-weightedVol)/0.15*0.3
	}
	return math.Max(0.2, 0.5-(weightedVol-0.40))
}

// calculateWeightedDrawdownScore calculates drawdown score
func calculateWeightedDrawdownScore(ctx models.PortfolioContext, totalValue float64) float64 {
	weightedDD := 0.0
	hasDD := false

	for isin, value := range ctx.Positions {
		weight := value / totalValue
		if dd, hasD := ctx.SecurityMaxDrawdown[isin]; hasD {
			weightedDD += math.Abs(dd) * weight
			hasDD = true
		}
	}

	if !hasDD {
		return 0.5
	}

	// Lower drawdown = higher score
	if weightedDD <= 0.10 {
		return 1.0
	} else if weightedDD <= 0.20 {
		return 0.8 + (0.20-weightedDD)*2
	} else if weightedDD <= 0.30 {
		return 0.6 + (0.30-weightedDD)*2
	} else if weightedDD <= 0.50 {
		return 0.2 + (0.50-weightedDD)*2
	}
	return math.Max(0.0, 0.2-(weightedDD-0.50))
}

// =============================================================================
// TRANSACTION COST CALCULATION
// =============================================================================

// CalculateTransactionCost calculates total transaction cost for a sequence.
func CalculateTransactionCost(
	sequence []models.ActionCandidate,
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
func CalculateTransactionCostEnhanced(
	sequence []models.ActionCandidate,
	transactionCostFixed float64,
	transactionCostPercent float64,
	spreadCostPercent float64,
	slippagePercent float64,
	marketImpactPercent float64,
) float64 {
	totalCost := 0.0
	for _, action := range sequence {
		fixedCost := transactionCostFixed
		variableCost := math.Abs(action.ValueEUR) * transactionCostPercent
		spreadCost := math.Abs(action.ValueEUR) * spreadCostPercent
		slippageCost := math.Abs(action.ValueEUR) * slippagePercent
		impactCost := math.Abs(action.ValueEUR) * marketImpactPercent

		tradeCost := fixedCost + variableCost + spreadCost + slippageCost + impactCost
		totalCost += tradeCost
	}
	return totalCost
}

// =============================================================================
// DIVERSIFICATION SCORE
// =============================================================================

// CalculateDiversificationScore calculates diversification score for a portfolio.
func CalculateDiversificationScore(ctx models.PortfolioContext) float64 {
	totalValue := ctx.TotalValue
	if totalValue <= 0 {
		return 0.5
	}

	return calculateDiversificationAlignmentScore(ctx)
}

// =============================================================================
// MAIN SEQUENCE EVALUATION
// =============================================================================

// EvaluateSequence evaluates a complete sequence: simulate + score
func EvaluateSequence(
	sequence []models.ActionCandidate,
	context models.EvaluationContext,
) models.SequenceEvaluationResult {
	// Check feasibility first
	feasible := CheckSequenceFeasibility(
		sequence,
		context.AvailableCashEUR,
		context.PortfolioContext,
	)

	if !feasible {
		txCosts := CalculateTransactionCost(
			sequence,
			context.TransactionCostFixed,
			context.TransactionCostPercent,
		)

		return models.SequenceEvaluationResult{
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

	// Evaluate end state with pure end-state scoring
	// Pass BOTH start and end context for improvement calculation
	score := EvaluateEndState(
		context.PortfolioContext, // Start state
		endPortfolio,             // End state
		sequence,
		context.TransactionCostFixed,
		context.TransactionCostPercent,
		context.CostPenaltyFactor,
		context.ScoringConfig,
	)

	return models.SequenceEvaluationResult{
		Sequence:         sequence,
		Score:            score,
		EndCashEUR:       endCash,
		EndPortfolio:     endPortfolio,
		TransactionCosts: txCosts,
		Feasible:         true,
	}
}

// Helper function to sum a slice of floats
func sum(values []float64) float64 {
	total := 0.0
	for _, v := range values {
		total += v
	}
	return total
}
