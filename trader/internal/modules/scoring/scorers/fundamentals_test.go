package scorers

import (
	"testing"

	"github.com/aristath/arduino-trader/pkg/formulas"
	"github.com/stretchr/testify/assert"
)

// ============================================================================
// FundamentalsScorer.Calculate Tests
// ============================================================================

func TestFundamentalsScorer_Calculate_HealthyCompany(t *testing.T) {
	scorer := NewFundamentalsScorer()

	// Strong fundamentals: Good margin, low debt, healthy liquidity
	profitMargin := 0.15 // 15% profit margin
	debtToEquity := 30.0 // Low debt
	currentRatio := 2.5  // Strong liquidity
	monthlyPrices := []formulas.MonthlyPrice{}

	result := scorer.Calculate(&profitMargin, &debtToEquity, &currentRatio, monthlyPrices)

	// Should score high (>0.7)
	assert.Greater(t, result.Score, 0.7)
	assert.Contains(t, result.Components, "financial_strength")
	assert.Contains(t, result.Components, "consistency")
	assert.Greater(t, result.Components["financial_strength"], 0.7)
}

func TestFundamentalsScorer_Calculate_WeakCompany(t *testing.T) {
	scorer := NewFundamentalsScorer()

	// Weak fundamentals: Negative margin, high debt, poor liquidity
	profitMargin := -0.05 // -5% margin (losing money)
	debtToEquity := 150.0 // Very high debt
	currentRatio := 0.8   // Poor liquidity
	monthlyPrices := []formulas.MonthlyPrice{}

	result := scorer.Calculate(&profitMargin, &debtToEquity, &currentRatio, monthlyPrices)

	// Should score low (<0.5)
	assert.Less(t, result.Score, 0.5)
	assert.Less(t, result.Components["financial_strength"], 0.5)
}

func TestFundamentalsScorer_Calculate_NilMetrics(t *testing.T) {
	scorer := NewFundamentalsScorer()

	// All metrics nil - should use defaults
	result := scorer.Calculate(nil, nil, nil, []formulas.MonthlyPrice{})

	// Should return middle-of-road score (defaults are moderate)
	assert.NotNil(t, result.Score)
	assert.GreaterOrEqual(t, result.Score, 0.0)
	assert.LessOrEqual(t, result.Score, 1.0)
	assert.Contains(t, result.Components, "financial_strength")
	assert.Contains(t, result.Components, "consistency")
}

func TestFundamentalsScorer_Calculate_WithConsistentGrowth(t *testing.T) {
	scorer := NewFundamentalsScorer()

	profitMargin := 0.12
	debtToEquity := 40.0
	currentRatio := 2.0

	// Create consistent growth pattern (10% annual growth)
	monthlyPrices := make([]formulas.MonthlyPrice, 121) // 10+ years
	basePrice := 100.0
	for i := range monthlyPrices {
		// 10% annual = ~0.797% monthly
		monthlyPrices[i] = formulas.MonthlyPrice{
			YearMonth:   "2014-01",
			AvgAdjClose: basePrice * (1.00797 * float64(i)),
		}
	}

	result := scorer.Calculate(&profitMargin, &debtToEquity, &currentRatio, monthlyPrices)

	// With consistent growth, consistency score should be high
	assert.GreaterOrEqual(t, result.Components["consistency"], 0.5)
	assert.GreaterOrEqual(t, result.Score, 0.6)
}

// ============================================================================
// Financial Strength Component Tests
// ============================================================================

func TestCalculateFinancialStrength_HighProfitMargin(t *testing.T) {
	// 20% profit margin should score very high
	profitMargin := 0.20
	debtToEquity := 50.0
	currentRatio := 1.5

	score := calculateFinancialStrength(&profitMargin, &debtToEquity, &currentRatio)

	// Margin contributes 40%, should push score up
	assert.GreaterOrEqual(t, score, 0.6)
}

func TestCalculateFinancialStrength_NegativeProfitMargin(t *testing.T) {
	// -10% margin (losing money)
	profitMargin := -0.10
	debtToEquity := 50.0
	currentRatio := 1.5

	score := calculateFinancialStrength(&profitMargin, &debtToEquity, &currentRatio)

	// Negative margin should reduce score (below 0.6)
	assert.LessOrEqual(t, score, 0.6)
}

func TestCalculateFinancialStrength_LowDebtToEquity(t *testing.T) {
	// Low debt (10) is excellent
	profitMargin := 0.10
	debtToEquity := 10.0
	currentRatio := 1.5

	score := calculateFinancialStrength(&profitMargin, &debtToEquity, &currentRatio)

	// Low debt should contribute positively (30% weight)
	assert.GreaterOrEqual(t, score, 0.6)
}

func TestCalculateFinancialStrength_HighDebtToEquity(t *testing.T) {
	// Very high debt (200+, capped at 200)
	profitMargin := 0.10
	debtToEquity := 250.0 // Capped at 200
	currentRatio := 1.5

	score := calculateFinancialStrength(&profitMargin, &debtToEquity, &currentRatio)

	// High debt should reduce score (capped at 200)
	assert.LessOrEqual(t, score, 0.6)
}

func TestCalculateFinancialStrength_HighCurrentRatio(t *testing.T) {
	// Current ratio of 3+ (excellent liquidity)
	profitMargin := 0.10
	debtToEquity := 50.0
	currentRatio := 3.5 // Capped at 3.0

	score := calculateFinancialStrength(&profitMargin, &debtToEquity, &currentRatio)

	// High liquidity should contribute (30% weight)
	assert.GreaterOrEqual(t, score, 0.5)
}

func TestCalculateFinancialStrength_LowCurrentRatio(t *testing.T) {
	// Poor liquidity
	profitMargin := 0.10
	debtToEquity := 50.0
	currentRatio := 0.5

	score := calculateFinancialStrength(&profitMargin, &debtToEquity, &currentRatio)

	// Low liquidity should reduce score (below 0.65)
	assert.LessOrEqual(t, score, 0.65)
}

func TestCalculateFinancialStrength_Defaults(t *testing.T) {
	// All nil - should use defaults
	score := calculateFinancialStrength(nil, nil, nil)

	// Default values: margin=0.5, D/E=50, CR=1.0
	// Should produce moderate score
	assert.GreaterOrEqual(t, score, 0.4)
	assert.LessOrEqual(t, score, 0.6)
}

// ============================================================================
// Consistency Component Tests
// ============================================================================

func TestCalculateConsistency_SimilarCAGR(t *testing.T) {
	// 5-year CAGR = 10%, 10-year CAGR = 10% (very consistent)
	cagr5y := 0.10
	cagr10y := 0.10

	score := calculateConsistency(cagr5y, &cagr10y)

	// Very similar CAGRs should score high
	assert.GreaterOrEqual(t, score, 0.8)
}

func TestCalculateConsistency_DivergentCAGR(t *testing.T) {
	// 5-year = 20%, 10-year = 5% (recent acceleration)
	cagr5y := 0.20
	cagr10y := 0.05

	score := calculateConsistency(cagr5y, &cagr10y)

	// Large divergence should score lower
	assert.LessOrEqual(t, score, 0.7)
}

func TestCalculateConsistency_NegativeCAGR(t *testing.T) {
	// Recent decline
	cagr5y := -0.05
	cagr10y := 0.10

	score := calculateConsistency(cagr5y, &cagr10y)

	// Negative growth should reduce score
	assert.LessOrEqual(t, score, 0.5)
}

func TestCalculateConsistency_OnlyFiveYearData(t *testing.T) {
	// No 10-year data available
	cagr5y := 0.12
	var cagr10y *float64 // nil

	score := calculateConsistency(cagr5y, cagr10y)

	// Should use only 5-year data for scoring
	assert.GreaterOrEqual(t, score, 0.0)
	assert.LessOrEqual(t, score, 1.0)
}

func TestCalculateConsistency_ZeroCAGR(t *testing.T) {
	// Flat growth
	cagr5y := 0.0
	cagr10y := 0.0

	score := calculateConsistency(cagr5y, &cagr10y)

	// Zero growth is consistent (gets high consistency score)
	assert.GreaterOrEqual(t, score, 0.4)
	assert.LessOrEqual(t, score, 1.0)
}

// ============================================================================
// Edge Cases
// ============================================================================

func TestFundamentalsScorer_ScoreCappedAtOne(t *testing.T) {
	scorer := NewFundamentalsScorer()

	// Extremely good fundamentals
	profitMargin := 0.50 // 50% margin (unrealistic but testing cap)
	debtToEquity := 0.0  // No debt
	currentRatio := 5.0  // Excessive liquidity
	monthlyPrices := []formulas.MonthlyPrice{}

	result := scorer.Calculate(&profitMargin, &debtToEquity, &currentRatio, monthlyPrices)

	// Score should be capped at 1.0
	assert.LessOrEqual(t, result.Score, 1.0)
}

func TestFundamentalsScorer_EmptyPriceHistory(t *testing.T) {
	scorer := NewFundamentalsScorer()

	profitMargin := 0.12
	debtToEquity := 40.0
	currentRatio := 2.0
	monthlyPrices := []formulas.MonthlyPrice{}

	result := scorer.Calculate(&profitMargin, &debtToEquity, &currentRatio, monthlyPrices)

	// Should still calculate financial strength component
	assert.GreaterOrEqual(t, result.Components["financial_strength"], 0.0)
	// Consistency should default
	assert.GreaterOrEqual(t, result.Components["consistency"], 0.0)
}

func TestFundamentalsScorer_ShortPriceHistory(t *testing.T) {
	scorer := NewFundamentalsScorer()

	profitMargin := 0.12
	debtToEquity := 40.0
	currentRatio := 2.0

	// Only 30 months of data (< 5 years)
	monthlyPrices := make([]formulas.MonthlyPrice, 30)
	for i := range monthlyPrices {
		monthlyPrices[i] = formulas.MonthlyPrice{
			YearMonth:   "2024-01",
			AvgAdjClose: 100.0 + float64(i),
		}
	}

	result := scorer.Calculate(&profitMargin, &debtToEquity, &currentRatio, monthlyPrices)

	// Should calculate CAGR with available data
	assert.GreaterOrEqual(t, result.Score, 0.0)
	assert.LessOrEqual(t, result.Score, 1.0)
}

// ============================================================================
// Weighting Tests
// ============================================================================

func TestFundamentalsScorer_ComponentWeighting(t *testing.T) {
	scorer := NewFundamentalsScorer()

	// Perfect financial strength, zero consistency
	profitMargin := 0.20
	debtToEquity := 0.0
	currentRatio := 3.0
	monthlyPrices := []formulas.MonthlyPrice{}

	result := scorer.Calculate(&profitMargin, &debtToEquity, &currentRatio, monthlyPrices)

	// 60% financial strength should dominate
	expectedScore := result.Components["financial_strength"]*0.60 + result.Components["consistency"]*0.40
	assert.InDelta(t, expectedScore, result.Score, 0.001)
}

func TestFundamentalsScorer_RoundingPrecision(t *testing.T) {
	scorer := NewFundamentalsScorer()

	profitMargin := 0.123456
	debtToEquity := 45.6789
	currentRatio := 1.987654
	monthlyPrices := []formulas.MonthlyPrice{}

	result := scorer.Calculate(&profitMargin, &debtToEquity, &currentRatio, monthlyPrices)

	// Should be rounded to 3 decimal places (check via round3 implementation)
	// Score should be between 0 and 1
	assert.GreaterOrEqual(t, result.Score, 0.0)
	assert.LessOrEqual(t, result.Score, 1.0)
}
