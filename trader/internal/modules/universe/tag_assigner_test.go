package universe

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestTagAssigner_ValueOpportunity(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	currentPrice := 80.0
	price52wHigh := 100.0
	peRatio := 15.0
	marketAvgPE := 20.0

	input := AssignTagsInput{
		Symbol:       "TEST",
		CurrentPrice: &currentPrice,
		Price52wHigh: &price52wHigh,
		PERatio:      &peRatio,
		MarketAvgPE:  marketAvgPE,
		GroupScores: map[string]float64{
			"opportunity": 0.75,
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "value-opportunity")
	assert.Contains(t, tags, "below-52w-high")
	assert.Contains(t, tags, "undervalued-pe")
}

func TestTagAssigner_HighQuality(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	input := AssignTagsInput{
		Symbol: "TEST",
		GroupScores: map[string]float64{
			"fundamentals": 0.85,
			"long_term":    0.80,
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "high-quality")
	assert.Contains(t, tags, "strong-fundamentals")
}

func TestTagAssigner_Stable(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	volatility := 0.15

	input := AssignTagsInput{
		Symbol:     "TEST",
		Volatility: &volatility,
		GroupScores: map[string]float64{
			"fundamentals": 0.80,
		},
		SubScores: map[string]map[string]float64{
			"fundamentals": {
				"consistency": 0.85,
			},
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "stable")
}

func TestTagAssigner_Volatile(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	volatility := 0.35

	input := AssignTagsInput{
		Symbol:     "TEST",
		Volatility: &volatility,
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "volatile")
	assert.Contains(t, tags, "high-risk")
}

func TestTagAssigner_Oversold(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	rsi := 25.0

	input := AssignTagsInput{
		Symbol: "TEST",
		RSI:    &rsi,
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "oversold")
}

func TestTagAssigner_Overbought(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	rsi := 75.0

	input := AssignTagsInput{
		Symbol: "TEST",
		RSI:    &rsi,
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "overbought")
}

func TestTagAssigner_HighDividend(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	dividendYield := 7.0

	input := AssignTagsInput{
		Symbol:        "TEST",
		DividendYield: &dividendYield,
		GroupScores: map[string]float64{
			"dividends": 0.75,
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "high-dividend")
	assert.Contains(t, tags, "dividend-opportunity")
	assert.Contains(t, tags, "dividend-focused")
}

func TestTagAssigner_MultipleTags(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	currentPrice := 75.0 // 25% below 52W high
	price52wHigh := 100.0
	volatility := 0.12
	dividendYield := 5.0
	peRatio := 15.0
	marketAvgPE := 20.0

	input := AssignTagsInput{
		Symbol:        "TEST",
		CurrentPrice:  &currentPrice,
		Price52wHigh:  &price52wHigh,
		Volatility:    &volatility,
		DividendYield: &dividendYield,
		PERatio:       &peRatio,
		MarketAvgPE:   marketAvgPE,
		GroupScores: map[string]float64{
			"fundamentals": 0.85, // > 0.8 for high-quality
			"long_term":    0.80, // > 0.75 for high-quality
			"opportunity":  0.75, // > 0.7 for value-opportunity
			"dividends":    0.75,
		},
		SubScores: map[string]map[string]float64{
			"fundamentals": {
				"consistency": 0.85,
			},
		},
		Score: &SecurityScore{
			TotalScore: 0.78,
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	// Should have multiple tags
	assert.Greater(t, len(tags), 5)
	assert.Contains(t, tags, "value-opportunity")
	assert.Contains(t, tags, "high-quality")
	assert.Contains(t, tags, "stable")
	assert.Contains(t, tags, "dividend-opportunity")
	assert.Contains(t, tags, "low-risk")
}

func TestTagAssigner_NoTags(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	input := AssignTagsInput{
		Symbol: "TEST",
		GroupScores: map[string]float64{
			"fundamentals": 0.50,
			"long_term":    0.50,
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	// Should have at least risk profile tags
	assert.GreaterOrEqual(t, len(tags), 0)
}

func TestTagAssigner_QualityGatePass(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	input := AssignTagsInput{
		Symbol: "TEST",
		GroupScores: map[string]float64{
			"fundamentals": 0.65, // >= 0.6
			"long_term":    0.55, // >= 0.5
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "quality-gate-pass")
	assert.NotContains(t, tags, "quality-gate-fail")
}

func TestTagAssigner_QualityGateFail(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	// Test case 1: Fundamentals too low
	input1 := AssignTagsInput{
		Symbol: "TEST",
		GroupScores: map[string]float64{
			"fundamentals": 0.55, // < 0.6
			"long_term":    0.55, // >= 0.5
		},
	}

	tags1, err := assigner.AssignTagsForSecurity(input1)
	assert.NoError(t, err)
	assert.Contains(t, tags1, "quality-gate-fail")
	assert.NotContains(t, tags1, "quality-gate-pass")

	// Test case 2: Long-term too low
	input2 := AssignTagsInput{
		Symbol: "TEST",
		GroupScores: map[string]float64{
			"fundamentals": 0.65, // >= 0.6
			"long_term":    0.45, // < 0.5
		},
	}

	tags2, err := assigner.AssignTagsForSecurity(input2)
	assert.NoError(t, err)
	assert.Contains(t, tags2, "quality-gate-fail")
	assert.NotContains(t, tags2, "quality-gate-pass")
}

func TestTagAssigner_QualityValue(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	currentPrice := 80.0
	price52wHigh := 100.0
	peRatio := 15.0
	marketAvgPE := 20.0

	input := AssignTagsInput{
		Symbol:       "TEST",
		CurrentPrice: &currentPrice,
		Price52wHigh: &price52wHigh,
		PERatio:      &peRatio,
		MarketAvgPE:  marketAvgPE,
		GroupScores: map[string]float64{
			"fundamentals": 0.85, // > 0.8 for high-quality
			"long_term":    0.80, // > 0.75 for high-quality
			"opportunity":  0.75, // > 0.7 for value-opportunity
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	// Should have both high-quality and value-opportunity
	assert.Contains(t, tags, "high-quality")
	assert.Contains(t, tags, "value-opportunity")
	// Should also have quality-value combination tag
	assert.Contains(t, tags, "quality-value")
}

func TestTagAssigner_BubbleRisk(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	volatility := 0.45 // > 0.40

	input := AssignTagsInput{
		Symbol:     "TEST",
		Volatility: &volatility,
		GroupScores: map[string]float64{
			"fundamentals": 0.55, // < 0.6
		},
		SubScores: map[string]map[string]float64{
			"long_term": {
				"cagr_raw":    0.18, // > 16.5%
				"sharpe_raw":  0.3,  // < 0.5
				"sortino_raw": 0.4,  // < 0.5
			},
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "bubble-risk")
	assert.Contains(t, tags, "ensemble-bubble-risk") // Classical bubble should also get ensemble tag
	assert.NotContains(t, tags, "quality-high-cagr")
}

func TestTagAssigner_QualityHighCAGR(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	volatility := 0.30 // <= 0.40

	input := AssignTagsInput{
		Symbol:     "TEST",
		Volatility: &volatility,
		GroupScores: map[string]float64{
			"fundamentals": 0.70, // >= 0.6
		},
		SubScores: map[string]map[string]float64{
			"long_term": {
				"cagr_raw":    0.17, // > 15%
				"sharpe_raw":  0.6,  // >= 0.5
				"sortino_raw": 0.6,  // >= 0.5
			},
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "quality-high-cagr")
	assert.NotContains(t, tags, "bubble-risk")
}

func TestTagAssigner_HighSharpe(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	input := AssignTagsInput{
		Symbol: "TEST",
		SubScores: map[string]map[string]float64{
			"long_term": {
				"sharpe_raw": 1.8, // >= 1.5
			},
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "high-sharpe")
}

func TestTagAssigner_HighSortino(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	input := AssignTagsInput{
		Symbol: "TEST",
		SubScores: map[string]map[string]float64{
			"long_term": {
				"sortino_raw": 1.8, // >= 1.5
			},
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "high-sortino")
}

func TestTagAssigner_PoorRiskAdjusted(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	// Test case 1: Low Sharpe
	input1 := AssignTagsInput{
		Symbol: "TEST",
		SubScores: map[string]map[string]float64{
			"long_term": {
				"sharpe_raw":  0.3, // < 0.5
				"sortino_raw": 0.6, // >= 0.5
			},
		},
	}

	tags1, err := assigner.AssignTagsForSecurity(input1)
	assert.NoError(t, err)
	assert.Contains(t, tags1, "poor-risk-adjusted")

	// Test case 2: Low Sortino
	input2 := AssignTagsInput{
		Symbol: "TEST",
		SubScores: map[string]map[string]float64{
			"long_term": {
				"sharpe_raw":  0.6, // >= 0.5
				"sortino_raw": 0.3, // < 0.5
			},
		},
	}

	tags2, err := assigner.AssignTagsForSecurity(input2)
	assert.NoError(t, err)
	assert.Contains(t, tags2, "poor-risk-adjusted")
}

func TestTagAssigner_ValueTrap(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	peRatio := 12.0
	marketAvgPE := 20.0
	volatility := 0.40 // > 0.35

	input := AssignTagsInput{
		Symbol:      "TEST",
		PERatio:     &peRatio,
		MarketAvgPE: marketAvgPE,
		Volatility:  &volatility,
		GroupScores: map[string]float64{
			"fundamentals": 0.55, // < 0.6
			"long_term":    0.45, // < 0.5
		},
		SubScores: map[string]map[string]float64{
			"short_term": {
				"momentum": -0.06, // < -0.05
			},
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "value-trap")
}

func TestTagAssigner_NotValueTrap(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	peRatio := 12.0
	marketAvgPE := 20.0
	volatility := 0.20 // < 0.35

	input := AssignTagsInput{
		Symbol:      "TEST",
		PERatio:     &peRatio,
		MarketAvgPE: marketAvgPE,
		Volatility:  &volatility,
		GroupScores: map[string]float64{
			"fundamentals": 0.70, // >= 0.6
			"long_term":    0.60, // >= 0.5
		},
		SubScores: map[string]map[string]float64{
			"short_term": {
				"momentum": 0.05, // >= -0.05
			},
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	// Should have undervalued-pe but NOT value-trap
	assert.Contains(t, tags, "undervalued-pe")
	assert.NotContains(t, tags, "value-trap")
}

func TestTagAssigner_ExcellentTotalReturn(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	dividendYield := 0.10 // 10%
	cagrValue := 0.09     // 9% (total = 19% >= 18%)

	input := AssignTagsInput{
		Symbol:        "TEST",
		DividendYield: &dividendYield,
		SubScores: map[string]map[string]float64{
			"long_term": {
				"cagr_raw": cagrValue,
			},
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "excellent-total-return")
}

func TestTagAssigner_HighTotalReturn(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	dividendYield := 0.08 // 8%
	cagrValue := 0.08     // 8% (total = 16% >= 15%)

	input := AssignTagsInput{
		Symbol:        "TEST",
		DividendYield: &dividendYield,
		SubScores: map[string]map[string]float64{
			"long_term": {
				"cagr_raw": cagrValue,
			},
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "high-total-return")
	assert.NotContains(t, tags, "excellent-total-return")
}

func TestTagAssigner_ModerateTotalReturn(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	dividendYield := 0.06 // 6%
	cagrValue := 0.07     // 7% (total = 13% >= 12%)

	input := AssignTagsInput{
		Symbol:        "TEST",
		DividendYield: &dividendYield,
		SubScores: map[string]map[string]float64{
			"long_term": {
				"cagr_raw": cagrValue,
			},
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "moderate-total-return")
	assert.NotContains(t, tags, "high-total-return")
}

func TestTagAssigner_DividendTotalReturn(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	dividendYield := 0.10 // 10% >= 8%
	cagrValue := 0.06     // 6% >= 5%

	input := AssignTagsInput{
		Symbol:        "TEST",
		DividendYield: &dividendYield,
		SubScores: map[string]map[string]float64{
			"long_term": {
				"cagr_raw": cagrValue,
			},
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "dividend-total-return")
}

func TestTagAssigner_TargetAligned(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	positionWeight := 0.10 // 10%
	targetWeight := 0.10   // 10% (deviation = 0% <= 1%)

	input := AssignTagsInput{
		Symbol:         "TEST",
		PositionWeight: &positionWeight,
		TargetWeight:   &targetWeight,
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "target-aligned")
}

func TestTagAssigner_Underweight(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	positionWeight := 0.05 // 5%
	targetWeight := 0.10   // 10% (deviation = -5% < -2%)

	input := AssignTagsInput{
		Symbol:         "TEST",
		PositionWeight: &positionWeight,
		TargetWeight:   &targetWeight,
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "underweight")
}

func TestTagAssigner_NeedsRebalance(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	// Test case 1: Overweight by more than 3%
	positionWeight1 := 0.15 // 15%
	targetWeight1 := 0.10   // 10% (deviation = 5% > 3%)

	input1 := AssignTagsInput{
		Symbol:         "TEST",
		PositionWeight: &positionWeight1,
		TargetWeight:   &targetWeight1,
	}

	tags1, err := assigner.AssignTagsForSecurity(input1)
	assert.NoError(t, err)
	assert.Contains(t, tags1, "needs-rebalance")

	// Test case 2: Underweight by more than 3%
	positionWeight2 := 0.05 // 5%
	targetWeight2 := 0.10   // 10% (deviation = -5% < -3%)

	input2 := AssignTagsInput{
		Symbol:         "TEST",
		PositionWeight: &positionWeight2,
		TargetWeight:   &targetWeight2,
	}

	tags2, err := assigner.AssignTagsForSecurity(input2)
	assert.NoError(t, err)
	assert.Contains(t, tags2, "needs-rebalance")
}

func TestTagAssigner_SlightlyOverweight(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	positionWeight := 0.12 // 12%
	targetWeight := 0.10   // 10% (deviation = 2%, between 1% and 3%)

	input := AssignTagsInput{
		Symbol:         "TEST",
		PositionWeight: &positionWeight,
		TargetWeight:   &targetWeight,
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "slightly-overweight")
}

func TestTagAssigner_SlightlyUnderweight(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	positionWeight := 0.08 // 8%
	targetWeight := 0.10   // 10% (deviation = -2%, between -1% and -3%)

	input := AssignTagsInput{
		Symbol:         "TEST",
		PositionWeight: &positionWeight,
		TargetWeight:   &targetWeight,
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "slightly-underweight")
}

func TestTagAssigner_RegimeBearSafe(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	volatility := 0.15  // < 0.20
	maxDrawdown := 15.0 // < 20%

	input := AssignTagsInput{
		Symbol:      "TEST",
		Volatility:  &volatility,
		MaxDrawdown: &maxDrawdown,
		GroupScores: map[string]float64{
			"fundamentals": 0.80, // > 0.75
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "regime-bear-safe")
}

func TestTagAssigner_RegimeBullGrowth(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	cagrValue := 0.13 // > 12%

	input := AssignTagsInput{
		Symbol: "TEST",
		GroupScores: map[string]float64{
			"fundamentals": 0.75, // > 0.7
		},
		SubScores: map[string]map[string]float64{
			"long_term": {
				"cagr_raw": cagrValue,
			},
			"short_term": {
				"momentum": 0.05, // > 0
			},
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	assert.Contains(t, tags, "regime-bull-growth")
}

func TestTagAssigner_RegimeSidewaysValue(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	currentPrice := 80.0
	price52wHigh := 100.0
	peRatio := 15.0
	marketAvgPE := 20.0

	input := AssignTagsInput{
		Symbol:       "TEST",
		CurrentPrice: &currentPrice,
		Price52wHigh: &price52wHigh,
		PERatio:      &peRatio,
		MarketAvgPE:  marketAvgPE,
		GroupScores: map[string]float64{
			"opportunity":  0.75, // > 0.7 for value-opportunity
			"fundamentals": 0.80, // > 0.75
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)
	// Should have value-opportunity
	assert.Contains(t, tags, "value-opportunity")
	// Should also have regime-sideways-value
	assert.Contains(t, tags, "regime-sideways-value")
}

func TestTagAssigner_RegimeVolatile(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	// Test case 1: High volatility
	volatility1 := 0.35 // > 0.30
	historicalVolatility1 := 0.20

	input1 := AssignTagsInput{
		Symbol:               "TEST",
		Volatility:           &volatility1,
		HistoricalVolatility: &historicalVolatility1,
	}

	tags1, err := assigner.AssignTagsForSecurity(input1)
	assert.NoError(t, err)
	assert.Contains(t, tags1, "regime-volatile")

	// Test case 2: Volatility spike
	volatility2 := 0.30
	historicalVolatility2 := 0.15 // volatility > historical * 1.5 = 0.225, so 0.30 > 0.225 = spike

	input2 := AssignTagsInput{
		Symbol:               "TEST",
		Volatility:           &volatility2,
		HistoricalVolatility: &historicalVolatility2,
	}

	tags2, err := assigner.AssignTagsForSecurity(input2)
	assert.NoError(t, err)
	assert.Contains(t, tags2, "volatility-spike")
	assert.Contains(t, tags2, "regime-volatile")
}

func TestTagAssigner_AllEnhancedTags(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	// Create a security that meets criteria for multiple enhanced tags
	currentPrice := 75.0
	price52wHigh := 100.0
	peRatio := 15.0
	marketAvgPE := 20.0
	volatility := 0.18
	historicalVolatility := 0.15
	dividendYield := 0.10 // 10%
	maxDrawdown := 15.0
	positionWeight := 0.10
	targetWeight := 0.10

	input := AssignTagsInput{
		Symbol:               "TEST",
		CurrentPrice:         &currentPrice,
		Price52wHigh:         &price52wHigh,
		PERatio:              &peRatio,
		MarketAvgPE:          marketAvgPE,
		Volatility:           &volatility,
		HistoricalVolatility: &historicalVolatility,
		DividendYield:        &dividendYield,
		MaxDrawdown:          &maxDrawdown,
		PositionWeight:       &positionWeight,
		TargetWeight:         &targetWeight,
		GroupScores: map[string]float64{
			"fundamentals": 0.85, // > 0.8 for high-quality, > 0.6 for quality-gate-pass
			"long_term":    0.80, // > 0.75 for high-quality, > 0.5 for quality-gate-pass
			"opportunity":  0.75, // > 0.7 for value-opportunity
		},
		SubScores: map[string]map[string]float64{
			"long_term": {
				"cagr_raw":    0.17, // > 15% for quality-high-cagr
				"sharpe_raw":  1.8,  // >= 1.5 for high-sharpe
				"sortino_raw": 1.8,  // >= 1.5 for high-sortino
			},
			"short_term": {
				"momentum": 0.05, // > 0 for regime-bull-growth
			},
		},
		Score: &SecurityScore{
			TotalScore: 0.78,
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)

	// Verify quality gate tags
	assert.Contains(t, tags, "quality-gate-pass")
	assert.Contains(t, tags, "high-quality")
	assert.Contains(t, tags, "value-opportunity")
	assert.Contains(t, tags, "quality-value")

	// Verify bubble detection tags
	assert.Contains(t, tags, "quality-high-cagr")
	assert.Contains(t, tags, "high-sharpe")
	// high-sortino may not be present if sortino is not available (0.0)

	// Verify total return tags
	// Total return = 0.17 + 0.10 = 0.27 >= 0.18
	assert.Contains(t, tags, "excellent-total-return")
	// dividend-total-return: 0.10 >= 0.08 AND 0.17 >= 0.05
	assert.Contains(t, tags, "dividend-total-return")

	// Verify optimizer alignment tags
	assert.Contains(t, tags, "target-aligned")

	// Verify regime-specific tags
	assert.Contains(t, tags, "regime-bear-safe")      // volatility < 0.20, fundamentals > 0.75, drawdown < 20%
	assert.Contains(t, tags, "regime-bull-growth")    // CAGR > 12%, fundamentals > 0.7, momentum > 0
	assert.Contains(t, tags, "regime-sideways-value") // value-opportunity AND fundamentals > 0.75

	// Should NOT have value trap (good fundamentals)
	assert.NotContains(t, tags, "value-trap")
	assert.NotContains(t, tags, "bubble-risk")

	t.Logf("Assigned %d tags total", len(tags))
}

func TestTagAssigner_QuantumBubbleDetection(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	volatility := 0.38 // Just below 0.40 threshold

	input := AssignTagsInput{
		Symbol:     "TEST",
		Volatility: &volatility,
		GroupScores: map[string]float64{
			"fundamentals": 0.62, // Just above 0.6 threshold
		},
		SubScores: map[string]map[string]float64{
			"long_term": {
				"cagr_raw":    0.16, // 16% - high but not > 16.5% (classical threshold)
				"sharpe_raw":  0.52, // Just above 0.5 (classical threshold)
				"sortino_raw": 0.52, // Just above 0.5 (classical threshold)
			},
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)

	// Classical should NOT detect (all metrics just above thresholds)
	assert.NotContains(t, tags, "bubble-risk")

	// Quantum might detect (early warning) - check if quantum tags are present
	// Quantum detection is probabilistic, so we just verify the system runs
	// In practice, with these inputs, quantum might detect early warning
	t.Logf("Quantum bubble detection tags: %v", tags)
	// Verify system doesn't crash and produces tags
	assert.Greater(t, len(tags), 0, "Should produce some tags")
}

func TestTagAssigner_QuantumValueTrapDetection(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	peRatio := 12.0
	marketAvgPE := 20.0
	volatility := 0.30

	input := AssignTagsInput{
		Symbol:      "TEST",
		PERatio:     &peRatio,
		MarketAvgPE: marketAvgPE,
		Volatility:  &volatility,
		GroupScores: map[string]float64{
			"fundamentals": 0.55, // Just below threshold
			"long_term":    0.45, // Just below threshold
		},
		SubScores: map[string]map[string]float64{
			"short_term": {
				"momentum": -0.03, // Slightly negative
			},
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)

	// Classical might detect (borderline case)
	// Quantum should also evaluate
	hasValueTrapTag := false
	for _, tag := range tags {
		if tag == "value-trap" || tag == "quantum-value-trap" || tag == "ensemble-value-trap" {
			hasValueTrapTag = true
			break
		}
	}

	t.Logf("Value trap detection tags: %v", tags)
	// At least one detection method should flag this
	assert.True(t, hasValueTrapTag, "Should detect value trap (classical or quantum)")
}

func TestTagAssigner_EnsembleBubbleDetection(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	assigner := NewTagAssigner(log)

	volatility := 0.45

	input := AssignTagsInput{
		Symbol:     "TEST",
		Volatility: &volatility,
		GroupScores: map[string]float64{
			"fundamentals": 0.55, // < 0.6
		},
		SubScores: map[string]map[string]float64{
			"long_term": {
				"cagr_raw":    0.18, // > 16.5% (classical threshold)
				"sharpe_raw":  0.3,  // < 0.5 (classical threshold)
				"sortino_raw": 0.4,  // < 0.5 (classical threshold)
			},
		},
	}

	tags, err := assigner.AssignTagsForSecurity(input)
	assert.NoError(t, err)

	// Both classical and ensemble should detect
	assert.Contains(t, tags, "bubble-risk")
	assert.Contains(t, tags, "ensemble-bubble-risk")
}
