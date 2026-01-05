package evaluation

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestCalculateTransactionCost(t *testing.T) {
	sequence := []ActionCandidate{
		{ValueEUR: 1000.0},
		{ValueEUR: 500.0},
		{ValueEUR: -200.0}, // Negative value (should use absolute)
	}

	cost := CalculateTransactionCost(sequence, 2.0, 0.002)

	// Expected: 3 trades × 2.0 fixed = 6.0
	//           + (1000 + 500 + 200) × 0.002 = 3.4
	//           Total = 9.4
	expected := 6.0 + (1000.0+500.0+200.0)*0.002
	assert.InDelta(t, expected, cost, 0.01, "Transaction cost should be calculated correctly")
}

func TestCalculateDiversificationScore_EmptyPortfolio(t *testing.T) {
	portfolioContext := PortfolioContext{
		Positions:       make(map[string]float64),
		TotalValue:      0.0,
		CountryWeights:  make(map[string]float64),
		IndustryWeights: make(map[string]float64),
	}

	score := CalculateDiversificationScore(portfolioContext)

	assert.Equal(t, 0.5, score, "Empty portfolio should return neutral score")
}

func TestCalculateDiversificationScore_PerfectAllocation(t *testing.T) {
	// Perfect geographic allocation
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"US_STOCK": 600.0,
			"EU_STOCK": 400.0,
		},
		TotalValue: 1000.0,
		CountryWeights: map[string]float64{
			"NORTH_AMERICA": 0.6,
			"EUROPE":        0.4,
		},
		IndustryWeights: map[string]float64{},
		SecurityCountries: map[string]string{
			"US_STOCK": "United States",
			"EU_STOCK": "Germany",
		},
		CountryToGroup: map[string]string{
			"United States": "NORTH_AMERICA",
			"Germany":       "EUROPE",
		},
	}

	score := CalculateDiversificationScore(portfolioContext)

	// Score should be high (close to 1.0) for perfect allocation
	assert.Greater(t, score, 0.7, "Perfect allocation should have high score")
}

func TestCalculateDiversificationScore_ImbalancedAllocation(t *testing.T) {
	// Heavily imbalanced allocation (90% US, 10% EU, targets are 60/40)
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"US_STOCK": 900.0,
			"EU_STOCK": 100.0,
		},
		TotalValue: 1000.0,
		CountryWeights: map[string]float64{
			"NORTH_AMERICA": 0.6,
			"EUROPE":        0.4,
		},
		IndustryWeights: map[string]float64{},
		SecurityCountries: map[string]string{
			"US_STOCK": "United States",
			"EU_STOCK": "Germany",
		},
		CountryToGroup: map[string]string{
			"United States": "NORTH_AMERICA",
			"Germany":       "EUROPE",
		},
	}

	score := CalculateDiversificationScore(portfolioContext)

	// Score should be lower for imbalanced allocation
	assert.Less(t, score, 0.7, "Imbalanced allocation should have lower score")
}

func TestEvaluateEndState_BasicScore(t *testing.T) {
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"AAPL": 500.0,
			"MSFT": 500.0,
		},
		TotalValue: 1000.0,
		CountryWeights: map[string]float64{
			"NORTH_AMERICA": 1.0,
		},
		IndustryWeights: map[string]float64{},
		SecurityCountries: map[string]string{
			"AAPL": "United States",
			"MSFT": "United States",
		},
		CountryToGroup: map[string]string{
			"United States": "NORTH_AMERICA",
		},
	}

	sequence := []ActionCandidate{
		{ValueEUR: 100.0},
	}

	score := EvaluateEndState(
		portfolioContext,
		sequence,
		2.0,   // Fixed cost
		0.002, // Percent cost
		0.0,   // No cost penalty
	)

	assert.Greater(t, score, 0.0, "Score should be positive")
	assert.LessOrEqual(t, score, 1.0, "Score should not exceed 1.0")
}

func TestEvaluateEndState_WithCostPenalty(t *testing.T) {
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"AAPL": 500.0,
		},
		TotalValue:      500.0,
		CountryWeights:  make(map[string]float64),
		IndustryWeights: make(map[string]float64),
	}

	sequence := []ActionCandidate{
		{ValueEUR: 100.0},
		{ValueEUR: 100.0},
		{ValueEUR: 100.0},
	}

	scoreWithoutPenalty := EvaluateEndState(
		portfolioContext,
		sequence,
		2.0,
		0.002,
		0.0, // No penalty
	)

	scoreWithPenalty := EvaluateEndState(
		portfolioContext,
		sequence,
		2.0,
		0.002,
		1.0, // High penalty
	)

	assert.Less(t, scoreWithPenalty, scoreWithoutPenalty, "Score with penalty should be lower")
}

func TestEvaluateSequence_Feasible(t *testing.T) {
	context := EvaluationContext{
		PortfolioContext: PortfolioContext{
			Positions:       make(map[string]float64),
			TotalValue:      1000.0,
			CountryWeights:  make(map[string]float64),
			IndustryWeights: make(map[string]float64),
		},
		AvailableCashEUR:       1000.0,
		Securities:             []Security{},
		TransactionCostFixed:   2.0,
		TransactionCostPercent: 0.002,
	}

	sequence := []ActionCandidate{
		{
			Side:     TradeSideBuy,
			Symbol:   "AAPL",
			ValueEUR: 500.0,
		},
	}

	result := EvaluateSequence(sequence, context)

	assert.True(t, result.Feasible, "Sequence should be feasible")
	assert.Greater(t, result.Score, 0.0, "Score should be positive for feasible sequence")
	assert.Equal(t, 500.0, result.EndCashEUR, "End cash should reflect purchase")
}

func TestEvaluateSequence_Infeasible(t *testing.T) {
	context := EvaluationContext{
		PortfolioContext: PortfolioContext{
			Positions:       make(map[string]float64),
			TotalValue:      1000.0,
			CountryWeights:  make(map[string]float64),
			IndustryWeights: make(map[string]float64),
		},
		AvailableCashEUR:       500.0,
		Securities:             []Security{},
		TransactionCostFixed:   2.0,
		TransactionCostPercent: 0.002,
	}

	sequence := []ActionCandidate{
		{
			Side:     TradeSideBuy,
			Symbol:   "AAPL",
			ValueEUR: 1000.0, // Can't afford
		},
	}

	result := EvaluateSequence(sequence, context)

	assert.False(t, result.Feasible, "Sequence should be infeasible")
	assert.Equal(t, 0.0, result.Score, "Score should be 0 for infeasible sequence")
}

// ============================================================================
// Multi-Objective Evaluation Tests
// ============================================================================

func TestCalculateExpectedReturnScore_HighTotalReturn(t *testing.T) {
	// High quality securities with good dividends = high total return
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"HIGH_QUALITY": 600.0,
			"DIVIDEND_STOCK": 400.0,
		},
		TotalValue: 1000.0,
		SecurityScores: map[string]float64{
			"HIGH_QUALITY":  0.85, // High quality ≈ 12.75% CAGR estimate
			"DIVIDEND_STOCK": 0.70, // Medium quality ≈ 10.5% CAGR estimate
		},
		SecurityDividends: map[string]float64{
			"HIGH_QUALITY":  0.02, // 2% dividend
			"DIVIDEND_STOCK": 0.05, // 5% dividend
		},
	}

	score := calculateExpectedReturnScore(portfolioContext)

	// Weighted CAGR: (0.85*0.15*0.6) + (0.70*0.15*0.4) = 0.0765 + 0.042 = 0.1185 (11.85%)
	// Weighted dividend: (0.02*0.6) + (0.05*0.4) = 0.012 + 0.02 = 0.032 (3.2%)
	// Total return: 11.85% + 3.2% = 15.05% (should score high, >0.8)
	assert.Greater(t, score, 0.7, "High total return should score well")
	assert.LessOrEqual(t, score, 1.0, "Score should be capped at 1.0")
}

func TestCalculateExpectedReturnScore_LowTotalReturn(t *testing.T) {
	// Low quality securities with low dividends = low total return
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"LOW_QUALITY": 1000.0,
		},
		TotalValue: 1000.0,
		SecurityScores: map[string]float64{
			"LOW_QUALITY": 0.40, // Low quality ≈ 6% CAGR estimate
		},
		SecurityDividends: map[string]float64{
			"LOW_QUALITY": 0.01, // 1% dividend
		},
	}

	score := calculateExpectedReturnScore(portfolioContext)

	// Total return: 6% + 1% = 7% (should score low, <0.5)
	assert.Less(t, score, 0.5, "Low total return should score low")
	assert.GreaterOrEqual(t, score, 0.0, "Score should be non-negative")
}

func TestCalculateExpectedReturnScore_EmptyPortfolio(t *testing.T) {
	portfolioContext := PortfolioContext{
		Positions:  make(map[string]float64),
		TotalValue: 0.0,
	}

	score := calculateExpectedReturnScore(portfolioContext)

	assert.Equal(t, 0.5, score, "Empty portfolio should return neutral score")
}

func TestCalculateRiskAdjustedScore_HighQuality(t *testing.T) {
	// High quality portfolio = good risk-adjusted returns
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"HIGH_QUALITY_1": 500.0,
			"HIGH_QUALITY_2": 500.0,
		},
		TotalValue: 1000.0,
		SecurityScores: map[string]float64{
			"HIGH_QUALITY_1": 0.85,
			"HIGH_QUALITY_2": 0.80,
		},
	}

	score := calculateRiskAdjustedScore(portfolioContext)

	// Weighted average: (0.85*0.5) + (0.80*0.5) = 0.825
	assert.InDelta(t, 0.825, score, 0.01, "High quality should score high")
}

func TestCalculateRiskAdjustedScore_LowQuality(t *testing.T) {
	// Low quality portfolio = poor risk-adjusted returns
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"LOW_QUALITY": 1000.0,
		},
		TotalValue: 1000.0,
		SecurityScores: map[string]float64{
			"LOW_QUALITY": 0.35,
		},
	}

	score := calculateRiskAdjustedScore(portfolioContext)

	assert.InDelta(t, 0.35, score, 0.01, "Low quality should score low")
}

func TestCalculateRiskAdjustedScore_NoQualityData(t *testing.T) {
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"NO_DATA": 1000.0,
		},
		TotalValue: 1000.0,
		SecurityScores: nil,
	}

	score := calculateRiskAdjustedScore(portfolioContext)

	assert.Equal(t, 0.5, score, "No quality data should return neutral score")
}

func TestCalculatePortfolioQualityScore(t *testing.T) {
	// Test that it uses the existing calculateQualityScore function
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"STOCK1": 600.0,
			"STOCK2": 400.0,
		},
		TotalValue: 1000.0,
		SecurityScores: map[string]float64{
			"STOCK1": 0.80,
			"STOCK2": 0.70,
		},
		SecurityDividends: map[string]float64{
			"STOCK1": 0.03,
			"STOCK2": 0.02,
		},
	}

	score := calculatePortfolioQualityScore(portfolioContext)

	// Should use calculateQualityScore which combines quality and dividends
	assert.Greater(t, score, 0.0, "Should have positive score")
	assert.LessOrEqual(t, score, 1.0, "Should be capped at 1.0")
}

func TestEvaluateEndStateEnhanced_MultiObjective(t *testing.T) {
	// Test that enhanced evaluation combines all objectives
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"HIGH_QUALITY": 1000.0,
		},
		TotalValue: 1000.0,
		CountryWeights: map[string]float64{
			"NORTH_AMERICA": 1.0,
		},
		IndustryWeights: make(map[string]float64),
		SecurityCountries: map[string]string{
			"HIGH_QUALITY": "United States",
		},
		CountryToGroup: map[string]string{
			"United States": "NORTH_AMERICA",
		},
		SecurityScores: map[string]float64{
			"HIGH_QUALITY": 0.85, // High quality
		},
		SecurityDividends: map[string]float64{
			"HIGH_QUALITY": 0.04, // 4% dividend
		},
	}

	sequence := []ActionCandidate{
		{ValueEUR: 100.0},
	}

	score := EvaluateEndStateEnhanced(
		portfolioContext,
		sequence,
		2.0,   // Fixed cost
		0.002, // Percent cost
		0.0,   // No cost penalty
	)

	// Should combine diversification (30%), expected return (30%), risk-adjusted (20%), quality (20%)
	assert.Greater(t, score, 0.0, "Score should be positive")
	assert.LessOrEqual(t, score, 1.0, "Score should not exceed 1.0")
}

func TestEvaluateEndStateEnhanced_BackwardCompatibility(t *testing.T) {
	// Test that EvaluateEndState calls EvaluateEndStateEnhanced (backward compatibility)
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"STOCK": 1000.0,
		},
		TotalValue:      1000.0,
		CountryWeights:  make(map[string]float64),
		IndustryWeights: make(map[string]float64),
	}

	sequence := []ActionCandidate{
		{ValueEUR: 100.0},
	}

	scoreOld := EvaluateEndState(
		portfolioContext,
		sequence,
		2.0,
		0.002,
		0.0,
	)

	scoreNew := EvaluateEndStateEnhanced(
		portfolioContext,
		sequence,
		2.0,
		0.002,
		0.0,
	)

	// Should return same score (backward compatibility)
	assert.Equal(t, scoreNew, scoreOld, "EvaluateEndState should call EvaluateEndStateEnhanced")
}

// ============================================================================
// Optimizer Alignment Tests
// ============================================================================

func TestCalculateOptimizerAlignment_PerfectAlignment(t *testing.T) {
	// Perfect alignment with optimizer targets
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"STOCK1": 400.0, // 40% of portfolio
			"STOCK2": 600.0, // 60% of portfolio
		},
		TotalValue: 1000.0,
		OptimizerTargetWeights: map[string]float64{
			"STOCK1": 0.40, // Target: 40%
			"STOCK2": 0.60, // Target: 60%
		},
	}

	score := calculateOptimizerAlignment(portfolioContext)

	// Perfect alignment (0 deviation) should score 1.0
	assert.InDelta(t, 1.0, score, 0.01, "Perfect alignment should score 1.0")
}

func TestCalculateOptimizerAlignment_GoodAlignment(t *testing.T) {
	// Good alignment (small deviations)
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"STOCK1": 420.0, // 42% (target: 40%, deviation: 2%)
			"STOCK2": 580.0, // 58% (target: 60%, deviation: 2%)
		},
		TotalValue: 1000.0,
		OptimizerTargetWeights: map[string]float64{
			"STOCK1": 0.40,
			"STOCK2": 0.60,
		},
	}

	score := calculateOptimizerAlignment(portfolioContext)

	// Average deviation: 2% → score should be high (>0.8)
	assert.Greater(t, score, 0.8, "Good alignment should score high")
}

func TestCalculateOptimizerAlignment_PoorAlignment(t *testing.T) {
	// Poor alignment (large deviations)
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"STOCK1": 200.0, // 20% (target: 40%, deviation: 20%)
			"STOCK2": 800.0, // 80% (target: 60%, deviation: 20%)
		},
		TotalValue: 1000.0,
		OptimizerTargetWeights: map[string]float64{
			"STOCK1": 0.40,
			"STOCK2": 0.60,
		},
	}

	score := calculateOptimizerAlignment(portfolioContext)

	// Average deviation: 20% → score should be 0.0 (20% / 0.20 = 1.0, so 1.0 - 1.0 = 0.0)
	assert.InDelta(t, 0.0, score, 0.01, "Poor alignment should score 0.0")
}

func TestCalculateOptimizerAlignment_ModerateDeviation(t *testing.T) {
	// Moderate deviation (10% average)
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"STOCK1": 300.0, // 30% (target: 40%, deviation: 10%)
			"STOCK2": 700.0, // 70% (target: 60%, deviation: 10%)
		},
		TotalValue: 1000.0,
		OptimizerTargetWeights: map[string]float64{
			"STOCK1": 0.40,
			"STOCK2": 0.60,
		},
	}

	score := calculateOptimizerAlignment(portfolioContext)

	// Average deviation: 10% → score should be 0.5 (10% / 0.20 = 0.5, so 1.0 - 0.5 = 0.5)
	assert.InDelta(t, 0.5, score, 0.05, "10% deviation should score 0.5")
}

func TestCalculateOptimizerAlignment_MissingPosition(t *testing.T) {
	// Target exists but position doesn't (should count as deviation)
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"STOCK1": 1000.0, // 100% (target: 40%, deviation: 60%)
		},
		TotalValue: 1000.0,
		OptimizerTargetWeights: map[string]float64{
			"STOCK1": 0.40,
			"STOCK2": 0.60, // Target exists but no position (deviation: 60%)
		},
	}

	score := calculateOptimizerAlignment(portfolioContext)

	// Average deviation: (60% + 60%) / 2 = 60% → score should be 0.0
	assert.InDelta(t, 0.0, score, 0.01, "Missing positions should be penalized")
}

func TestCalculateOptimizerAlignment_NoTargets(t *testing.T) {
	// No optimizer targets available
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"STOCK1": 1000.0,
		},
		TotalValue:            1000.0,
		OptimizerTargetWeights: nil, // No targets
	}

	score := calculateOptimizerAlignment(portfolioContext)

	// Should return neutral score (0.5) when no targets available
	assert.Equal(t, 0.5, score, "No targets should return neutral score")
}

func TestCalculateOptimizerAlignment_EmptyPortfolio(t *testing.T) {
	// Empty portfolio
	portfolioContext := PortfolioContext{
		Positions:  make(map[string]float64),
		TotalValue: 0.0,
		OptimizerTargetWeights: map[string]float64{
			"STOCK1": 0.40,
		},
	}

	score := calculateOptimizerAlignment(portfolioContext)

	// Should return neutral score for empty portfolio
	assert.Equal(t, 0.5, score, "Empty portfolio should return neutral score")
}

func TestEvaluateEndStateEnhanced_WithOptimizerAlignment(t *testing.T) {
	// Test that optimizer alignment is included in enhanced evaluation
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"STOCK1": 400.0, // 40% (matches target)
			"STOCK2": 600.0, // 60% (matches target)
		},
		TotalValue: 1000.0,
		CountryWeights: map[string]float64{
			"NORTH_AMERICA": 1.0,
		},
		IndustryWeights: make(map[string]float64),
		SecurityCountries: map[string]string{
			"STOCK1": "United States",
			"STOCK2": "United States",
		},
		CountryToGroup: map[string]string{
			"United States": "NORTH_AMERICA",
		},
		SecurityScores: map[string]float64{
			"STOCK1": 0.80,
			"STOCK2": 0.75,
		},
		SecurityDividends: map[string]float64{
			"STOCK1": 0.03,
			"STOCK2": 0.04,
		},
		OptimizerTargetWeights: map[string]float64{
			"STOCK1": 0.40, // Perfect alignment
			"STOCK2": 0.60, // Perfect alignment
		},
	}

	sequence := []ActionCandidate{
		{ValueEUR: 100.0},
	}

	score := EvaluateEndStateEnhanced(
		portfolioContext,
		sequence,
		2.0,   // Fixed cost
		0.002, // Percent cost
		0.0,   // No cost penalty
	)

	// Should combine all objectives including optimizer alignment (25%)
	assert.Greater(t, score, 0.0, "Score should be positive")
	assert.LessOrEqual(t, score, 1.0, "Score should not exceed 1.0")
	// With perfect alignment, score should be higher than without
	assert.Greater(t, score, 0.7, "Perfect alignment should boost score")
}
