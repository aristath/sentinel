package optimization

import (
	"math"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestBuildCorrelationMap(t *testing.T) {
	tests := []struct {
		name     string
		pairs    []CorrelationPair
		expected map[string]float64
	}{
		{
			name:     "empty pairs",
			pairs:    []CorrelationPair{},
			expected: map[string]float64{},
		},
		{
			name: "single pair",
			pairs: []CorrelationPair{
				{Symbol1: "AAPL", Symbol2: "MSFT", Correlation: 0.85},
			},
			expected: map[string]float64{
				"AAPL:MSFT": 0.85,
				"MSFT:AAPL": 0.85,
			},
		},
		{
			name: "multiple pairs",
			pairs: []CorrelationPair{
				{Symbol1: "AAPL", Symbol2: "MSFT", Correlation: 0.85},
				{Symbol1: "GOOGL", Symbol2: "AMZN", Correlation: 0.90},
			},
			expected: map[string]float64{
				"AAPL:MSFT":  0.85,
				"MSFT:AAPL":  0.85,
				"GOOGL:AMZN": 0.90,
				"AMZN:GOOGL": 0.90,
			},
		},
		{
			name: "negative correlation",
			pairs: []CorrelationPair{
				{Symbol1: "AAPL", Symbol2: "GOLD", Correlation: -0.30},
			},
			expected: map[string]float64{
				"AAPL:GOLD": -0.30,
				"GOLD:AAPL": -0.30,
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := BuildCorrelationMap(tt.pairs)
			assert.Equal(t, len(tt.expected), len(result), "Map size should match")

			for key, expectedValue := range tt.expected {
				actualValue, exists := result[key]
				assert.True(t, exists, "Key %s should exist", key)
				assert.InDelta(t, expectedValue, actualValue, 0.0001, "Value for %s should match", key)
			}
		})
	}
}

func TestEffectiveSampleSize(t *testing.T) {
	tests := []struct {
		name     string
		weights  []float64
		expected float64
	}{
		{
			name:     "empty weights",
			weights:  []float64{},
			expected: 0.0,
		},
		{
			name:     "uniform weights",
			weights:  []float64{0.25, 0.25, 0.25, 0.25},
			expected: 4.0, // 1 / (0.25^2 + 0.25^2 + 0.25^2 + 0.25^2) = 1 / 0.25 = 4.0
		},
		{
			name:     "single weight",
			weights:  []float64{1.0},
			expected: 1.0, // 1 / (1.0^2) = 1.0
		},
		{
			name:     "unequal weights",
			weights:  []float64{0.5, 0.3, 0.2},
			expected: 2.6316, // 1 / (0.25 + 0.09 + 0.04) = 1 / 0.38 ≈ 2.6316
		},
		{
			name:     "concentrated weights",
			weights:  []float64{0.9, 0.1},
			expected: 1.2346, // 1 / (0.81 + 0.01) = 1 / 0.82 ≈ 1.2195
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := effectiveSampleSize(tt.weights)
			assert.InDelta(t, tt.expected, result, 0.1, "Effective sample size should match")
			if result > 0 {
				assert.False(t, math.IsNaN(result), "Result should not be NaN")
				assert.False(t, math.IsInf(result, 0), "Result should not be Inf")
			}
		})
	}
}

func TestRegimeTimeDecayWeights(t *testing.T) {
	tests := []struct {
		name           string
		regimeScores   []float64
		currentRegime  float64
		halfLifeDays   float64
		bandwidth      float64
		expectedErr    bool
		expectedSum    float64
		expectedLength int
		description    string
	}{
		{
			name:           "valid weights",
			regimeScores:   []float64{0.5, 0.6, 0.7, 0.65, 0.55},
			currentRegime:  0.6,
			halfLifeDays:   63.0,
			bandwidth:      0.25,
			expectedErr:    false,
			expectedSum:    1.0,
			expectedLength: 5,
			description:    "Valid parameters should return normalized weights",
		},
		{
			name:          "empty regime scores",
			regimeScores:  []float64{},
			currentRegime: 0.6,
			halfLifeDays:  63.0,
			bandwidth:     0.25,
			expectedErr:   true,
			description:   "Empty regime scores should return error",
		},
		{
			name:          "invalid half life",
			regimeScores:  []float64{0.5, 0.6},
			currentRegime: 0.6,
			halfLifeDays:  0.0,
			bandwidth:     0.25,
			expectedErr:   true,
			description:   "Zero half life should return error",
		},
		{
			name:          "invalid bandwidth",
			regimeScores:  []float64{0.5, 0.6},
			currentRegime: 0.6,
			halfLifeDays:  63.0,
			bandwidth:     0.0,
			expectedErr:   true,
			description:   "Zero bandwidth should return error",
		},
		{
			name:          "negative half life",
			regimeScores:  []float64{0.5, 0.6},
			currentRegime: 0.6,
			halfLifeDays:  -10.0,
			bandwidth:     0.25,
			expectedErr:   true,
			description:   "Negative half life should return error",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := regimeTimeDecayWeights(tt.regimeScores, tt.currentRegime, tt.halfLifeDays, tt.bandwidth)
			if tt.expectedErr {
				assert.Error(t, err, tt.description)
				assert.Nil(t, result, "Result should be nil on error")
			} else {
				assert.NoError(t, err, tt.description)
				assert.NotNil(t, result, "Result should not be nil")
				assert.Equal(t, tt.expectedLength, len(result), "Should have correct length")

				// Weights should sum to 1.0 (normalized)
				var sum float64
				for _, w := range result {
					sum += w
					assert.False(t, math.IsNaN(w), "Weight should not be NaN")
					assert.False(t, math.IsInf(w, 0), "Weight should not be Inf")
					assert.GreaterOrEqual(t, w, 0.0, "Weight should be non-negative")
				}
				assert.InDelta(t, tt.expectedSum, sum, 0.0001, "Weights should sum to 1.0")
			}
		})
	}
}

func TestBuildPlaceholders(t *testing.T) {
	rb := &RiskModelBuilder{}

	tests := []struct {
		name     string
		n        int
		expected string
	}{
		{"zero", 0, ""},
		{"one", 1, "?"},
		{"two", 2, "?, ?"},
		{"three", 3, "?, ?, ?"},
		{"five", 5, "?, ?, ?, ?, ?"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := rb.buildPlaceholders(tt.n)
			assert.Equal(t, tt.expected, result)
		})
	}
}
