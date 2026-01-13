// Package evaluation provides evaluation functionality for security sequences.
// This package delegates to internal/evaluation for the actual scoring logic
// to maintain a single source of truth for evaluation weights and algorithms.
package evaluation

import (
	"math"

	coreevaluation "github.com/aristath/sentinel/internal/evaluation"
	coremodels "github.com/aristath/sentinel/internal/evaluation/models"
)

// =============================================================================
// CONSTANTS - Re-exported from core evaluation
// =============================================================================

const (
	// Main evaluation component weights (pure end-state scoring)
	WeightPortfolioQuality         = coreevaluation.WeightPortfolioQuality
	WeightDiversificationAlignment = coreevaluation.WeightDiversificationAlignment
	WeightRiskAdjustedMetrics      = coreevaluation.WeightRiskAdjustedMetrics
	WeightEndStateImprovement      = coreevaluation.WeightEndStateImprovement

	GeoWeight             = 0.40
	IndustryWeight        = 0.30
	QualityWeight         = 0.30
	DeviationScale        = 0.3
	SecurityQualityWeight = 0.6
	DividendYieldWeight   = 0.4
)

// =============================================================================
// TYPE CONVERSION UTILITIES
// =============================================================================

// convertToCorePorfolioContext converts local PortfolioContext to core models.PortfolioContext
func convertToCorePortfolioContext(ctx PortfolioContext) coremodels.PortfolioContext {
	return coremodels.PortfolioContext{
		CountryWeights:         ctx.CountryWeights,
		IndustryWeights:        ctx.IndustryWeights,
		Positions:              ctx.Positions,
		SecurityCountries:      ctx.SecurityCountries,
		SecurityIndustries:     ctx.SecurityIndustries,
		SecurityScores:         ctx.SecurityScores,
		SecurityDividends:      ctx.SecurityDividends,
		CountryToGroup:         ctx.CountryToGroup,
		IndustryToGroup:        ctx.IndustryToGroup,
		PositionAvgPrices:      ctx.PositionAvgPrices,
		CurrentPrices:          ctx.CurrentPrices,
		TotalValue:             ctx.TotalValue,
		SecurityCAGRs:          ctx.SecurityCAGRs,
		SecurityVolatility:     ctx.SecurityVolatility,
		SecuritySharpe:         ctx.SecuritySharpe,
		SecuritySortino:        ctx.SecuritySortino,
		SecurityMaxDrawdown:    ctx.SecurityMaxDrawdown,
		MarketRegimeScore:      ctx.MarketRegimeScore,
		OptimizerTargetWeights: ctx.OptimizerTargetWeights,
	}
}

// convertToCoreSequence converts local ActionCandidate slice to core models
func convertToCoreSequence(sequence []ActionCandidate) []coremodels.ActionCandidate {
	result := make([]coremodels.ActionCandidate, len(sequence))
	for i, action := range sequence {
		result[i] = coremodels.ActionCandidate{
			Side:     coremodels.TradeSide(action.Side),
			ISIN:     action.ISIN,
			Symbol:   action.Symbol,
			Name:     action.Name,
			Currency: action.Currency,
			Reason:   action.Reason,
			Tags:     action.Tags,
			Quantity: action.Quantity,
			Price:    action.Price,
			ValueEUR: action.ValueEUR,
			Priority: action.Priority,
		}
	}
	return result
}

// convertFromCorePortfolioContext converts core models.PortfolioContext to local PortfolioContext
func convertFromCorePortfolioContext(ctx coremodels.PortfolioContext) PortfolioContext {
	return PortfolioContext{
		CountryWeights:         ctx.CountryWeights,
		IndustryWeights:        ctx.IndustryWeights,
		Positions:              ctx.Positions,
		SecurityCountries:      ctx.SecurityCountries,
		SecurityIndustries:     ctx.SecurityIndustries,
		SecurityScores:         ctx.SecurityScores,
		SecurityDividends:      ctx.SecurityDividends,
		CountryToGroup:         ctx.CountryToGroup,
		IndustryToGroup:        ctx.IndustryToGroup,
		PositionAvgPrices:      ctx.PositionAvgPrices,
		CurrentPrices:          ctx.CurrentPrices,
		TotalValue:             ctx.TotalValue,
		SecurityCAGRs:          ctx.SecurityCAGRs,
		SecurityVolatility:     ctx.SecurityVolatility,
		SecuritySharpe:         ctx.SecuritySharpe,
		SecuritySortino:        ctx.SecuritySortino,
		SecurityMaxDrawdown:    ctx.SecurityMaxDrawdown,
		MarketRegimeScore:      ctx.MarketRegimeScore,
		OptimizerTargetWeights: ctx.OptimizerTargetWeights,
	}
}

// =============================================================================
// MAIN EVALUATION FUNCTIONS - Delegate to core evaluation
// =============================================================================

// GetRegimeAdaptiveWeights returns evaluation weights adjusted for market regime.
// Delegates to core evaluation package.
func GetRegimeAdaptiveWeights(regimeScore float64) map[string]float64 {
	return coreevaluation.GetRegimeAdaptiveWeights(regimeScore)
}

// CalculateTransactionCost calculates total transaction cost for a sequence.
// Delegates to core evaluation package.
func CalculateTransactionCost(
	sequence []ActionCandidate,
	transactionCostFixed float64,
	transactionCostPercent float64,
) float64 {
	coreSequence := convertToCoreSequence(sequence)
	return coreevaluation.CalculateTransactionCost(coreSequence, transactionCostFixed, transactionCostPercent)
}

// CalculateTransactionCostEnhanced calculates total transaction cost with all components.
// Delegates to core evaluation package.
func CalculateTransactionCostEnhanced(
	sequence []ActionCandidate,
	transactionCostFixed float64,
	transactionCostPercent float64,
	spreadCostPercent float64,
	slippagePercent float64,
	marketImpactPercent float64,
) float64 {
	coreSequence := convertToCoreSequence(sequence)
	return coreevaluation.CalculateTransactionCostEnhanced(
		coreSequence,
		transactionCostFixed,
		transactionCostPercent,
		spreadCostPercent,
		slippagePercent,
		marketImpactPercent,
	)
}

// EvaluateEndState evaluates the end state of a portfolio after executing a sequence.
// Delegates to core evaluation package for unified scoring.
// Now uses pure end-state scoring with start context for improvement calculation.
func EvaluateEndState(
	startContext PortfolioContext,
	endContext PortfolioContext,
	sequence []ActionCandidate,
	transactionCostFixed float64,
	transactionCostPercent float64,
	costPenaltyFactor float64,
) float64 {
	coreStartContext := convertToCorePortfolioContext(startContext)
	coreEndContext := convertToCorePortfolioContext(endContext)
	coreSequence := convertToCoreSequence(sequence)
	return coreevaluation.EvaluateEndState(
		coreStartContext,
		coreEndContext,
		coreSequence,
		transactionCostFixed,
		transactionCostPercent,
		costPenaltyFactor,
		nil, // Use default scoring config (temperament config would need to be passed through)
	)
}

// CalculateDiversificationScore calculates diversification score for a portfolio.
// Delegates to core evaluation package.
func CalculateDiversificationScore(ctx PortfolioContext) float64 {
	coreContext := convertToCorePortfolioContext(ctx)
	return coreevaluation.CalculateDiversificationScore(coreContext)
}

// EvaluateSequence evaluates a complete sequence: simulate + score.
// Delegates to core evaluation package.
func EvaluateSequence(
	sequence []ActionCandidate,
	context EvaluationContext,
) SequenceEvaluationResult {
	// Convert to core types
	coreSequence := convertToCoreSequence(sequence)
	coreContext := coremodels.EvaluationContext{
		PortfolioContext:       convertToCorePortfolioContext(context.PortfolioContext),
		CurrentPrices:          context.CurrentPrices,
		PriceAdjustments:       context.PriceAdjustments,
		AvailableCashEUR:       context.AvailableCashEUR,
		TotalPortfolioValueEUR: context.TotalPortfolioValueEUR,
		TransactionCostFixed:   context.TransactionCostFixed,
		TransactionCostPercent: context.TransactionCostPercent,
		CostPenaltyFactor:      context.CostPenaltyFactor,
	}

	// Convert securities
	coreSecurities := make([]coremodels.Security, len(context.Securities))
	for i, sec := range context.Securities {
		coreSecurities[i] = coremodels.Security{
			ISIN:     sec.ISIN,
			Symbol:   sec.Symbol,
			Name:     sec.Name,
			Country:  sec.Country,
			Industry: sec.Industry,
			Currency: sec.Currency,
		}
	}
	coreContext.Securities = coreSecurities

	// Convert positions
	corePositions := make([]coremodels.Position, len(context.Positions))
	for i, pos := range context.Positions {
		corePositions[i] = coremodels.Position{
			Symbol:         pos.Symbol,
			Currency:       pos.Currency,
			Quantity:       pos.Quantity,
			AvgPrice:       pos.AvgPrice,
			CurrencyRate:   pos.CurrencyRate,
			CurrentPrice:   pos.CurrentPrice,
			MarketValueEUR: pos.MarketValueEUR,
		}
	}
	coreContext.Positions = corePositions

	// Build stocks by symbol map
	stocksBySymbol := make(map[string]coremodels.Security)
	for _, sec := range coreSecurities {
		stocksBySymbol[sec.Symbol] = sec
	}
	coreContext.StocksBySymbol = stocksBySymbol

	// Call core evaluation
	coreResult := coreevaluation.EvaluateSequence(coreSequence, coreContext)

	// Convert result back
	return SequenceEvaluationResult{
		EndPortfolio:     convertFromCorePortfolioContext(coreResult.EndPortfolio),
		Sequence:         sequence,
		Score:            coreResult.Score,
		EndCashEUR:       coreResult.EndCashEUR,
		TransactionCosts: coreResult.TransactionCosts,
		Feasible:         coreResult.Feasible,
	}
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

// sum is a helper function to sum a slice of floats
func sum(values []float64) float64 {
	total := 0.0
	for _, v := range values {
		total += v
	}
	return total
}

// Note: CheckSequenceFeasibility and SimulateSequence are defined in simulation.go

// =============================================================================
// Expose internal scoring functions for tests
// =============================================================================

// calculateOptimizerAlignment is exposed for testing
func calculateOptimizerAlignment(ctx PortfolioContext, totalValue float64) float64 {
	if len(ctx.OptimizerTargetWeights) == 0 {
		return 0.5
	}

	var deviations []float64
	for symbol, targetWeight := range ctx.OptimizerTargetWeights {
		currentValue, hasPosition := ctx.Positions[symbol]
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
	return math.Max(0.0, 1.0-avgDeviation/0.20)
}

// calculatePortfolioQualityScore is exposed for testing
func calculatePortfolioQualityScore(ctx PortfolioContext) float64 {
	coreContext := convertToCorePortfolioContext(ctx)
	// Use same context for start and end to get base quality score
	return coreevaluation.EvaluateEndState(coreContext, coreContext, nil, 0, 0, 0, nil)
}

// calculateRiskAdjustedScore is exposed for testing - returns neutral if no data
func calculateRiskAdjustedScore(ctx PortfolioContext) float64 {
	if ctx.TotalValue <= 0 {
		return 0.5
	}

	// Check if we have any Sharpe data
	hasSharpe := false
	for _, v := range ctx.SecuritySharpe {
		if v != 0 {
			hasSharpe = true
			break
		}
	}

	if !hasSharpe || len(ctx.SecuritySharpe) == 0 {
		return 0.5
	}

	// Calculate weighted Sharpe
	weightedSharpe := 0.0
	for symbol, value := range ctx.Positions {
		weight := value / ctx.TotalValue
		if sharpe, ok := ctx.SecuritySharpe[symbol]; ok {
			weightedSharpe += sharpe * weight
		}
	}

	// Convert to score
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

// The new scoring is purely based on portfolio end state quality.
