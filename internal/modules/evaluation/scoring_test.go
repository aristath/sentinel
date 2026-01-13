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

	// Expected with enhanced calculation (includes spread and slippage):
	// 3 trades × 2.0 fixed = 6.0
	// + (1000 + 500 + 200) × 0.002 = 3.4 (variable cost)
	// + (1000 + 500 + 200) × 0.001 = 1.7 (spread cost, default 0.1%)
	// + (1000 + 500 + 200) × 0.0015 = 2.55 (slippage cost, default 0.15%)
	// Total = 6.0 + 3.4 + 1.7 + 2.55 = 13.65
	expected := 6.0 + (1000.0+500.0+200.0)*0.002 + (1000.0+500.0+200.0)*0.001 + (1000.0+500.0+200.0)*0.0015
	assert.InDelta(t, expected, cost, 0.01, "Transaction cost should be calculated correctly with spread and slippage")
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

	// Score should be reasonable for allocation (diversification is just one component now)
	assert.Greater(t, score, 0.3, "Perfect allocation should have reasonable score")
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

	// Pass same context for start and end (no change scenario)
	score := EvaluateEndState(
		portfolioContext, // Start
		portfolioContext, // End
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

	// Pass same context for start and end
	scoreWithoutPenalty := EvaluateEndState(
		portfolioContext, // Start
		portfolioContext, // End
		sequence,
		2.0,
		0.002,
		0.0, // No penalty
	)

	scoreWithPenalty := EvaluateEndState(
		portfolioContext, // Start
		portfolioContext, // End
		sequence,
		2.0,
		0.002,
		1.0, // High penalty
	)

	assert.Less(t, scoreWithPenalty, scoreWithoutPenalty, "Score with penalty should be lower")
}

func TestEvaluateSequence_Feasible(t *testing.T) {
	isin := "US0378331005" // AAPL ISIN
	context := EvaluationContext{
		PortfolioContext: PortfolioContext{
			Positions:       make(map[string]float64),
			TotalValue:      1000.0,
			CountryWeights:  make(map[string]float64),
			IndustryWeights: make(map[string]float64),
		},
		AvailableCashEUR: 1000.0,
		Securities: []Security{
			{
				ISIN:   isin,
				Symbol: "AAPL",
				Name:   "Apple Inc.",
			},
		},
		TransactionCostFixed:   2.0,
		TransactionCostPercent: 0.002,
	}

	sequence := []ActionCandidate{
		{
			Side:     TradeSideBuy,
			ISIN:     isin,
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
// Unified Evaluation Tests
// ============================================================================

func TestCalculatePortfolioQualityScore(t *testing.T) {
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

	assert.Greater(t, score, 0.0, "Should have positive score")
	assert.LessOrEqual(t, score, 1.0, "Should be capped at 1.0")
}

func TestCalculateRiskAdjustedScore_HighQuality(t *testing.T) {
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"HIGH_QUALITY_1": 500.0,
			"HIGH_QUALITY_2": 500.0,
		},
		TotalValue: 1000.0,
		SecuritySharpe: map[string]float64{
			"HIGH_QUALITY_1": 1.5,
			"HIGH_QUALITY_2": 1.8,
		},
	}

	score := calculateRiskAdjustedScore(portfolioContext)

	// High Sharpe should score well
	assert.Greater(t, score, 0.5, "High Sharpe should score well")
}

func TestCalculateRiskAdjustedScore_NoData(t *testing.T) {
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"NO_DATA": 1000.0,
		},
		TotalValue:     1000.0,
		SecuritySharpe: nil,
	}

	score := calculateRiskAdjustedScore(portfolioContext)

	assert.Equal(t, 0.5, score, "No data should return neutral score")
}

// ============================================================================
// Optimizer Alignment Tests
// ============================================================================

func TestCalculateOptimizerAlignment_PerfectAlignment(t *testing.T) {
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"STOCK1": 400.0,
			"STOCK2": 600.0,
		},
		TotalValue: 1000.0,
		OptimizerTargetWeights: map[string]float64{
			"STOCK1": 0.40,
			"STOCK2": 0.60,
		},
	}

	score := calculateOptimizerAlignment(portfolioContext, 1000.0)

	assert.InDelta(t, 1.0, score, 0.01, "Perfect alignment should score 1.0")
}

func TestCalculateOptimizerAlignment_GoodAlignment(t *testing.T) {
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"STOCK1": 420.0,
			"STOCK2": 580.0,
		},
		TotalValue: 1000.0,
		OptimizerTargetWeights: map[string]float64{
			"STOCK1": 0.40,
			"STOCK2": 0.60,
		},
	}

	score := calculateOptimizerAlignment(portfolioContext, 1000.0)

	assert.Greater(t, score, 0.8, "Good alignment should score high")
}

func TestCalculateOptimizerAlignment_PoorAlignment(t *testing.T) {
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"STOCK1": 200.0,
			"STOCK2": 800.0,
		},
		TotalValue: 1000.0,
		OptimizerTargetWeights: map[string]float64{
			"STOCK1": 0.40,
			"STOCK2": 0.60,
		},
	}

	score := calculateOptimizerAlignment(portfolioContext, 1000.0)

	assert.InDelta(t, 0.0, score, 0.01, "Poor alignment should score 0.0")
}

func TestCalculateOptimizerAlignment_NoTargets(t *testing.T) {
	portfolioContext := PortfolioContext{
		Positions: map[string]float64{
			"STOCK1": 1000.0,
		},
		TotalValue:             1000.0,
		OptimizerTargetWeights: nil,
	}

	score := calculateOptimizerAlignment(portfolioContext, 1000.0)

	assert.Equal(t, 0.5, score, "No targets should return neutral score")
}

// ============================================================================
// Regime Adaptive Weights Tests
// ============================================================================

func TestGetRegimeAdaptiveWeights_NeutralMarket(t *testing.T) {
	weights := GetRegimeAdaptiveWeights(0.0)

	// Pure end-state scoring weights
	assert.InDelta(t, WeightPortfolioQuality, weights["quality"], 0.01, "Quality should be 35% in neutral")
	assert.InDelta(t, WeightDiversificationAlignment, weights["diversification"], 0.01, "Diversification should be 30% in neutral")
	assert.InDelta(t, WeightRiskAdjustedMetrics, weights["risk"], 0.01, "Risk should be 25% in neutral")
	assert.InDelta(t, WeightEndStateImprovement, weights["improvement"], 0.01, "Improvement should be 10% in neutral")
}

func TestGetRegimeAdaptiveWeights_BullMarket(t *testing.T) {
	weights := GetRegimeAdaptiveWeights(0.8)

	// Bull market should increase quality, decrease risk
	assert.Greater(t, weights["quality"], WeightPortfolioQuality, "Quality should increase in bull")
	assert.Less(t, weights["risk"], WeightRiskAdjustedMetrics, "Risk should decrease in bull")
}

func TestGetRegimeAdaptiveWeights_BearMarket(t *testing.T) {
	weights := GetRegimeAdaptiveWeights(-0.8)

	// Bear market should decrease quality, increase risk
	assert.Less(t, weights["quality"], WeightPortfolioQuality, "Quality should decrease in bear")
	assert.Greater(t, weights["risk"], WeightRiskAdjustedMetrics, "Risk should increase in bear")
}

// NOTE: TestCalculateWindfallScore and TestCalculateActionPriorityScore have been removed
// as part of the pure end-state scoring refactor. These functions scored based on
// action characteristics, which is no longer part of the scoring philosophy.

// TestSum tests the sum helper function
func TestSum(t *testing.T) {
	tests := []struct {
		name     string
		values   []float64
		expected float64
	}{
		{
			name:     "empty slice",
			values:   []float64{},
			expected: 0.0,
		},
		{
			name:     "single value",
			values:   []float64{5.5},
			expected: 5.5,
		},
		{
			name:     "multiple positive values",
			values:   []float64{1.0, 2.5, 3.5, 4.0},
			expected: 11.0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := sum(tt.values)
			assert.InDelta(t, tt.expected, result, 0.0001)
		})
	}
}
