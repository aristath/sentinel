package symbolic_regression

import (
	"math"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNormalizeFeatures(t *testing.T) {
	examples := []TrainingExample{
		{
			Inputs: TrainingInputs{
				TotalScore:    0.75,
				LongTermScore: 0.80,
				CAGR:          0.12,
				Volatility:    0.25,
				RegimeScore:   0.3,
			},
		},
		{
			Inputs: TrainingInputs{
				TotalScore:    0.50,
				LongTermScore: 0.60,
				CAGR:          0.08,
				Volatility:    0.15,
				RegimeScore:   -0.2,
			},
		},
		{
			Inputs: TrainingInputs{
				TotalScore:    0.90,
				LongTermScore: 0.95,
				CAGR:          0.20,
				Volatility:    0.30,
				RegimeScore:   0.8,
			},
		},
	}

	normalized := NormalizeFeatures(examples)

	require.Equal(t, len(examples), len(normalized))

	// Verify all scores are in [0, 1] range
	for _, ex := range normalized {
		assert.GreaterOrEqual(t, ex.Inputs.TotalScore, 0.0)
		assert.LessOrEqual(t, ex.Inputs.TotalScore, 1.0)
		assert.GreaterOrEqual(t, ex.Inputs.LongTermScore, 0.0)
		assert.LessOrEqual(t, ex.Inputs.LongTermScore, 1.0)
	}

	// Verify regime scores are in [-1, 1] range (should not be normalized)
	for _, ex := range normalized {
		assert.GreaterOrEqual(t, ex.Inputs.RegimeScore, -1.0)
		assert.LessOrEqual(t, ex.Inputs.RegimeScore, 1.0)
	}
}

func TestNormalizeFeatures_EmptyInput(t *testing.T) {
	examples := []TrainingExample{}
	normalized := NormalizeFeatures(examples)
	assert.Equal(t, 0, len(normalized))
}

func TestNormalizeFeatures_WithMissingValues(t *testing.T) {
	examples := []TrainingExample{
		{
			Inputs: TrainingInputs{
				TotalScore:  0.75,
				CAGR:        0.12,
				RegimeScore: 0.3,
				// Missing LongTermScore, Volatility
			},
		},
		{
			Inputs: TrainingInputs{
				TotalScore:    0.50,
				LongTermScore: 0.60,
				CAGR:          0.08,
				Volatility:    0.15,
				RegimeScore:   -0.2,
			},
		},
	}

	normalized := NormalizeFeatures(examples)
	require.Equal(t, 2, len(normalized))

	// First example should have default values for missing features
	assert.Equal(t, 0.5, normalized[0].Inputs.LongTermScore) // Default
	assert.Equal(t, 0.0, normalized[0].Inputs.Volatility)    // Default
}

func TestExtractFeatureNames(t *testing.T) {
	examples := []TrainingExample{
		{
			Inputs: TrainingInputs{
				TotalScore:           0.75,
				LongTermScore:        0.80,
				FundamentalsScore:    0.70,
				DividendsScore:       0.65,
				OpportunityScore:     0.60,
				ShortTermScore:       0.55,
				TechnicalsScore:      0.50,
				OpinionScore:         0.45,
				DiversificationScore: 0.40,
				CAGR:                 0.12,
				DividendYield:        0.03,
				Volatility:           0.25,
				RegimeScore:          0.3,
			},
		},
	}

	featureNames := ExtractFeatureNames(examples[0].Inputs)

	expected := []string{
		"long_term", "fundamentals", "dividends", "opportunity",
		"short_term", "technicals", "opinion", "diversification",
		"total_score", "cagr", "dividend_yield", "volatility", "regime",
	}

	for _, name := range expected {
		assert.Contains(t, featureNames, name, "Feature %s should be included", name)
	}
}

func TestGetFeatureValue(t *testing.T) {
	inputs := TrainingInputs{
		LongTermScore:     0.80,
		FundamentalsScore: 0.70,
		CAGR:              0.12,
		Volatility:        0.25,
		RegimeScore:       0.3,
		SharpeRatio:       floatPtr(1.5),
		SortinoRatio:      floatPtr(2.0),
		RSI:               floatPtr(65.0),
		MaxDrawdown:       floatPtr(-0.15),
	}

	// Test scoring components
	assert.Equal(t, 0.80, GetFeatureValue(inputs, "long_term"))
	assert.Equal(t, 0.70, GetFeatureValue(inputs, "fundamentals"))
	assert.Equal(t, 0.0, GetFeatureValue(inputs, "dividends")) // Missing, returns 0

	// Test metrics
	assert.Equal(t, 0.12, GetFeatureValue(inputs, "cagr"))
	assert.Equal(t, 0.25, GetFeatureValue(inputs, "volatility"))
	assert.Equal(t, 0.3, GetFeatureValue(inputs, "regime"))

	// Test optional metrics
	assert.Equal(t, 1.5, GetFeatureValue(inputs, "sharpe"))
	assert.Equal(t, 2.0, GetFeatureValue(inputs, "sortino"))
	assert.Equal(t, 65.0, GetFeatureValue(inputs, "rsi"))
	assert.Equal(t, -0.15, GetFeatureValue(inputs, "max_drawdown"))

	// Test unknown feature
	assert.Equal(t, 0.0, GetFeatureValue(inputs, "unknown_feature"))
}

func TestNormalizeValue(t *testing.T) {
	tests := []struct {
		name     string
		value    float64
		minMax   [2]float64
		expected float64
	}{
		{
			name:     "value at min",
			value:    0.0,
			minMax:   [2]float64{0.0, 10.0},
			expected: 0.0,
		},
		{
			name:     "value at max",
			value:    10.0,
			minMax:   [2]float64{0.0, 10.0},
			expected: 1.0,
		},
		{
			name:     "value in middle",
			value:    5.0,
			minMax:   [2]float64{0.0, 10.0},
			expected: 0.5,
		},
		{
			name:     "value below min (clamped)",
			value:    -5.0,
			minMax:   [2]float64{0.0, 10.0},
			expected: 0.0,
		},
		{
			name:     "value above max (clamped)",
			value:    15.0,
			minMax:   [2]float64{0.0, 10.0},
			expected: 1.0,
		},
		{
			name:     "no range (min == max)",
			value:    5.0,
			minMax:   [2]float64{5.0, 5.0},
			expected: 0.5,
		},
		{
			name:     "negative range",
			value:    -5.0,
			minMax:   [2]float64{-10.0, 0.0},
			expected: 0.5,
		},
		{
			name:     "NaN value",
			value:    math.NaN(),
			minMax:   [2]float64{0.0, 10.0},
			expected: 0.0,
		},
		{
			name:     "positive infinity",
			value:    math.Inf(1),
			minMax:   [2]float64{0.0, 10.0},
			expected: 0.0,
		},
		{
			name:     "negative infinity",
			value:    math.Inf(-1),
			minMax:   [2]float64{0.0, 10.0},
			expected: 0.0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := normalizeValue(tt.value, tt.minMax)
			assert.InDelta(t, tt.expected, result, 0.0001)
		})
	}
}

func floatPtr(f float64) *float64 {
	return &f
}
