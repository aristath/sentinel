package scorers

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

// ============================================================================
// DividendScorer.Calculate Tests
// ============================================================================

func TestDividendScorer_Calculate_HighYieldHighConsistency(t *testing.T) {
	scorer := NewDividendScorer()

	// Excellent dividend stock: 6%+ yield, ideal payout ratio
	dividendYield := 0.065      // 6.5% yield
	payoutRatio := 0.50         // 50% payout (ideal range)
	fiveYearAvgDivYield := 0.04 // 4% 5-year average

	result := scorer.Calculate(&dividendYield, &payoutRatio, &fiveYearAvgDivYield)

	// Should score very high (>0.9)
	assert.Greater(t, result.Score, 0.9)
	assert.Contains(t, result.Components, "yield")
	assert.Contains(t, result.Components, "consistency")
	assert.Greater(t, result.Components["yield"], 0.9)
	assert.Greater(t, result.Components["consistency"], 0.7)
}

func TestDividendScorer_Calculate_LowYield(t *testing.T) {
	scorer := NewDividendScorer()

	// Low dividend stock: 1% yield
	dividendYield := 0.01
	payoutRatio := 0.40
	fiveYearAvgDivYield := 0.01

	result := scorer.Calculate(&dividendYield, &payoutRatio, &fiveYearAvgDivYield)

	// Should score low on yield
	assert.LessOrEqual(t, result.Score, 0.6)
	assert.LessOrEqual(t, result.Components["yield"], 0.5)
}

func TestDividendScorer_Calculate_NoDividend(t *testing.T) {
	scorer := NewDividendScorer()

	// Growth stock with no dividend
	dividendYield := 0.0
	payoutRatio := 0.0
	fiveYearAvgDivYield := 0.0

	result := scorer.Calculate(&dividendYield, &payoutRatio, &fiveYearAvgDivYield)

	// Should get base score (0.3 for non-dividend stocks)
	assert.LessOrEqual(t, result.Score, 0.4)
	assert.Equal(t, 0.3, result.Components["yield"])
}

func TestDividendScorer_Calculate_NilMetrics(t *testing.T) {
	scorer := NewDividendScorer()

	// All nil - missing data
	result := scorer.Calculate(nil, nil, nil)

	// Should use defaults (base yield 0.3, default consistency 0.5)
	assert.NotNil(t, result.Score)
	assert.GreaterOrEqual(t, result.Score, 0.0)
	assert.LessOrEqual(t, result.Score, 1.0)
	assert.Equal(t, 0.3, result.Components["yield"])
}

func TestDividendScorer_Calculate_MidRangeYield(t *testing.T) {
	scorer := NewDividendScorer()

	// Mid-range dividend: 4% yield (between 3-6%)
	dividendYield := 0.04
	payoutRatio := 0.45
	fiveYearAvgDivYield := 0.03

	result := scorer.Calculate(&dividendYield, &payoutRatio, &fiveYearAvgDivYield)

	// Mid-range yield should score around 0.7-0.9
	assert.GreaterOrEqual(t, result.Score, 0.7)
	assert.LessOrEqual(t, result.Score, 0.95)
	assert.GreaterOrEqual(t, result.Components["yield"], 0.7)
	assert.LessOrEqual(t, result.Components["yield"], 0.9)
}

// ============================================================================
// Dividend Yield Component Tests
// ============================================================================

func TestScoreDividendYield_HighYield(t *testing.T) {
	// 7% yield (above 6% threshold)
	yield := 0.07
	score := scoreDividendYield(&yield)

	// Should score 1.0 (maximum)
	assert.Equal(t, 1.0, score)
}

func TestScoreDividendYield_ExactHighThreshold(t *testing.T) {
	// Exactly 6% yield
	yield := 0.06
	score := scoreDividendYield(&yield)

	// Should score 1.0
	assert.Equal(t, 1.0, score)
}

func TestScoreDividendYield_MidRange(t *testing.T) {
	// 4.5% yield (mid-range between 3-6%)
	yield := 0.045
	score := scoreDividendYield(&yield)

	// Should score between 0.7 and 1.0
	assert.GreaterOrEqual(t, score, 0.7)
	assert.LessOrEqual(t, score, 1.0)
}

func TestScoreDividendYield_ExactMidThreshold(t *testing.T) {
	// Exactly 3% yield
	yield := 0.03
	score := scoreDividendYield(&yield)

	// Should score 0.7 (bottom of mid range)
	assert.InDelta(t, 0.7, score, 0.01)
}

func TestScoreDividendYield_LowRange(t *testing.T) {
	// 2% yield (between 1-3%)
	yield := 0.02
	score := scoreDividendYield(&yield)

	// Should score between 0.4 and 0.7
	assert.GreaterOrEqual(t, score, 0.4)
	assert.LessOrEqual(t, score, 0.7)
}

func TestScoreDividendYield_VeryLowYield(t *testing.T) {
	// 0.5% yield (below 1%)
	yield := 0.005
	score := scoreDividendYield(&yield)

	// Should score between 0.3 and 0.4
	assert.GreaterOrEqual(t, score, 0.3)
	assert.LessOrEqual(t, score, 0.4)
}

func TestScoreDividendYield_ZeroYield(t *testing.T) {
	yield := 0.0
	score := scoreDividendYield(&yield)

	// Should get base score
	assert.Equal(t, 0.3, score)
}

func TestScoreDividendYield_NegativeYield(t *testing.T) {
	// Invalid negative yield
	yield := -0.02
	score := scoreDividendYield(&yield)

	// Should treat as no dividend
	assert.Equal(t, 0.3, score)
}

func TestScoreDividendYield_Nil(t *testing.T) {
	score := scoreDividendYield(nil)

	// Should get base score
	assert.Equal(t, 0.3, score)
}

// ============================================================================
// Dividend Consistency Component Tests
// ============================================================================

func TestScoreDividendConsistency_IdealPayoutRatio(t *testing.T) {
	// Perfect 50% payout ratio
	payoutRatio := 0.50
	fiveYearAvgDivYield := 0.03

	score := scoreDividendConsistency(&payoutRatio, &fiveYearAvgDivYield)

	// Ideal payout should contribute positively
	assert.GreaterOrEqual(t, score, 0.7)
}

func TestScoreDividendConsistency_LowPayoutRatio(t *testing.T) {
	// 20% payout (below ideal 30-60%)
	payoutRatio := 0.20
	fiveYearAvgDivYield := 0.03

	score := scoreDividendConsistency(&payoutRatio, &fiveYearAvgDivYield)

	// Low payout should reduce score slightly
	assert.GreaterOrEqual(t, score, 0.5)
	assert.LessOrEqual(t, score, 0.9)
}

func TestScoreDividendConsistency_HighPayoutRatio(t *testing.T) {
	// 85% payout (risky, above 80%)
	payoutRatio := 0.85
	fiveYearAvgDivYield := 0.03

	score := scoreDividendConsistency(&payoutRatio, &fiveYearAvgDivYield)

	// High payout is risky, should reduce score
	assert.LessOrEqual(t, score, 0.7)
}

func TestScoreDividendConsistency_ModerateHighPayout(t *testing.T) {
	// 70% payout (acceptable but not ideal)
	payoutRatio := 0.70
	fiveYearAvgDivYield := 0.03

	score := scoreDividendConsistency(&payoutRatio, &fiveYearAvgDivYield)

	// Should be decent but below ideal
	assert.GreaterOrEqual(t, score, 0.5)
	assert.LessOrEqual(t, score, 0.9)
}

func TestScoreDividendConsistency_StrongGrowth(t *testing.T) {
	// Strong 5-year dividend growth
	payoutRatio := 0.50
	fiveYearAvgDivYield := 0.10 // 10% 5-year average

	score := scoreDividendConsistency(&payoutRatio, &fiveYearAvgDivYield)

	// Strong growth should boost score
	assert.GreaterOrEqual(t, score, 0.8)
}

func TestScoreDividendConsistency_NegativeGrowth(t *testing.T) {
	// Declining dividends
	payoutRatio := 0.50
	fiveYearAvgDivYield := -0.02 // Negative growth

	score := scoreDividendConsistency(&payoutRatio, &fiveYearAvgDivYield)

	// Calculation: payoutScore=1.0 (0.50 in ideal range), growthScore=0.4 (0.5 + (-0.02)*5)
	// consistencyScore = 1.0*0.5 + 0.4*0.5 = 0.7
	// Negative growth should reduce score, but payout ratio is ideal
	assert.Equal(t, 0.7, score)
}

func TestScoreDividendConsistency_NilPayoutRatio(t *testing.T) {
	// Missing payout ratio data
	fiveYearAvgDivYield := 0.03

	score := scoreDividendConsistency(nil, &fiveYearAvgDivYield)

	// Should use default payout score (0.5)
	assert.GreaterOrEqual(t, score, 0.0)
	assert.LessOrEqual(t, score, 1.0)
}

func TestScoreDividendConsistency_NilGrowth(t *testing.T) {
	// Missing growth data
	payoutRatio := 0.50

	score := scoreDividendConsistency(&payoutRatio, nil)

	// Should use default growth score (0.5)
	assert.GreaterOrEqual(t, score, 0.0)
	assert.LessOrEqual(t, score, 1.0)
}

func TestScoreDividendConsistency_AllNil(t *testing.T) {
	// Missing all data
	score := scoreDividendConsistency(nil, nil)

	// Should use all defaults (0.5 each)
	assert.Equal(t, 0.5, score)
}

// ============================================================================
// Edge Cases
// ============================================================================

func TestDividendScorer_ScoreCappedAtOne(t *testing.T) {
	scorer := NewDividendScorer()

	// Extremely high dividend (10% yield, perfect consistency)
	dividendYield := 0.10
	payoutRatio := 0.50
	fiveYearAvgDivYield := 0.15

	result := scorer.Calculate(&dividendYield, &payoutRatio, &fiveYearAvgDivYield)

	// Should be capped at 1.0
	assert.LessOrEqual(t, result.Score, 1.0)
}

func TestDividendScorer_ComponentWeighting(t *testing.T) {
	scorer := NewDividendScorer()

	// Known values for manual calculation
	dividendYield := 0.05 // Mid-range yield
	payoutRatio := 0.50   // Ideal payout
	fiveYearAvgDivYield := 0.03

	result := scorer.Calculate(&dividendYield, &payoutRatio, &fiveYearAvgDivYield)

	// 70% yield, 30% consistency
	expectedScore := result.Components["yield"]*0.70 + result.Components["consistency"]*0.30
	assert.InDelta(t, expectedScore, result.Score, 0.001)
}

func TestDividendScorer_PayoutRatioBoundaries(t *testing.T) {
	// Test exact boundaries of payout ratio ranges
	testCases := []struct {
		name        string
		payoutRatio float64
		expectedMin float64
		expectedMax float64
	}{
		{"Lower ideal boundary (30%)", 0.30, 0.8, 1.0},
		{"Upper ideal boundary (60%)", 0.60, 0.8, 1.0},
		{"Just below ideal (29%)", 0.29, 0.7, 1.0},
		{"Just above ideal (61%)", 0.61, 0.6, 1.0},
		{"Upper acceptable (80%)", 0.80, 0.5, 0.8},
		{"Risky high (90%)", 0.90, 0.3, 0.6},
	}

	fiveYearAvgDivYield := 0.03
	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			score := scoreDividendConsistency(&tc.payoutRatio, &fiveYearAvgDivYield)
			assert.GreaterOrEqual(t, score, tc.expectedMin, "Score should be >= %f", tc.expectedMin)
			assert.LessOrEqual(t, score, tc.expectedMax, "Score should be <= %f", tc.expectedMax)
		})
	}
}

func TestDividendScorer_YieldThresholds(t *testing.T) {
	// Test exact threshold boundaries
	testCases := []struct {
		name        string
		yield       float64
		expectedMin float64
		expectedMax float64
	}{
		{"Zero yield", 0.00, 0.30, 0.30},
		{"Very low (0.5%)", 0.005, 0.30, 0.40},
		{"Low threshold (1%)", 0.01, 0.40, 0.45},
		{"Low-mid (2%)", 0.02, 0.50, 0.60},
		{"Mid threshold (3%)", 0.03, 0.70, 0.75},
		{"Mid-high (4.5%)", 0.045, 0.80, 0.90},
		{"High threshold (6%)", 0.06, 1.00, 1.00},
		{"Very high (8%)", 0.08, 1.00, 1.00},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			score := scoreDividendYield(&tc.yield)
			assert.GreaterOrEqual(t, score, tc.expectedMin, "Score should be >= %f", tc.expectedMin)
			assert.LessOrEqual(t, score, tc.expectedMax, "Score should be <= %f", tc.expectedMax)
		})
	}
}

// ============================================================================
// Total Return Boost Tests (Enhanced Dividend Scoring)
// ============================================================================

func TestDividendScorer_CalculateEnhanced_HighTotalReturn(t *testing.T) {
	scorer := NewDividendScorer()

	// Example from document: 5% growth + 10% dividend = 15% total return
	dividendYield := 0.10  // 10% dividend
	expectedCAGR := 0.05    // 5% growth
	payoutRatio := 0.50
	fiveYearAvgDivYield := 0.08

	result := scorer.CalculateEnhanced(&dividendYield, &payoutRatio, &fiveYearAvgDivYield, &expectedCAGR)

	// Should get boost for 15%+ total return
	assert.Greater(t, result.Score, 0.8, "High total return should boost score")
	assert.Contains(t, result.Components, "total_return_boost")
	assert.GreaterOrEqual(t, result.Components["total_return_boost"], 0.15, "15%+ total return should get 0.15-0.20 boost")
	assert.Contains(t, result.Components, "total_return")
	assert.InDelta(t, 0.15, result.Components["total_return"], 0.001, "Total return should be 15%")
}

func TestDividendScorer_CalculateEnhanced_ExcellentTotalReturn(t *testing.T) {
	scorer := NewDividendScorer()

	// 20%+ total return (very high)
	dividendYield := 0.12  // 12% dividend
	expectedCAGR := 0.10   // 10% growth
	payoutRatio := 0.50
	fiveYearAvgDivYield := 0.10

	result := scorer.CalculateEnhanced(&dividendYield, &payoutRatio, &fiveYearAvgDivYield, &expectedCAGR)

	// Should get maximum boost (0.20) for 15%+ total return
	assert.Greater(t, result.Score, 0.8)
	assert.GreaterOrEqual(t, result.Components["total_return_boost"], 0.20, "15%+ total return should get 0.20 boost")
	assert.InDelta(t, 0.22, result.Components["total_return"], 0.001, "Total return should be 22%")
}

func TestDividendScorer_CalculateEnhanced_ModerateTotalReturn(t *testing.T) {
	scorer := NewDividendScorer()

	// 12% total return (moderate-high)
	dividendYield := 0.06  // 6% dividend
	expectedCAGR := 0.06   // 6% growth
	payoutRatio := 0.50
	fiveYearAvgDivYield := 0.05

	result := scorer.CalculateEnhanced(&dividendYield, &payoutRatio, &fiveYearAvgDivYield, &expectedCAGR)

	// Should get boost for 12-15% total return
	assert.Greater(t, result.Score, 0.7)
	assert.GreaterOrEqual(t, result.Components["total_return_boost"], 0.15, "12-15% total return should get 0.15 boost")
	assert.InDelta(t, 0.12, result.Components["total_return"], 0.001, "Total return should be 12%")
}

func TestDividendScorer_CalculateEnhanced_LowTotalReturn(t *testing.T) {
	scorer := NewDividendScorer()

	// 8% total return (below 10% threshold)
	dividendYield := 0.03  // 3% dividend
	expectedCAGR := 0.05   // 5% growth
	payoutRatio := 0.50
	fiveYearAvgDivYield := 0.03

	result := scorer.CalculateEnhanced(&dividendYield, &payoutRatio, &fiveYearAvgDivYield, &expectedCAGR)

	// Should not get boost (below 10% threshold)
	assert.Equal(t, 0.0, result.Components["total_return_boost"], "Below 10% total return should get no boost")
	assert.InDelta(t, 0.08, result.Components["total_return"], 0.001, "Total return should be 8%")
}

func TestDividendScorer_CalculateEnhanced_NoCAGR(t *testing.T) {
	scorer := NewDividendScorer()

	// No CAGR available (nil)
	dividendYield := 0.10
	payoutRatio := 0.50
	fiveYearAvgDivYield := 0.08

	result := scorer.CalculateEnhanced(&dividendYield, &payoutRatio, &fiveYearAvgDivYield, nil)

	// Should work without CAGR (no boost)
	assert.NotNil(t, result.Score)
	assert.Equal(t, 0.0, result.Components["total_return_boost"], "No CAGR should result in no boost")
	assert.NotContains(t, result.Components, "total_return", "Total return should not be calculated without CAGR")
}

func TestCalculateTotalReturnBoost_Thresholds(t *testing.T) {
	testCases := []struct {
		name        string
		dividend    float64
		cagr        float64
		expectedMin float64
		expectedMax float64
	}{
		{"15%+ total return", 0.10, 0.05, 0.20, 0.20},   // 15% total
		{"12-15% total return", 0.06, 0.06, 0.15, 0.15}, // 12% total
		{"10-12% total return", 0.05, 0.05, 0.10, 0.10}, // 10% total
		{"Below 10% total return", 0.03, 0.05, 0.0, 0.0}, // 8% total
		{"Exactly 15% total return", 0.10, 0.05, 0.20, 0.20},
		{"Exactly 12% total return", 0.07, 0.05, 0.15, 0.15},
		{"Exactly 10% total return", 0.05, 0.05, 0.10, 0.10},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			boost := calculateTotalReturnBoost(&tc.dividend, &tc.cagr)
			assert.GreaterOrEqual(t, boost, tc.expectedMin, "Boost should be >= %f", tc.expectedMin)
			assert.LessOrEqual(t, boost, tc.expectedMax, "Boost should be <= %f", tc.expectedMax)
		})
	}
}

func TestCalculateTotalReturnBoost_NilValues(t *testing.T) {
	// Nil dividend
	cagr := 0.10
	boost := calculateTotalReturnBoost(nil, &cagr)
	assert.Equal(t, 0.0, boost, "Nil dividend should result in no boost")

	// Nil CAGR
	dividend := 0.05
	boost = calculateTotalReturnBoost(&dividend, nil)
	assert.Equal(t, 0.0, boost, "Nil CAGR should result in no boost")

	// Both nil
	boost = calculateTotalReturnBoost(nil, nil)
	assert.Equal(t, 0.0, boost, "Both nil should result in no boost")
}
