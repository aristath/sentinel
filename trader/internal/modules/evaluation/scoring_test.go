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
