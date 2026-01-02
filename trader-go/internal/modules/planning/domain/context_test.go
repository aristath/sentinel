package domain

import (
	"testing"

	"github.com/aristath/arduino-trader/internal/domain"
	scoringdomain "github.com/aristath/arduino-trader/internal/modules/scoring/domain"
	"github.com/stretchr/testify/assert"
)

func TestNewOpportunityContext(t *testing.T) {
	portfolioCtx := &scoringdomain.PortfolioContext{}
	positions := []domain.Position{
		{Symbol: "AAPL", Quantity: 10},
		{Symbol: "GOOGL", Quantity: 5},
	}
	securities := []domain.Security{
		{Symbol: "AAPL", Name: "Apple Inc."},
		{Symbol: "GOOGL", Name: "Alphabet Inc."},
	}
	availableCash := 1000.0
	totalValue := 5000.0
	currentPrices := map[string]float64{
		"AAPL":  150.0,
		"GOOGL": 2800.0,
	}

	ctx := NewOpportunityContext(
		portfolioCtx,
		positions,
		securities,
		availableCash,
		totalValue,
		currentPrices,
	)

	assert.NotNil(t, ctx)
	assert.Equal(t, portfolioCtx, ctx.PortfolioContext)
	assert.Equal(t, positions, ctx.Positions)
	assert.Equal(t, securities, ctx.Securities)
	assert.Equal(t, availableCash, ctx.AvailableCashEUR)
	assert.Equal(t, totalValue, ctx.TotalPortfolioValueEUR)
	assert.Equal(t, currentPrices, ctx.CurrentPrices)

	// Check that stocks by symbol map is built correctly
	assert.Len(t, ctx.StocksBySymbol, 2)
	assert.Equal(t, "Apple Inc.", ctx.StocksBySymbol["AAPL"].Name)
	assert.Equal(t, "Alphabet Inc.", ctx.StocksBySymbol["GOOGL"].Name)

	// Check default values
	assert.NotNil(t, ctx.IneligibleSymbols)
	assert.NotNil(t, ctx.RecentlySold)
	assert.NotNil(t, ctx.RecentlyBought)
	assert.Equal(t, 2.0, ctx.TransactionCostFixed)
	assert.Equal(t, 0.002, ctx.TransactionCostPercent)
	assert.True(t, ctx.AllowSell)
	assert.True(t, ctx.AllowBuy)
}

func TestNewEvaluationContext(t *testing.T) {
	portfolioCtx := &scoringdomain.PortfolioContext{}
	positions := []domain.Position{
		{Symbol: "AAPL", Quantity: 10},
	}
	securities := []domain.Security{
		{Symbol: "AAPL", Name: "Apple Inc."},
	}
	availableCash := 1000.0
	totalValue := 5000.0
	currentPrices := map[string]float64{
		"AAPL": 150.0,
	}

	ctx := NewEvaluationContext(
		portfolioCtx,
		positions,
		securities,
		availableCash,
		totalValue,
		currentPrices,
	)

	assert.NotNil(t, ctx)
	assert.Equal(t, portfolioCtx, ctx.PortfolioContext)
	assert.Equal(t, positions, ctx.Positions)
	assert.Equal(t, securities, ctx.Securities)
	assert.Equal(t, availableCash, ctx.AvailableCashEUR)
	assert.Equal(t, totalValue, ctx.TotalPortfolioValueEUR)
	assert.Equal(t, currentPrices, ctx.CurrentPrices)

	// Check that stocks by symbol map is built correctly
	assert.Len(t, ctx.StocksBySymbol, 1)
	assert.Equal(t, "Apple Inc.", ctx.StocksBySymbol["AAPL"].Name)

	// Check default values
	assert.Equal(t, 2.0, ctx.TransactionCostFixed)
	assert.Equal(t, 0.002, ctx.TransactionCostPercent)
}

func TestNewPlanningContext(t *testing.T) {
	opportunityCtx := &OpportunityContext{
		AvailableCashEUR: 1000.0,
	}
	evaluationCtx := &EvaluationContext{
		AvailableCashEUR: 1000.0,
	}

	ctx := NewPlanningContext(opportunityCtx, evaluationCtx)

	assert.NotNil(t, ctx)
	assert.Equal(t, opportunityCtx, ctx.OpportunityContext)
	assert.Equal(t, evaluationCtx, ctx.EvaluationContext)

	// Check default values
	assert.Equal(t, 5, ctx.MaxDepth)
	assert.Equal(t, 5, ctx.MaxOpportunitiesPerCategory)
	assert.Equal(t, 0.3, ctx.PriorityThreshold)
	assert.True(t, ctx.EnableDiverseSelection)
	assert.Equal(t, 0.3, ctx.DiversityWeight)
	assert.Equal(t, 10, ctx.BeamWidth)
	assert.Equal(t, "single_objective", ctx.EvaluationMode)
	assert.Equal(t, 100, ctx.MonteCarloPathCount)
	assert.True(t, ctx.EnableCombinatorial)
	assert.True(t, ctx.EnableAdaptivePatterns)

	// Check stochastic shifts
	assert.Len(t, ctx.StochasticShifts, 5)
	assert.Contains(t, ctx.StochasticShifts, -0.10)
	assert.Contains(t, ctx.StochasticShifts, -0.05)
	assert.Contains(t, ctx.StochasticShifts, 0.0)
	assert.Contains(t, ctx.StochasticShifts, 0.05)
	assert.Contains(t, ctx.StochasticShifts, 0.10)
}

func TestFromOpportunityContext(t *testing.T) {
	portfolioCtx := &scoringdomain.PortfolioContext{}
	positions := []domain.Position{
		{Symbol: "AAPL", Quantity: 10},
	}
	securities := []domain.Security{
		{Symbol: "AAPL", Name: "Apple Inc."},
	}
	availableCash := 1000.0
	totalValue := 5000.0
	currentPrices := map[string]float64{
		"AAPL": 150.0,
	}

	opportunityCtx := NewOpportunityContext(
		portfolioCtx,
		positions,
		securities,
		availableCash,
		totalValue,
		currentPrices,
	)

	planningCtx := FromOpportunityContext(opportunityCtx)

	assert.NotNil(t, planningCtx)
	assert.Equal(t, opportunityCtx, planningCtx.OpportunityContext)
	assert.NotNil(t, planningCtx.EvaluationContext)

	// Check that evaluation context was created from same data
	assert.Equal(t, availableCash, planningCtx.EvaluationContext.AvailableCashEUR)
	assert.Equal(t, totalValue, planningCtx.EvaluationContext.TotalPortfolioValueEUR)
	assert.Len(t, planningCtx.EvaluationContext.StocksBySymbol, 1)

	// Check default planning settings
	assert.Equal(t, 5, planningCtx.MaxDepth)
	assert.Equal(t, 5, planningCtx.MaxOpportunitiesPerCategory)
	assert.Equal(t, 0.3, planningCtx.PriorityThreshold)
}
