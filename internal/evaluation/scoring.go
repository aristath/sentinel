package evaluation

import (
	"math"

	"github.com/aristath/sentinel/internal/evaluation/models"
)

// =============================================================================
// UNIFIED EVALUATION WEIGHTS
// =============================================================================
// These weights implement solid investment principles with a retirement bias.
// Designed to be action-oriented while remaining principled.
//
// Philosophy:
// - Opportunity Capture (30%): This is WHY the system exists - to act on opportunities
// - Portfolio Quality (25%): Quality compounding over 15 years matters
// - Diversification & Alignment (20%): Discipline without paralysis
// - Risk-Adjusted Metrics (15%): Risk-AWARE not risk-AVERSE
// - Regime & Robustness (10%): Adaptive + sanity check, not gatekeeper

const (
	// Main evaluation component weights (must sum to 1.0)
	WeightOpportunityCapture       = 0.30 // Windfall, action priority, opportunity score
	WeightPortfolioQuality         = 0.25 // End state quality (total return, promise, stability)
	WeightDiversificationAlignment = 0.20 // Geographic, industry, optimizer alignment
	WeightRiskAdjustedMetrics      = 0.15 // Sharpe, Sortino, volatility impact
	WeightRegimeRobustness         = 0.10 // Market regime, robustness checks

	// Sub-weights for Opportunity Capture (30%)
	OpportunityWeightWindfall       = 0.40 // Windfall detection (excess gains)
	OpportunityWeightActionPriority = 0.35 // Priority from opportunity identification
	OpportunityWeightTechnical      = 0.25 // Technical opportunity score

	// Sub-weights for Portfolio Quality (25%)
	QualityWeightTotalReturn     = 0.40 // CAGR + Dividends
	QualityWeightLongTermPromise = 0.35 // Consistency, financial strength
	QualityWeightStability       = 0.25 // Low volatility, minimal drawdown

	// Sub-weights for Diversification & Alignment (20%)
	DiversificationWeightGeographic = 0.35 // Geographic allocation fit
	DiversificationWeightIndustry   = 0.30 // Industry/sector allocation fit
	DiversificationWeightOptimizer  = 0.35 // Optimizer target weight alignment

	// Sub-weights for Risk-Adjusted Metrics (15%)
	RiskWeightSharpe     = 0.40 // Risk-adjusted return (Sharpe)
	RiskWeightVolatility = 0.35 // Portfolio volatility
	RiskWeightDrawdown   = 0.25 // Maximum drawdown impact

	// Deviation scoring scale
	DeviationScale = 0.3 // Maximum deviation for 0 score (30%)

	// Windfall thresholds
	WindfallExcessHigh   = 0.50 // 50%+ above expected = high windfall
	WindfallExcessMedium = 0.25 // 25-50% above expected = medium windfall
)

// =============================================================================
// REGIME-ADAPTIVE WEIGHTS
// =============================================================================
// Weights shift based on market conditions while maintaining overall philosophy.

// GetRegimeAdaptiveWeights returns evaluation weights adjusted for market regime
func GetRegimeAdaptiveWeights(regimeScore float64) map[string]float64 {
	// Clamp regime score to valid range
	score := math.Max(-1.0, math.Min(1.0, regimeScore))

	// Base weights (neutral market)
	weights := map[string]float64{
		"opportunity":     WeightOpportunityCapture,
		"quality":         WeightPortfolioQuality,
		"diversification": WeightDiversificationAlignment,
		"risk":            WeightRiskAdjustedMetrics,
		"robustness":      WeightRegimeRobustness,
	}

	// Adjust based on regime
	if score > 0.3 { // Bull market
		// More aggressive: increase opportunity capture, decrease risk focus
		bullFactor := (score - 0.3) / 0.7                   // 0 to 1 as score goes from 0.3 to 1.0
		weights["opportunity"] = 0.30 + 0.05*bullFactor     // 30% -> 35%
		weights["risk"] = 0.15 - 0.03*bullFactor            // 15% -> 12%
		weights["diversification"] = 0.20 - 0.02*bullFactor // 20% -> 18%
		weights["robustness"] = 0.10 + 0.02*bullFactor      // 10% -> 12%
	} else if score < -0.3 { // Bear market
		// More defensive: decrease opportunity, increase risk focus
		bearFactor := (-score - 0.3) / 0.7                  // 0 to 1 as score goes from -0.3 to -1.0
		weights["opportunity"] = 0.30 - 0.10*bearFactor     // 30% -> 20%
		weights["risk"] = 0.15 + 0.10*bearFactor            // 15% -> 25%
		weights["diversification"] = 0.20 + 0.05*bearFactor // 20% -> 25%
		weights["quality"] = 0.25 - 0.02*bearFactor         // 25% -> 23%
		weights["robustness"] = 0.10 - 0.03*bearFactor      // 10% -> 7%
	}

	return weights
}

// =============================================================================
// MAIN EVALUATION FUNCTION
// =============================================================================

// EvaluateEndState evaluates the end state of a portfolio after executing a sequence.
//
// This is the UNIFIED evaluation function that combines:
// 1. Opportunity Capture (30%): Windfall, action priority, technical opportunity
// 2. Portfolio Quality (25%): Total return, long-term promise, stability
// 3. Diversification & Alignment (20%): Geographic, industry, optimizer alignment
// 4. Risk-Adjusted Metrics (15%): Sharpe, volatility, drawdown
// 5. Regime & Robustness (10%): Market regime alignment, robustness checks
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
func EvaluateEndState(
	endContext models.PortfolioContext,
	sequence []models.ActionCandidate,
	transactionCostFixed float64,
	transactionCostPercent float64,
	costPenaltyFactor float64,
) float64 {
	// Get regime-adaptive weights
	weights := GetRegimeAdaptiveWeights(endContext.MarketRegimeScore)

	// 1. OPPORTUNITY CAPTURE (30% default)
	opportunityScore := calculateOpportunityCaptureScore(endContext, sequence)

	// 2. PORTFOLIO QUALITY (25% default)
	qualityScore := calculatePortfolioQualityScore(endContext)

	// 3. DIVERSIFICATION & ALIGNMENT (20% default)
	diversificationScore := calculateDiversificationAlignmentScore(endContext)

	// 4. RISK-ADJUSTED METRICS (15% default)
	riskScore := calculateRiskAdjustedScore(endContext)

	// 5. REGIME & ROBUSTNESS (10% default)
	robustnessScore := calculateRegimeRobustnessScore(endContext, sequence)

	// Combine scores with regime-adaptive weights
	endScore := opportunityScore*weights["opportunity"] +
		qualityScore*weights["quality"] +
		diversificationScore*weights["diversification"] +
		riskScore*weights["risk"] +
		robustnessScore*weights["robustness"]

	// Apply transaction cost penalty
	totalCost := CalculateTransactionCost(sequence, transactionCostFixed, transactionCostPercent)
	if costPenaltyFactor > 0.0 && endContext.TotalValue > 0 {
		costPenalty := (totalCost / endContext.TotalValue) * costPenaltyFactor
		endScore = math.Max(0.0, endScore-costPenalty)
	}

	return math.Min(1.0, math.Max(0.0, endScore))
}

// =============================================================================
// COMPONENT 1: OPPORTUNITY CAPTURE (30%)
// =============================================================================
// This is WHY the system exists - to capture value opportunities.

func calculateOpportunityCaptureScore(ctx models.PortfolioContext, sequence []models.ActionCandidate) float64 {
	if len(sequence) == 0 {
		return 0.5 // Neutral for empty sequence
	}

	// Calculate sub-scores
	windfallScore := calculateWindfallScore(ctx, sequence)
	priorityScore := calculateActionPriorityScore(sequence)
	technicalScore := calculateTechnicalOpportunityScore(ctx, sequence)

	// Combine with sub-weights
	return windfallScore*OpportunityWeightWindfall +
		priorityScore*OpportunityWeightActionPriority +
		technicalScore*OpportunityWeightTechnical
}

// calculateWindfallScore detects excess gains above expected CAGR
func calculateWindfallScore(ctx models.PortfolioContext, sequence []models.ActionCandidate) float64 {
	if len(sequence) == 0 {
		return 0.5
	}

	totalWindfallScore := 0.0
	sellCount := 0

	for _, action := range sequence {
		if !action.Side.IsSell() {
			continue
		}
		sellCount++

		// Calculate current gain
		avgPrice, hasAvg := ctx.PositionAvgPrices[action.Symbol]
		currentPrice, hasCurrent := ctx.CurrentPrices[action.Symbol]
		if !hasAvg || !hasCurrent || avgPrice <= 0 {
			totalWindfallScore += 0.5 // Neutral if no price data
			continue
		}

		currentGain := (currentPrice - avgPrice) / avgPrice

		// Get historical CAGR (default 10% if not available)
		historicalCAGR := 0.10
		if cagr, hasCagr := ctx.SecurityCAGRs[action.Symbol]; hasCagr && cagr > 0 {
			historicalCAGR = cagr
		}

		// Calculate expected gain (assume 1 year holding if no data)
		yearsHeld := 1.0
		expectedGain := math.Pow(1+historicalCAGR, yearsHeld) - 1
		excessGain := currentGain - expectedGain

		// Score based on excess gain
		var windfallScore float64
		if excessGain >= WindfallExcessHigh { // 50%+ excess
			windfallScore = 1.0
		} else if excessGain >= WindfallExcessMedium { // 25-50% excess
			windfallScore = 0.5 + (excessGain-WindfallExcessMedium)/(WindfallExcessHigh-WindfallExcessMedium)*0.5
		} else if excessGain > 0 { // 0-25% excess
			windfallScore = excessGain / WindfallExcessMedium * 0.5
		} else {
			windfallScore = 0.3 // Below expected, still valid to sell for rebalancing
		}

		totalWindfallScore += windfallScore
	}

	// For BUY sequences, check if we're buying at good prices
	buyCount := 0
	for _, action := range sequence {
		if action.Side.IsBuy() {
			buyCount++
			// Buying opportunity score based on technical indicators
			// (handled in technical score)
			totalWindfallScore += 0.6 // Neutral-positive for buys
		}
	}

	totalActions := sellCount + buyCount
	if totalActions == 0 {
		return 0.5
	}

	return totalWindfallScore / float64(totalActions)
}

// calculateActionPriorityScore uses the priority from opportunity identification
func calculateActionPriorityScore(sequence []models.ActionCandidate) float64 {
	if len(sequence) == 0 {
		return 0.5
	}

	totalPriority := 0.0
	for _, action := range sequence {
		// Priority is already 0-1 from opportunity identification
		// Clamp to ensure valid range
		priority := math.Max(0, math.Min(1, action.Priority))
		totalPriority += priority
	}

	return totalPriority / float64(len(sequence))
}

// calculateTechnicalOpportunityScore evaluates technical indicators
func calculateTechnicalOpportunityScore(ctx models.PortfolioContext, sequence []models.ActionCandidate) float64 {
	if len(sequence) == 0 {
		return 0.5
	}

	// For now, use security scores as proxy for technical opportunity
	// In full implementation, this would check RSI, Bollinger, 52W high, etc.
	totalScore := 0.0
	count := 0

	for _, action := range sequence {
		if score, hasScore := ctx.SecurityScores[action.Symbol]; hasScore {
			// For buys: higher score = better opportunity
			// For sells: score indicates we're selling quality (neutral)
			if action.Side.IsBuy() {
				totalScore += score
			} else {
				totalScore += 0.5 + score*0.3 // Selling quality is okay
			}
			count++
		} else {
			totalScore += 0.5 // Neutral if no score
			count++
		}
	}

	if count == 0 {
		return 0.5
	}

	return totalScore / float64(count)
}

// =============================================================================
// COMPONENT 2: PORTFOLIO QUALITY (25%)
// =============================================================================
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
// COMPONENT 3: DIVERSIFICATION & ALIGNMENT (20%)
// =============================================================================
// Discipline without paralysis.

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
	if ctx.SecurityCountries == nil || len(ctx.CountryWeights) == 0 {
		return 0.5
	}

	countryToGroup := ctx.CountryToGroup
	if countryToGroup == nil {
		countryToGroup = make(map[string]string)
	}

	groupValues := make(map[string]float64)
	for isin, value := range ctx.Positions {
		country, hasCountry := ctx.SecurityCountries[isin]
		if !hasCountry {
			country = "OTHER"
		}

		group, hasGroup := countryToGroup[country]
		if !hasGroup {
			group = "OTHER"
		}

		groupValues[group] += value
	}

	var deviations []float64
	for group, targetWeight := range ctx.CountryWeights {
		currentValue := groupValues[group]
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

	industryToGroup := ctx.IndustryToGroup
	if industryToGroup == nil {
		industryToGroup = make(map[string]string)
	}

	groupValues := make(map[string]float64)
	for isin, value := range ctx.Positions {
		industry, hasIndustry := ctx.SecurityIndustries[isin]
		if !hasIndustry {
			industry = "OTHER"
		}

		group, hasGroup := industryToGroup[industry]
		if !hasGroup {
			group = "OTHER"
		}

		groupValues[group] += value
	}

	var deviations []float64
	for group, targetWeight := range ctx.IndustryWeights {
		currentValue := groupValues[group]
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
// COMPONENT 4: RISK-ADJUSTED METRICS (15%)
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
// COMPONENT 5: REGIME & ROBUSTNESS (10%)
// =============================================================================
// Adaptive + sanity check, not gatekeeper.

func calculateRegimeRobustnessScore(ctx models.PortfolioContext, sequence []models.ActionCandidate) float64 {
	// Market regime alignment
	regimeScore := calculateRegimeAlignmentScore(ctx, sequence)

	// Robustness (simplified - sequence coherence check)
	robustnessScore := calculateSequenceCoherenceScore(sequence)

	// Combine
	return regimeScore*0.6 + robustnessScore*0.4
}

// calculateRegimeAlignmentScore checks if actions align with market regime
func calculateRegimeAlignmentScore(ctx models.PortfolioContext, sequence []models.ActionCandidate) float64 {
	regime := ctx.MarketRegimeScore // -1 (bear) to +1 (bull)

	if len(sequence) == 0 {
		return 0.5
	}

	// Count buy vs sell actions
	buys := 0
	sells := 0
	for _, action := range sequence {
		if action.Side.IsBuy() {
			buys++
		} else {
			sells++
		}
	}

	totalActions := buys + sells
	if totalActions == 0 {
		return 0.5
	}

	buyRatio := float64(buys) / float64(totalActions)

	// In bull market: buying is aligned
	// In bear market: selling is aligned
	// In neutral: both are okay
	var alignmentScore float64
	if regime > 0.3 { // Bull
		alignmentScore = 0.5 + buyRatio*0.5 // More buys = better
	} else if regime < -0.3 { // Bear
		alignmentScore = 0.5 + (1-buyRatio)*0.5 // More sells = better
	} else { // Neutral
		alignmentScore = 0.7 // Both are acceptable
	}

	return alignmentScore
}

// calculateSequenceCoherenceScore checks if sequence is coherent
func calculateSequenceCoherenceScore(sequence []models.ActionCandidate) float64 {
	if len(sequence) == 0 {
		return 0.5
	}

	// Check for contradictory actions (buy and sell same symbol)
	symbolActions := make(map[string]struct {
		buys  int
		sells int
	})

	for _, action := range sequence {
		entry := symbolActions[action.Symbol]
		if action.Side.IsBuy() {
			entry.buys++
		} else {
			entry.sells++
		}
		symbolActions[action.Symbol] = entry
	}

	// Penalize contradictory actions
	contradictions := 0
	for _, entry := range symbolActions {
		if entry.buys > 0 && entry.sells > 0 {
			contradictions++
		}
	}

	if len(symbolActions) == 0 {
		return 0.5
	}

	coherenceRatio := 1.0 - float64(contradictions)/float64(len(symbolActions))
	return coherenceRatio
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
// DIVERSIFICATION SCORE (for backwards compatibility)
// =============================================================================

// CalculateDiversificationScore calculates diversification score for a portfolio.
// This is kept for backwards compatibility with existing code.
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

	// Evaluate end state with unified scoring
	score := EvaluateEndState(
		endPortfolio,
		sequence,
		context.TransactionCostFixed,
		context.TransactionCostPercent,
		context.CostPenaltyFactor,
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
