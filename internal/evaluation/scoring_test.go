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
		Positions:        make(map[string]float64),
		TotalValue:       0.0,
		GeographyWeights: make(map[string]float64),
		IndustryWeights:  make(map[string]float64),
	}

	score := CalculateDiversificationScore(portfolioContext)

	assert.Equal(t, 0.5, score, "Empty portfolio should return neutral score")
}

func TestCalculateDiversificationScore_PerfectAllocation(t *testing.T) {
	// Perfect geographic allocation - geography weights now match security geographies directly
	portfolioContext := models.PortfolioContext{
		Positions: map[string]float64{
			"US_STOCK": 600.0,
			"EU_STOCK": 400.0,
		},
		TotalValue: 1000.0,
		GeographyWeights: map[string]float64{
			"US": 0.6, // Direct geography values, no group mapping
			"EU": 0.4,
		},
		IndustryWeights: map[string]float64{},
		SecurityGeographies: map[string]string{
			"US_STOCK": "US",
			"EU_STOCK": "EU",
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
		GeographyWeights: map[string]float64{
			"US": 0.6,
			"EU": 0.4,
		},
		IndustryWeights: map[string]float64{},
		SecurityGeographies: map[string]string{
			"US_STOCK": "US",
			"EU_STOCK": "EU",
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
		GeographyWeights: map[string]float64{
			"US": 1.0,
		},
		IndustryWeights: map[string]float64{},
		SecurityGeographies: map[string]string{
			"AAPL": "US",
			"MSFT": "US",
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
		TotalValue:       500.0,
		GeographyWeights: make(map[string]float64),
		IndustryWeights:  make(map[string]float64),
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
			Positions:        make(map[string]float64),
			TotalValue:       1000.0,
			GeographyWeights: make(map[string]float64),
			IndustryWeights:  make(map[string]float64),
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
			Positions:        make(map[string]float64),
			TotalValue:       1000.0,
			GeographyWeights: make(map[string]float64),
			IndustryWeights:  make(map[string]float64),
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
		GeographyWeights: map[string]float64{
			"US": 1.0,
		},
		IndustryWeights: map[string]float64{},
		SecurityGeographies: map[string]string{
			"AAPL": "US",
			"MSFT": "US",
		},
	}

	startContext := models.PortfolioContext{
		Positions: map[string]float64{
			"AAPL": 600.0,
			"MSFT": 400.0,
		},
		TotalValue: 1000.0,
		GeographyWeights: map[string]float64{
			"US": 1.0,
		},
		IndustryWeights: map[string]float64{},
		SecurityGeographies: map[string]string{
			"AAPL": "US",
			"MSFT": "US",
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
		GeographyWeights: map[string]float64{
			"US": 0.5,
			"EU": 0.5,
		},
		IndustryWeights: map[string]float64{},
		SecurityGeographies: map[string]string{
			"AAPL": "US",
			"SAP":  "Germany",
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
		GeographyWeights: map[string]float64{
			"US": 0.5,
			"EU": 0.5,
		},
		IndustryWeights: map[string]float64{},
		SecurityGeographies: map[string]string{
			"AAPL": "US",
			"SAP":  "Germany",
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
		GeographyWeights: map[string]float64{
			"US": 0.5,
			"EU": 0.5,
		},
		IndustryWeights: map[string]float64{},
		SecurityGeographies: map[string]string{
			"AAPL": "US",
			"MSFT": "EU",
		},
	}

	// End with better diversification (closer to 50/50)
	endBetter := models.PortfolioContext{
		Positions: map[string]float64{
			"AAPL": 500.0,
			"MSFT": 500.0,
		},
		TotalValue: 1000.0,
		GeographyWeights: map[string]float64{
			"US": 0.5,
			"EU": 0.5,
		},
		IndustryWeights: map[string]float64{},
		SecurityGeographies: map[string]string{
			"AAPL": "US",
			"MSFT": "EU",
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
		TotalValue:       1000.0,
		GeographyWeights: map[string]float64{},
		IndustryWeights:  map[string]float64{},
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
		GeographyWeights: map[string]float64{
			"US": 1.0,
		},
		IndustryWeights: map[string]float64{},
		SecurityGeographies: map[string]string{
			"AAPL": "US",
			"MSFT": "US",
		},
	}
}

// =============================================================================
// MULTI-VALUE GEOGRAPHY/INDUSTRY TESTS
// =============================================================================
// These tests verify that comma-separated geography and industry values
// are properly parsed and split across multiple categories.

func TestCalculateGeoDiversification_MultiGeography(t *testing.T) {
	// Security with multiple geographies should split its value across all of them
	portfolioContext := models.PortfolioContext{
		Positions: map[string]float64{
			"VT":  600.0, // Global ETF with multiple geographies
			"SPY": 400.0, // US-only ETF
		},
		TotalValue: 1000.0,
		GeographyWeights: map[string]float64{
			"US":     0.5,
			"Europe": 0.3,
			"Asia":   0.2,
		},
		SecurityGeographies: map[string]string{
			"VT":  "US, Europe, Asia", // Comma-separated geographies
			"SPY": "US",
		},
	}

	score := CalculateDiversificationScore(portfolioContext)

	// VT's €600 should be split: €200 each to US, Europe, Asia
	// SPY's €400 goes entirely to US
	// Expected allocations: US=€600/€1000=60%, Europe=€200/€1000=20%, Asia=€200/€1000=20%
	// Target: US=50%, Europe=30%, Asia=20%
	// This is reasonably well-balanced, so score should be decent
	assert.Greater(t, score, 0.3, "Multi-geography security should contribute to diversification")
}

func TestCalculateGeoDiversification_SingleVsMultiGeography(t *testing.T) {
	// Compare a well-diversified portfolio using multi-geo securities
	// vs. one using single-geo securities

	// Portfolio using multi-geo security
	multiGeoContext := models.PortfolioContext{
		Positions: map[string]float64{
			"VT": 1000.0, // Global ETF covering all geographies
		},
		TotalValue: 1000.0,
		GeographyWeights: map[string]float64{
			"US":     0.4,
			"Europe": 0.3,
			"Asia":   0.3,
		},
		SecurityGeographies: map[string]string{
			"VT": "US, Europe, Asia", // Equal split to all 3
		},
	}

	// Portfolio using single-geo securities that match targets
	singleGeoContext := models.PortfolioContext{
		Positions: map[string]float64{
			"SPY": 400.0, // US only
			"VGK": 300.0, // Europe only
			"VPL": 300.0, // Asia only
		},
		TotalValue: 1000.0,
		GeographyWeights: map[string]float64{
			"US":     0.4,
			"Europe": 0.3,
			"Asia":   0.3,
		},
		SecurityGeographies: map[string]string{
			"SPY": "US",
			"VGK": "Europe",
			"VPL": "Asia",
		},
	}

	multiScore := CalculateDiversificationScore(multiGeoContext)
	singleScore := CalculateDiversificationScore(singleGeoContext)

	// Both should have positive scores
	assert.Greater(t, multiScore, 0.0, "Multi-geo portfolio should have positive score")
	assert.Greater(t, singleScore, 0.0, "Single-geo portfolio should have positive score")
}

func TestCalculateIndustryDiversification_MultiIndustry(t *testing.T) {
	// Security with multiple industries should split its value across all of them
	portfolioContext := models.PortfolioContext{
		Positions: map[string]float64{
			"GE":  600.0, // Conglomerate with multiple industries
			"XOM": 400.0, // Energy-only company
		},
		TotalValue: 1000.0,
		IndustryWeights: map[string]float64{
			"Industrial": 0.3,
			"Technology": 0.3,
			"Energy":     0.4,
		},
		SecurityIndustries: map[string]string{
			"GE":  "Industrial, Technology, Energy", // Comma-separated industries
			"XOM": "Energy",
		},
	}

	score := CalculateDiversificationScore(portfolioContext)

	// GE's €600 should be split: €200 each to Industrial, Technology, Energy
	// XOM's €400 goes entirely to Energy
	// Expected allocations: Industrial=€200/€1000=20%, Technology=€200/€1000=20%, Energy=€600/€1000=60%
	// This should produce a reasonable score
	assert.Greater(t, score, 0.0, "Multi-industry security should contribute to diversification")
}

func TestVerifyMultiGeoValueDistribution(t *testing.T) {
	// Test that a security with "US, Europe" geography
	// actually distributes value to both US and Europe, not to a single key "US, Europe"

	ctx := models.PortfolioContext{
		Positions: map[string]float64{
			"VT": 1000.0, // Global ETF
		},
		TotalValue: 1000.0,
		GeographyWeights: map[string]float64{
			"US":     0.5,
			"Europe": 0.5,
		},
		SecurityGeographies: map[string]string{
			"VT": "US, Europe", // Comma-separated!
		},
	}

	// If parsing works correctly:
	// - VT's €1000 should split: €500 to US, €500 to Europe
	// - US allocation: 500/1000 = 50% (matches target 50%)
	// - Europe allocation: 500/1000 = 50% (matches target 50%)
	// - Diversification component should score high

	// If parsing DOESN'T work (bug):
	// - VT's €1000 goes to key "US, Europe" (the raw string)
	// - US allocation: 0/1000 = 0% (target 50%)
	// - Europe allocation: 0/1000 = 0% (target 50%)
	// - Score should be very low

	score := CalculateDiversificationScore(ctx)

	// This assertion will FAIL if multi-geo parsing is broken
	// Score should be reasonable if multi-geo works (value distributed to both US and Europe)
	assert.Greater(t, score, 0.6,
		"Multi-geo security with perfect target match should have good score - if this fails, parsing is broken")
}

func TestCalculateGeoDiversification_EmptyGeographyTreatedAsOther(t *testing.T) {
	portfolioContext := models.PortfolioContext{
		Positions: map[string]float64{
			"AAPL": 500.0,
			"XYZ":  500.0, // Unknown company with no geography
		},
		TotalValue: 1000.0,
		GeographyWeights: map[string]float64{
			"US":    0.5,
			"OTHER": 0.5,
		},
		SecurityGeographies: map[string]string{
			"AAPL": "US",
			"XYZ":  "", // Empty geography should be treated as OTHER
		},
	}

	score := CalculateDiversificationScore(portfolioContext)

	// Should handle empty geography gracefully
	assert.GreaterOrEqual(t, score, 0.0, "Empty geography should be handled gracefully")
}

func TestCalculateIndustryDiversification_EmptyIndustryTreatedAsOther(t *testing.T) {
	portfolioContext := models.PortfolioContext{
		Positions: map[string]float64{
			"AAPL": 500.0,
			"XYZ":  500.0, // Unknown company with no industry
		},
		TotalValue: 1000.0,
		IndustryWeights: map[string]float64{
			"Technology": 0.5,
			"OTHER":      0.5,
		},
		SecurityIndustries: map[string]string{
			"AAPL": "Technology",
			"XYZ":  "", // Empty industry should be treated as OTHER
		},
	}

	score := CalculateDiversificationScore(portfolioContext)

	// Should handle empty industry gracefully
	assert.GreaterOrEqual(t, score, 0.0, "Empty industry should be handled gracefully")
}
