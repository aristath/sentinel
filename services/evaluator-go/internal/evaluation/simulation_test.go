package evaluation

import (
	"testing"

	"github.com/aristath/arduino-trader/services/evaluator-go/internal/models"
	"github.com/stretchr/testify/assert"
)

func TestSimulateSequence_BuyAction(t *testing.T) {
	// Setup
	initialCash := 1000.0
	portfolioContext := models.PortfolioContext{
		Positions:       make(map[string]float64),
		TotalValue:      500.0,
		CountryWeights:  make(map[string]float64),
		IndustryWeights: make(map[string]float64),
	}

	securities := []models.Security{
		{
			Symbol:  "AAPL",
			Name:    "Apple Inc.",
			Country: stringPtr("United States"),
		},
	}

	// Create a BUY action
	buyAction := models.ActionCandidate{
		Side:     models.TradeSideBuy,
		Symbol:   "AAPL",
		Quantity: 10,
		Price:    150.0,
		ValueEUR: 1500.0,
		Currency: "USD",
	}

	sequence := []models.ActionCandidate{buyAction}

	// Execute
	endPortfolio, endCash := SimulateSequence(
		sequence,
		portfolioContext,
		initialCash,
		securities,
		nil, // No price adjustments
	)

	// Can't afford the full amount (only 1000 EUR available, need 1500)
	// Should skip the action
	assert.Equal(t, initialCash, endCash, "Cash should remain unchanged when buy is unaffordable")
	assert.Equal(t, 0.0, endPortfolio.Positions["AAPL"], "Position should not be created")
}

func TestSimulateSequence_AffordableBuy(t *testing.T) {
	// Setup
	initialCash := 2000.0
	portfolioContext := models.PortfolioContext{
		Positions:       make(map[string]float64),
		TotalValue:      500.0,
		CountryWeights:  make(map[string]float64),
		IndustryWeights: make(map[string]float64),
	}

	securities := []models.Security{
		{
			Symbol:  "AAPL",
			Name:    "Apple Inc.",
			Country: stringPtr("United States"),
		},
	}

	// Create an affordable BUY action
	buyAction := models.ActionCandidate{
		Side:     models.TradeSideBuy,
		Symbol:   "AAPL",
		Quantity: 10,
		Price:    150.0,
		ValueEUR: 1500.0,
		Currency: "USD",
	}

	sequence := []models.ActionCandidate{buyAction}

	// Execute
	endPortfolio, endCash := SimulateSequence(
		sequence,
		portfolioContext,
		initialCash,
		securities,
		nil,
	)

	// Assertions
	assert.Equal(t, 500.0, endCash, "Cash should decrease by buy value")
	assert.Equal(t, 1500.0, endPortfolio.Positions["AAPL"], "Position should be created with correct value")
	assert.Equal(t, "United States", endPortfolio.SecurityCountries["AAPL"], "Country should be set")
}

func TestSimulateSequence_SellAction(t *testing.T) {
	// Setup - portfolio with existing position
	initialCash := 1000.0
	portfolioContext := models.PortfolioContext{
		Positions: map[string]float64{
			"AAPL": 2000.0, // Existing position worth 2000 EUR
		},
		TotalValue:      3000.0,
		CountryWeights:  make(map[string]float64),
		IndustryWeights: make(map[string]float64),
		SecurityCountries: map[string]string{
			"AAPL": "United States",
		},
	}

	securities := []models.Security{
		{
			Symbol:  "AAPL",
			Name:    "Apple Inc.",
			Country: stringPtr("United States"),
		},
	}

	// Create a SELL action
	sellAction := models.ActionCandidate{
		Side:     models.TradeSideSell,
		Symbol:   "AAPL",
		Quantity: 5,
		Price:    150.0,
		ValueEUR: 750.0,
		Currency: "USD",
	}

	sequence := []models.ActionCandidate{sellAction}

	// Execute
	endPortfolio, endCash := SimulateSequence(
		sequence,
		portfolioContext,
		initialCash,
		securities,
		nil,
	)

	// Assertions
	assert.Equal(t, 1750.0, endCash, "Cash should increase by sell value")
	assert.Equal(t, 1250.0, endPortfolio.Positions["AAPL"], "Position should decrease by sell value")
}

func TestSimulateSequence_SellEntirePosition(t *testing.T) {
	// Setup
	initialCash := 1000.0
	portfolioContext := models.PortfolioContext{
		Positions: map[string]float64{
			"AAPL": 1500.0,
		},
		TotalValue:      2500.0,
		CountryWeights:  make(map[string]float64),
		IndustryWeights: make(map[string]float64),
	}

	securities := []models.Security{
		{
			Symbol:  "AAPL",
			Name:    "Apple Inc.",
			Country: stringPtr("United States"),
		},
	}

	// Sell entire position
	sellAction := models.ActionCandidate{
		Side:     models.TradeSideSell,
		Symbol:   "AAPL",
		Quantity: 10,
		Price:    150.0,
		ValueEUR: 1500.0,
		Currency: "USD",
	}

	sequence := []models.ActionCandidate{sellAction}

	// Execute
	endPortfolio, endCash := SimulateSequence(
		sequence,
		portfolioContext,
		initialCash,
		securities,
		nil,
	)

	// Assertions
	assert.Equal(t, 2500.0, endCash, "Cash should increase by full sell value")
	_, exists := endPortfolio.Positions["AAPL"]
	assert.False(t, exists, "Position should be removed when sold entirely")
}

func TestCheckSequenceFeasibility_Feasible(t *testing.T) {
	sequence := []models.ActionCandidate{
		{Side: models.TradeSideBuy, ValueEUR: 500.0},
		{Side: models.TradeSideBuy, ValueEUR: 300.0},
	}

	feasible := CheckSequenceFeasibility(
		sequence,
		1000.0, // Enough cash
		models.PortfolioContext{},
	)

	assert.True(t, feasible, "Sequence should be feasible with sufficient cash")
}

func TestCheckSequenceFeasibility_NotFeasible(t *testing.T) {
	sequence := []models.ActionCandidate{
		{Side: models.TradeSideBuy, ValueEUR: 500.0},
		{Side: models.TradeSideBuy, ValueEUR: 600.0},
	}

	feasible := CheckSequenceFeasibility(
		sequence,
		1000.0, // Not enough cash for both buys
		models.PortfolioContext{},
	)

	assert.False(t, feasible, "Sequence should be infeasible with insufficient cash")
}

func TestCheckSequenceFeasibility_SellThenBuy(t *testing.T) {
	sequence := []models.ActionCandidate{
		{Side: models.TradeSideSell, ValueEUR: 500.0},  // Adds 500
		{Side: models.TradeSideBuy, ValueEUR: 1200.0},  // Needs 1200, have 500+500=1000
	}

	feasible := CheckSequenceFeasibility(
		sequence,
		500.0, // Initial cash
		models.PortfolioContext{},
	)

	assert.False(t, feasible, "Sequence should be infeasible even with sell proceeds")
}

func TestCalculateSequenceCashFlow(t *testing.T) {
	sequence := []models.ActionCandidate{
		{Side: models.TradeSideSell, ValueEUR: 500.0},
		{Side: models.TradeSideBuy, ValueEUR: 300.0},
		{Side: models.TradeSideSell, ValueEUR: 200.0},
		{Side: models.TradeSideBuy, ValueEUR: 150.0},
	}

	cashFlow := CalculateSequenceCashFlow(sequence)

	assert.Equal(t, 700.0, cashFlow.CashGenerated, "Should sum all sells")
	assert.Equal(t, 450.0, cashFlow.CashRequired, "Should sum all buys")
	assert.Equal(t, 250.0, cashFlow.NetCashFlow, "Net flow should be positive")
}

// Helper function
func stringPtr(s string) *string {
	return &s
}
