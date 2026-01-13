package evaluation

import (
	"testing"

	"github.com/aristath/sentinel/internal/evaluation/models"
	"github.com/stretchr/testify/assert"
)

func TestCalculateTransactionCost(t *testing.T) {
	sequence := []models.ActionCandidate{
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
	portfolioContext := models.PortfolioContext{
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
	portfolioContext := models.PortfolioContext{
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

	// Score should be reasonable for perfect geographic allocation
	// Note: diversification score now combines geo (35%), industry (30%), and optimizer (35%)
	// With only geo data provided, the score will be lower
	assert.Greater(t, score, 0.5, "Perfect geographic allocation should have reasonable score")
}

func TestCalculateDiversificationScore_ImbalancedAllocation(t *testing.T) {
	// Heavily imbalanced allocation (90% US, 10% EU, targets are 60/40)
	portfolioContext := models.PortfolioContext{
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
	portfolioContext := models.PortfolioContext{
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

	sequence := []models.ActionCandidate{
		{ValueEUR: 100.0},
	}

	// Use same context for start and end (no change scenario)
	score := EvaluateEndState(
		portfolioContext, // Start
		portfolioContext, // End (same as start)
		sequence,
		2.0,   // Fixed cost
		0.002, // Percent cost
		0.0,   // No cost penalty
		nil,   // Use default scoring config
	)

	assert.Greater(t, score, 0.0, "Score should be positive")
	assert.LessOrEqual(t, score, 1.0, "Score should not exceed 1.0")
}

func TestEvaluateEndState_WithCostPenalty(t *testing.T) {
	portfolioContext := models.PortfolioContext{
		Positions: map[string]float64{
			"AAPL": 500.0,
		},
		TotalValue:      500.0,
		CountryWeights:  make(map[string]float64),
		IndustryWeights: make(map[string]float64),
	}

	sequence := []models.ActionCandidate{
		{ValueEUR: 100.0},
		{ValueEUR: 100.0},
		{ValueEUR: 100.0},
	}

	// Use same context for start and end
	scoreWithoutPenalty := EvaluateEndState(
		portfolioContext, // Start
		portfolioContext, // End
		sequence,
		2.0,
		0.002,
		0.0, // No penalty
		nil, // Use default scoring config
	)

	scoreWithPenalty := EvaluateEndState(
		portfolioContext, // Start
		portfolioContext, // End
		sequence,
		2.0,
		0.002,
		1.0, // High penalty
		nil, // Use default scoring config
	)

	assert.Less(t, scoreWithPenalty, scoreWithoutPenalty, "Score with penalty should be lower")
}

func TestEvaluateSequence_Feasible(t *testing.T) {
	isin := "US0378331005" // AAPL ISIN
	context := models.EvaluationContext{
		PortfolioContext: models.PortfolioContext{
			Positions:       make(map[string]float64),
			TotalValue:      1000.0,
			CountryWeights:  make(map[string]float64),
			IndustryWeights: make(map[string]float64),
		},
		AvailableCashEUR: 1000.0,
		Securities: []models.Security{
			{
				ISIN:   isin,
				Symbol: "AAPL",
				Name:   "Apple Inc.",
			},
		},
		TransactionCostFixed:   2.0,
		TransactionCostPercent: 0.002,
	}

	sequence := []models.ActionCandidate{
		{
			Side:     models.TradeSideBuy,
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
	context := models.EvaluationContext{
		PortfolioContext: models.PortfolioContext{
			Positions:       make(map[string]float64),
			TotalValue:      1000.0,
			CountryWeights:  make(map[string]float64),
			IndustryWeights: make(map[string]float64),
		},
		AvailableCashEUR:       500.0,
		Securities:             []models.Security{},
		TransactionCostFixed:   2.0,
		TransactionCostPercent: 0.002,
	}

	sequence := []models.ActionCandidate{
		{
			Side:     models.TradeSideBuy,
			Symbol:   "AAPL",
			ValueEUR: 1000.0, // Can't afford
		},
	}

	result := EvaluateSequence(sequence, context)

	assert.False(t, result.Feasible, "Sequence should be infeasible")
	assert.Equal(t, 0.0, result.Score, "Score should be 0 for infeasible sequence")
}

// =============================================================================
// PURE END-STATE SCORING TESTS
// =============================================================================
// These tests verify that scoring is based ONLY on the end portfolio state,
// not on the characteristics of individual actions.

func TestScoringIsPureEndState(t *testing.T) {
	// Two identical end states should produce identical scores
	// regardless of how they were reached (number of actions, priorities, etc.)

	endContext := models.PortfolioContext{
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

	startContext := models.PortfolioContext{
		Positions: map[string]float64{
			"AAPL": 600.0,
			"MSFT": 400.0,
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

	// Single action to reach end state
	seq1 := []models.ActionCandidate{
		{Side: models.TradeSideSell, Symbol: "AAPL", ValueEUR: 100.0, Priority: 0.8},
	}

	// Multiple actions (high priority) to reach same end state
	seq2 := []models.ActionCandidate{
		{Side: models.TradeSideSell, Symbol: "AAPL", ValueEUR: 50.0, Priority: 0.9},
		{Side: models.TradeSideSell, Symbol: "AAPL", ValueEUR: 50.0, Priority: 0.9},
	}

	// Multiple actions (low priority) to reach same end state
	seq3 := []models.ActionCandidate{
		{Side: models.TradeSideSell, Symbol: "AAPL", ValueEUR: 25.0, Priority: 0.1},
		{Side: models.TradeSideSell, Symbol: "AAPL", ValueEUR: 25.0, Priority: 0.1},
		{Side: models.TradeSideSell, Symbol: "AAPL", ValueEUR: 25.0, Priority: 0.1},
		{Side: models.TradeSideSell, Symbol: "AAPL", ValueEUR: 25.0, Priority: 0.1},
	}

	// All sequences should score identically (except for transaction costs)
	// since they all result in the same end state
	score1 := EvaluateEndState(startContext, endContext, seq1, 2.0, 0.002, 0.0, nil)
	score2 := EvaluateEndState(startContext, endContext, seq2, 2.0, 0.002, 0.0, nil)
	score3 := EvaluateEndState(startContext, endContext, seq3, 2.0, 0.002, 0.0, nil)

	// Without cost penalty, scores should be identical
	assert.InDelta(t, score1, score2, 0.001, "Same end state with different action counts should score identically")
	assert.InDelta(t, score1, score3, 0.001, "Same end state with different priorities should score identically")
}

func TestScoringDoesNotUseActionPriority(t *testing.T) {
	// A sequence with low-priority actions should score the same as
	// one with high-priority actions if they produce identical end states

	startContext := createTestPortfolioContext(1000.0)
	endContext := createTestPortfolioContext(1000.0)

	highPrioritySeq := []models.ActionCandidate{
		{Side: models.TradeSideSell, Symbol: "AAPL", ValueEUR: 100.0, Priority: 0.99},
	}

	lowPrioritySeq := []models.ActionCandidate{
		{Side: models.TradeSideSell, Symbol: "AAPL", ValueEUR: 100.0, Priority: 0.01},
	}

	scoreHigh := EvaluateEndState(startContext, endContext, highPrioritySeq, 2.0, 0.002, 0.0, nil)
	scoreLow := EvaluateEndState(startContext, endContext, lowPrioritySeq, 2.0, 0.002, 0.0, nil)

	assert.Equal(t, scoreHigh, scoreLow, "Priority should not affect scoring - only end state matters")
}

func TestImprovementScoreRewardsProgress(t *testing.T) {
	// A sequence that improves diversification should score higher
	// than one that maintains or worsens it

	// Start: Poorly diversified portfolio (90% US, 10% Europe, target is 50/50)
	startPoor := models.PortfolioContext{
		Positions: map[string]float64{
			"AAPL": 900.0,
			"SAP":  100.0,
		},
		TotalValue: 1000.0,
		CountryWeights: map[string]float64{
			"NORTH_AMERICA": 0.5,
			"EUROPE":        0.5,
		},
		IndustryWeights: map[string]float64{},
		SecurityCountries: map[string]string{
			"AAPL": "United States",
			"SAP":  "Germany",
		},
		CountryToGroup: map[string]string{
			"United States": "NORTH_AMERICA",
			"Germany":       "EUROPE",
		},
		// Add some quality scores to differentiate
		SecurityScores: map[string]float64{
			"AAPL": 0.7,
			"SAP":  0.7,
		},
	}

	// End state 1: Well diversified (50/50, matches target)
	endBalanced := models.PortfolioContext{
		Positions: map[string]float64{
			"AAPL": 500.0,
			"SAP":  500.0,
		},
		TotalValue: 1000.0,
		CountryWeights: map[string]float64{
			"NORTH_AMERICA": 0.5,
			"EUROPE":        0.5,
		},
		IndustryWeights: map[string]float64{},
		SecurityCountries: map[string]string{
			"AAPL": "United States",
			"SAP":  "Germany",
		},
		CountryToGroup: map[string]string{
			"United States": "NORTH_AMERICA",
			"Germany":       "EUROPE",
		},
		SecurityScores: map[string]float64{
			"AAPL": 0.7,
			"SAP":  0.7,
		},
	}

	// End state 2: Still poorly diversified (same as start)
	endPoor := startPoor

	// Sequence that rebalances
	rebalanceSeq := []models.ActionCandidate{
		{Side: models.TradeSideSell, Symbol: "AAPL", ValueEUR: 400.0},
	}

	// Empty sequence (no change)
	emptySeq := []models.ActionCandidate{}

	scoreRebalance := EvaluateEndState(startPoor, endBalanced, rebalanceSeq, 2.0, 0.002, 0.0, nil)
	scoreNoChange := EvaluateEndState(startPoor, endPoor, emptySeq, 2.0, 0.002, 0.0, nil)

	assert.Greater(t, scoreRebalance, scoreNoChange,
		"Sequence that improves diversification should score higher than no change")
}

func TestEndStateImprovementCalculation(t *testing.T) {
	// Test the improvement score calculation directly

	// Start with poor diversification
	startPoor := models.PortfolioContext{
		Positions: map[string]float64{
			"AAPL": 900.0,
			"MSFT": 100.0,
		},
		TotalValue: 1000.0,
		CountryWeights: map[string]float64{
			"NORTH_AMERICA": 0.5,
			"EUROPE":        0.5,
		},
		IndustryWeights: map[string]float64{},
		SecurityCountries: map[string]string{
			"AAPL": "United States",
			"MSFT": "Germany",
		},
		CountryToGroup: map[string]string{
			"United States": "NORTH_AMERICA",
			"Germany":       "EUROPE",
		},
	}

	// End with better diversification (closer to 50/50)
	endBetter := models.PortfolioContext{
		Positions: map[string]float64{
			"AAPL": 500.0,
			"MSFT": 500.0,
		},
		TotalValue: 1000.0,
		CountryWeights: map[string]float64{
			"NORTH_AMERICA": 0.5,
			"EUROPE":        0.5,
		},
		IndustryWeights: map[string]float64{},
		SecurityCountries: map[string]string{
			"AAPL": "United States",
			"MSFT": "Germany",
		},
		CountryToGroup: map[string]string{
			"United States": "NORTH_AMERICA",
			"Germany":       "EUROPE",
		},
	}

	improvementScore := calculateEndStateImprovementScore(startPoor, endBetter)

	// Improvement score should be above 0.5 (neutral) when portfolio improves
	assert.Greater(t, improvementScore, 0.5,
		"Improvement score should be above neutral when diversification improves")
	assert.LessOrEqual(t, improvementScore, 1.0,
		"Improvement score should not exceed 1.0")
}

func TestNoImprovementReturnsNeutral(t *testing.T) {
	// Same start and end state should return neutral improvement score

	sameContext := models.PortfolioContext{
		Positions: map[string]float64{
			"AAPL": 500.0,
			"MSFT": 500.0,
		},
		TotalValue:      1000.0,
		CountryWeights:  map[string]float64{},
		IndustryWeights: map[string]float64{},
	}

	improvementScore := calculateEndStateImprovementScore(sameContext, sameContext)

	// Should be exactly 0.5 (neutral) for no change
	assert.InDelta(t, 0.5, improvementScore, 0.01,
		"No improvement should return neutral score (0.5)")
}

func TestNewWeightsSum(t *testing.T) {
	// Verify the new weights sum to 1.0
	total := WeightPortfolioQuality +
		WeightDiversificationAlignment +
		WeightRiskAdjustedMetrics +
		WeightEndStateImprovement

	assert.InDelta(t, 1.0, total, 0.001, "New weights should sum to 1.0")
}

// Helper function to create a test portfolio context
func createTestPortfolioContext(totalValue float64) models.PortfolioContext {
	return models.PortfolioContext{
		Positions: map[string]float64{
			"AAPL": totalValue * 0.5,
			"MSFT": totalValue * 0.5,
		},
		TotalValue: totalValue,
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
}
