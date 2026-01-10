package domain

import (
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	scoringdomain "github.com/aristath/sentinel/internal/modules/scoring/domain"
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

	// Check that stocks by ISIN map is built correctly (old test needs ISINs)
	// Note: This test uses old data without ISINs - in real code all securities have ISINs
	assert.Len(t, ctx.StocksByISIN, 0) // No ISINs in test data, so map should be empty

	// Check default values
	assert.NotNil(t, ctx.IneligibleISINs)
	assert.NotNil(t, ctx.RecentlySoldISINs)
	assert.NotNil(t, ctx.RecentlyBoughtISINs)
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

	// Check that stocks by ISIN map is built correctly (old test needs ISINs)
	// Note: This test uses old data without ISINs - in real code all securities have ISINs
	assert.Len(t, ctx.StocksByISIN, 0) // No ISINs in test data, so map should be empty

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
	assert.True(t, ctx.EnableDiverseSelection)
	assert.Equal(t, 0.3, ctx.DiversityWeight)
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
	assert.Len(t, planningCtx.EvaluationContext.StocksByISIN, 0) // No ISINs in test data

	// Check default planning settings
	assert.Equal(t, 5, planningCtx.MaxDepth)
	assert.Equal(t, 5, planningCtx.MaxOpportunitiesPerCategory)
}

// TestNewOpportunityContext_ISINKeys verifies that OpportunityContext uses ISIN keys for all maps
func TestNewOpportunityContext_ISINKeys(t *testing.T) {
	securities := []domain.Security{
		{ISIN: "US0378331005", Symbol: "AAPL.US", Name: "Apple Inc."},
		{ISIN: "US5949181045", Symbol: "MSFT.US", Name: "Microsoft Corp."},
	}

	positions := []domain.Position{
		{ISIN: "US0378331005", Symbol: "AAPL.US", Quantity: 10},
	}

	currentPrices := map[string]float64{
		"US0378331005": 150.0, // ISIN key
		"US5949181045": 300.0,
	}

	ctx := NewOpportunityContext(
		nil, // portfolioContext
		positions,
		securities,
		1000.0, // availableCashEUR
		2500.0, // totalPortfolioValueEUR
		currentPrices,
	)

	// Verify maps initialized correctly
	assert.NotNil(t, ctx.IneligibleISINs, "IneligibleISINs should be initialized")
	assert.NotNil(t, ctx.RecentlySoldISINs, "RecentlySoldISINs should be initialized")
	assert.NotNil(t, ctx.RecentlyBoughtISINs, "RecentlyBoughtISINs should be initialized")
	assert.Equal(t, currentPrices, ctx.CurrentPrices, "CurrentPrices should match input")

	// Verify StocksByISIN populated correctly
	assert.Contains(t, ctx.StocksByISIN, "US0378331005", "Should contain AAPL ISIN")
	assert.Equal(t, "Apple Inc.", ctx.StocksByISIN["US0378331005"].Name, "Should have correct name")
	assert.Contains(t, ctx.StocksByISIN, "US5949181045", "Should contain MSFT ISIN")
	assert.Len(t, ctx.StocksByISIN, 2, "Should have 2 securities")
}

// TestOpportunityContext_NoSymbolKeys verifies no Symbol keys exist in internal maps
func TestOpportunityContext_NoSymbolKeys(t *testing.T) {
	securities := []domain.Security{
		{ISIN: "US0378331005", Symbol: "AAPL.US", Name: "Apple Inc."},
		{ISIN: "US5949181045", Symbol: "MSFT.US", Name: "Microsoft Corp."},
	}

	positions := []domain.Position{
		{ISIN: "US0378331005", Symbol: "AAPL.US", Quantity: 10},
	}

	currentPrices := map[string]float64{
		"US0378331005": 150.0, // ISIN key
		"US5949181045": 300.0,
	}

	securityScores := map[string]float64{
		"US0378331005": 85.0, // ISIN key
		"US5949181045": 90.0,
	}

	targetWeights := map[string]float64{
		"US0378331005": 0.40, // ISIN key
		"US5949181045": 0.60,
	}

	ctx := NewOpportunityContext(
		nil,
		positions,
		securities,
		1000.0,
		2500.0,
		currentPrices,
	)
	ctx.SecurityScores = securityScores
	ctx.TargetWeights = targetWeights

	// Helper to check if a string looks like an ISIN (12 chars, starts with 2 letters)
	isISIN := func(s string) bool {
		if len(s) != 12 {
			return false
		}
		// ISINs start with 2 letter country code
		for i := 0; i < 2; i++ {
			if s[i] < 'A' || s[i] > 'Z' {
				return false
			}
		}
		return true
	}

	// Verify all keys in CurrentPrices are ISINs
	for key := range ctx.CurrentPrices {
		assert.True(t, isISIN(key), "CurrentPrices key should be ISIN, got: %s", key)
	}

	// Verify all keys in SecurityScores are ISINs
	for key := range ctx.SecurityScores {
		assert.True(t, isISIN(key), "SecurityScores key should be ISIN, got: %s", key)
	}

	// Verify all keys in TargetWeights are ISINs
	for key := range ctx.TargetWeights {
		assert.True(t, isISIN(key), "TargetWeights key should be ISIN, got: %s", key)
	}

	// Verify all keys in StocksByISIN are ISINs
	for key := range ctx.StocksByISIN {
		assert.True(t, isISIN(key), "StocksByISIN key should be ISIN, got: %s", key)
	}

	// Explicitly verify Symbol keys don't exist
	assert.NotContains(t, ctx.CurrentPrices, "AAPL.US", "CurrentPrices should NOT have Symbol keys")
	assert.NotContains(t, ctx.SecurityScores, "MSFT.US", "SecurityScores should NOT have Symbol keys")
	assert.NotContains(t, ctx.StocksByISIN, "AAPL.US", "StocksByISIN should NOT have Symbol keys")
}

// TestOpportunityContext_NoDualKeyDuplication verifies no dual-key duplication
func TestOpportunityContext_NoDualKeyDuplication(t *testing.T) {
	securities := []domain.Security{
		{ISIN: "US0378331005", Symbol: "AAPL.US", Name: "Apple Inc."},
		{ISIN: "US5949181045", Symbol: "MSFT.US", Name: "Microsoft Corp."},
		{ISIN: "US88160R1014", Symbol: "TSLA.US", Name: "Tesla Inc."},
	}

	securityScores := map[string]float64{
		"US0378331005": 85.0,
		"US5949181045": 90.0,
		"US88160R1014": 75.0,
	}

	ctx := NewOpportunityContext(
		nil,
		[]domain.Position{},
		securities,
		1000.0,
		2500.0,
		map[string]float64{},
	)
	ctx.SecurityScores = securityScores

	// If we have 3 securities, SecurityScores should have 3 keys, not 6
	assert.Equal(t, len(securities), len(ctx.SecurityScores),
		"SecurityScores should have exactly one key per security (no duplication)")

	// Verify map size matches security count
	assert.Equal(t, 3, len(ctx.SecurityScores), "Should have 3 scores for 3 securities")
	assert.Equal(t, 3, len(ctx.StocksByISIN), "Should have 3 entries in StocksByISIN")
}

// TestOpportunityContext_ConstraintMapsISINKeys verifies constraint maps use ISIN keys
func TestOpportunityContext_ConstraintMapsISINKeys(t *testing.T) {
	ctx := NewOpportunityContext(
		nil,
		[]domain.Position{},
		[]domain.Security{},
		1000.0,
		2500.0,
		map[string]float64{},
	)

	// Add entries to constraint maps (these would normally come from TradeRepository)
	ctx.RecentlyBoughtISINs["US0378331005"] = true
	ctx.RecentlySoldISINs["US5949181045"] = true
	ctx.IneligibleISINs["US88160R1014"] = true

	// Verify maps accept ISIN keys
	assert.True(t, ctx.RecentlyBoughtISINs["US0378331005"], "RecentlyBoughtISINs should accept ISIN keys")
	assert.True(t, ctx.RecentlySoldISINs["US5949181045"], "RecentlySoldISINs should accept ISIN keys")
	assert.True(t, ctx.IneligibleISINs["US88160R1014"], "IneligibleISINs should accept ISIN keys")

	// Verify Symbol keys don't work
	ctx.RecentlyBoughtISINs["AAPL.US"] = true // This should be a different entry
	assert.Len(t, ctx.RecentlyBoughtISINs, 2, "Symbol and ISIN should be separate keys")
}

// TestOpportunityContext_SecuritiesWithoutISIN tests handling of securities missing ISINs
func TestOpportunityContext_SecuritiesWithoutISIN(t *testing.T) {
	securities := []domain.Security{
		{ISIN: "US0378331005", Symbol: "AAPL.US", Name: "Apple Inc."},
		{ISIN: "", Symbol: "INVALID.US", Name: "Invalid Security"}, // No ISIN
	}

	ctx := NewOpportunityContext(
		nil,
		[]domain.Position{},
		securities,
		1000.0,
		2500.0,
		map[string]float64{},
	)

	// Should only have one entry in StocksByISIN (the one with ISIN)
	assert.Len(t, ctx.StocksByISIN, 1, "Should skip securities without ISIN")
	assert.Contains(t, ctx.StocksByISIN, "US0378331005", "Should have valid ISIN")
	assert.NotContains(t, ctx.StocksByISIN, "", "Should not have empty ISIN key")
}
