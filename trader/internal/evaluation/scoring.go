package evaluation

import (
	"math"

	"github.com/aristath/arduino-trader/internal/evaluation/models"
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
	sequence []models.ActionCandidate,
	transactionCostFixed float64,
	transactionCostPercent float64,
) float64 {
	totalCost := 0.0
	for _, action := range sequence {
		tradeCost := transactionCostFixed + math.Abs(action.ValueEUR)*transactionCostPercent
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
func CalculateDiversificationScore(portfolioContext models.PortfolioContext) float64 {
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
func calculateGeoDiversification(portfolioContext models.PortfolioContext, totalValue float64) float64 {
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
	var deviations []float64
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
func calculateIndustryDiversification(portfolioContext models.PortfolioContext, totalValue float64) float64 {
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
	var deviations []float64
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
func calculateQualityScore(portfolioContext models.PortfolioContext, totalValue float64) float64 {
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
	switch {
	case hasQuality && hasDividend:
		// Quality is 0-1, dividend is yield (normalize to 0-1 by capping at 10%)
		normalizedDividend := math.Min(1.0, weightedDividend*10)
		qualityScore = weightedQuality*SecurityQualityWeight + normalizedDividend*DividendYieldWeight
	case hasQuality:
		qualityScore = weightedQuality
	case hasDividend:
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
	// Calculate diversification score for end state
	divScore := CalculateDiversificationScore(endContext)

	// For MVP: Use diversification as the primary score
	// (In full implementation, this would combine total return, promise, stability, etc.)
	endScore := divScore

	// Calculate transaction cost
	totalCost := CalculateTransactionCost(sequence, transactionCostFixed, transactionCostPercent)

	// Apply transaction cost penalty if enabled
	if costPenaltyFactor > 0.0 && endContext.TotalValue > 0 {
		costPenalty := (totalCost / endContext.TotalValue) * costPenaltyFactor
		endScore = math.Max(0.0, endScore-costPenalty)
	}

	return math.Min(1.0, endScore)
}

// EvaluateSequence evaluates a complete sequence: simulate + score
//
// This is the main entry point for sequence evaluation that:
// 1. Simulates the sequence to get end state
// 2. Evaluates the end state to get a score
// 3. Returns the result
func EvaluateSequence(
	sequence []models.ActionCandidate,
	context models.EvaluationContext,
) models.SequenceEvaluationResult {
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

	// Evaluate end state to get score
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
