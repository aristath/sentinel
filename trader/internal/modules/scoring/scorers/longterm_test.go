package scorers

import (
	"testing"

	"github.com/aristath/arduino-trader/internal/modules/scoring"
	"github.com/stretchr/testify/assert"
)

func TestScoreCAGRWithBubbleDetection_BelowTarget(t *testing.T) {
	// Below target should use bell curve (peaks at target)
	target := 0.11

	// Test various CAGR values below target
	// Bell curve: closer to target = higher score
	tests := []struct {
		cagr         float64
		expectedMin  float64
		expectedMax  float64
		description  string
	}{
		{0.05, scoring.BellCurveFloor, 0.7, "5% CAGR (well below target, should score lower)"},
		{0.08, scoring.BellCurveFloor, 0.95, "8% CAGR (closer to target, should score higher)"},
		{0.10, 0.95, 1.0, "10% CAGR (very close to target, should score very high)"},
	}

	for _, tt := range tests {
		t.Run(tt.description, func(t *testing.T) {
			score := scoreCAGRWithBubbleDetection(tt.cagr, target, nil, nil, nil)
			assert.GreaterOrEqual(t, score, tt.expectedMin, "Score should be at least minimum")
			assert.LessOrEqual(t, score, tt.expectedMax, "Score should be at most maximum")
			assert.GreaterOrEqual(t, score, scoring.BellCurveFloor, "Score should respect floor")
		})
	}
}

func TestScoreCAGRWithBubbleDetection_AtTarget(t *testing.T) {
	// At target should score 0.8
	target := 0.11
	cagr := 0.11

	score := scoreCAGRWithBubbleDetection(cagr, target, nil, nil, nil)
	assert.InDelta(t, 0.8, score, 0.05, "At target should score approximately 0.8")
}

func TestScoreCAGRWithBubbleDetection_AboveTarget_Quality(t *testing.T) {
	// Above target with good risk metrics should be rewarded (monotonic)
	target := 0.11
	goodSharpe := 1.5
	goodSortino := 1.5
	lowVolatility := 0.20

	tests := []struct {
		cagr        float64
		expectedMin float64
		description string
	}{
		{0.12, 0.80, "12% CAGR (slightly above target)"},
		{0.15, 0.90, "15% CAGR (well above target, should be ~0.95)"},
		{0.20, 0.95, "20% CAGR (very high, quality, should be 1.0)"},
		{0.25, 1.0, "25% CAGR (excellent, quality, should be 1.0)"},
	}

	for _, tt := range tests {
		t.Run(tt.description, func(t *testing.T) {
			score := scoreCAGRWithBubbleDetection(tt.cagr, target, &goodSharpe, &goodSortino, &lowVolatility)
			assert.GreaterOrEqual(t, score, tt.expectedMin, "Quality high CAGR should be rewarded")
			assert.LessOrEqual(t, score, 1.0, "Score should be capped at 1.0")
		})
	}
}

func TestScoreCAGRWithBubbleDetection_BubbleDetection(t *testing.T) {
	// High CAGR with poor risk metrics should be detected as bubble
	target := 0.11
	highCAGR := 0.18 // 18% (above 1.5x target of 16.5%)

	// Poor risk metrics
	poorSharpe := 0.3
	poorSortino := 0.3
	highVolatility := 0.50

	t.Run("Bubble detected with 2+ poor risk metrics", func(t *testing.T) {
		// 2 poor metrics (Sharpe and Sortino)
		score := scoreCAGRWithBubbleDetection(highCAGR, target, &poorSharpe, &poorSortino, &highVolatility)
		assert.Equal(t, 0.6, score, "Bubble should be capped at 0.6")
	})

	t.Run("Bubble detected with poor Sharpe and high volatility", func(t *testing.T) {
		// 2 poor metrics (Sharpe and volatility)
		score := scoreCAGRWithBubbleDetection(highCAGR, target, &poorSharpe, nil, &highVolatility)
		assert.Equal(t, 0.6, score, "Bubble should be capped at 0.6")
	})

	t.Run("Bubble detected with poor Sortino and high volatility", func(t *testing.T) {
		// 2 poor metrics (Sortino and volatility)
		score := scoreCAGRWithBubbleDetection(highCAGR, target, nil, &poorSortino, &highVolatility)
		assert.Equal(t, 0.6, score, "Bubble should be capped at 0.6")
	})

	t.Run("No bubble with only 1 poor metric", func(t *testing.T) {
		// Only 1 poor metric (Sharpe), should not be bubble
		goodSortino := 1.0
		lowVolatility := 0.20
		score := scoreCAGRWithBubbleDetection(highCAGR, target, &poorSharpe, &goodSortino, &lowVolatility)
		assert.Greater(t, score, 0.6, "Should not be bubble with only 1 poor metric")
	})

	t.Run("No bubble with good risk metrics", func(t *testing.T) {
		// Good risk metrics, should reward high CAGR
		goodSharpe := 1.5
		goodSortino := 1.5
		lowVolatility := 0.20
		score := scoreCAGRWithBubbleDetection(highCAGR, target, &goodSharpe, &goodSortino, &lowVolatility)
		assert.Greater(t, score, 0.8, "Quality high CAGR should be rewarded")
	})
}

func TestScoreCAGRWithBubbleDetection_MonotonicScoring(t *testing.T) {
	// Verify that higher CAGR = higher score (monotonic) for quality securities
	target := 0.11
	goodSharpe := 1.5
	goodSortino := 1.5
	lowVolatility := 0.20

	cagr1 := 0.12
	cagr2 := 0.15
	cagr3 := 0.20

	score1 := scoreCAGRWithBubbleDetection(cagr1, target, &goodSharpe, &goodSortino, &lowVolatility)
	score2 := scoreCAGRWithBubbleDetection(cagr2, target, &goodSharpe, &goodSortino, &lowVolatility)
	score3 := scoreCAGRWithBubbleDetection(cagr3, target, &goodSharpe, &goodSortino, &lowVolatility)

	// Verify monotonic property: higher CAGR = higher score
	assert.Less(t, score1, score2, "12% should score lower than 15%")
	assert.Less(t, score2, score3, "15% should score lower than 20%")
}

func TestScoreCAGRWithBubbleDetection_EdgeCases(t *testing.T) {
	target := 0.11

	t.Run("Zero CAGR", func(t *testing.T) {
		score := scoreCAGRWithBubbleDetection(0.0, target, nil, nil, nil)
		assert.Equal(t, scoring.BellCurveFloor, score, "Zero CAGR should return floor")
	})

	t.Run("Negative CAGR", func(t *testing.T) {
		score := scoreCAGRWithBubbleDetection(-0.05, target, nil, nil, nil)
		assert.Equal(t, scoring.BellCurveFloor, score, "Negative CAGR should return floor")
	})

	t.Run("Nil risk metrics", func(t *testing.T) {
		// High CAGR without risk metrics - should not be bubble (can't detect)
		highCAGR := 0.18
		score := scoreCAGRWithBubbleDetection(highCAGR, target, nil, nil, nil)
		assert.Greater(t, score, 0.6, "Without risk metrics, should not be detected as bubble")
	})
}
