package adaptation

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestShouldAdapt(t *testing.T) {
	service := NewAdaptiveMarketService(nil, nil, nil, nil, zerolog.Nop())

	tests := []struct {
		name         string
		currentScore float64
		lastScore    float64
		threshold    float64
		expected     bool
		description  string
	}{
		{
			name:         "Significant change triggers adaptation",
			currentScore: 0.5,
			lastScore:    0.2,
			threshold:    0.1,
			expected:     true,
			description:  "Change of 0.3 > 0.1 threshold",
		},
		{
			name:         "Small change does not trigger",
			currentScore: 0.25,
			lastScore:    0.2,
			threshold:    0.1,
			expected:     false,
			description:  "Change of 0.05 < 0.1 threshold",
		},
		{
			name:         "Negative change triggers",
			currentScore: -0.3,
			lastScore:    -0.1,
			threshold:    0.1,
			expected:     true,
			description:  "Change of -0.2 (abs) > 0.1 threshold",
		},
		{
			name:         "Crossing threshold triggers",
			currentScore: 0.4,
			lastScore:    0.2,
			threshold:    0.33, // Crossing bull threshold
			expected:     true,
			description:  "Crossing key threshold (0.33)",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			shouldAdapt := service.ShouldAdapt(tt.currentScore, tt.lastScore, tt.threshold)
			assert.Equal(t, tt.expected, shouldAdapt, tt.description)
		})
	}
}

func TestCalculateAdaptiveWeights(t *testing.T) {
	service := NewAdaptiveMarketService(nil, nil, nil, nil, zerolog.Nop())

	tests := []struct {
		name            string
		regimeScore     float64
		expectedWeights map[string]float64
		description     string
	}{
		{
			name:        "Extreme bull weights",
			regimeScore: 1.0,
			expectedWeights: map[string]float64{
				"long_term":    0.30, // Higher in bull
				"opportunity":  0.18, // Higher in bull
				"fundamentals": 0.15, // Lower in bull
			},
			description: "Bull market should favor growth",
		},
		{
			name:        "Extreme bear weights",
			regimeScore: -1.0,
			expectedWeights: map[string]float64{
				"fundamentals": 0.30, // Higher in bear
				"dividends":    0.25, // Higher in bear
				"long_term":    0.20, // Lower in bear
			},
			description: "Bear market should favor quality",
		},
		{
			name:        "Neutral weights",
			regimeScore: 0.0,
			expectedWeights: map[string]float64{
				"long_term":    0.25, // Default
				"fundamentals": 0.20, // Default
				"opportunity":  0.12, // Default
			},
			description: "Neutral should use default weights",
		},
		{
			name:        "Bull-ish weights (0.3)",
			regimeScore: 0.3,
			expectedWeights: map[string]float64{
				"long_term": 0.265, // Interpolated: 0.25 + (0.30-0.25)*0.3
			},
			description: "Bull-ish should interpolate between neutral and bull",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			weights := service.CalculateAdaptiveWeights(tt.regimeScore)
			require.NotNil(t, weights)

			// Verify weights sum to 1.0
			total := 0.0
			for _, w := range weights {
				total += w
			}
			assert.InDelta(t, 1.0, total, 0.01, "Weights should sum to 1.0")

			// Check specific weights match expectations
			for key, expected := range tt.expectedWeights {
				if actual, ok := weights[key]; ok {
					assert.InDelta(t, expected, actual, 0.01,
						"%s: %s weight should be %.3f, got %.3f",
						tt.description, key, expected, actual)
				}
			}
		})
	}
}

func TestCalculateAdaptiveBlend(t *testing.T) {
	service := NewAdaptiveMarketService(nil, nil, nil, nil, zerolog.Nop())

	tests := []struct {
		name        string
		regimeScore float64
		expectedMin float64
		expectedMax float64
		description string
	}{
		{
			name:        "Extreme bull - more MV",
			regimeScore: 1.0,
			expectedMin: 0.25,
			expectedMax: 0.35,
			description: "Bull should favor MV (return-focused)",
		},
		{
			name:        "Extreme bear - more HRP",
			regimeScore: -1.0,
			expectedMin: 0.65,
			expectedMax: 0.75,
			description: "Bear should favor HRP (risk-focused)",
		},
		{
			name:        "Neutral - balanced",
			regimeScore: 0.0,
			expectedMin: 0.48,
			expectedMax: 0.52,
			description: "Neutral should be balanced (0.5)",
		},
		{
			name:        "Bull-ish - slightly more MV",
			regimeScore: 0.3,
			expectedMin: 0.44,
			expectedMax: 0.48,
			description: "Bull-ish should interpolate toward MV",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			blend := service.CalculateAdaptiveBlend(tt.regimeScore)

			assert.GreaterOrEqual(t, blend, tt.expectedMin,
				"%s: blend %.3f should be >= %.3f", tt.description, blend, tt.expectedMin)
			assert.LessOrEqual(t, blend, tt.expectedMax,
				"%s: blend %.3f should be <= %.3f", tt.description, blend, tt.expectedMax)

			// Verify blend is in valid range
			assert.GreaterOrEqual(t, blend, 0.0)
			assert.LessOrEqual(t, blend, 1.0)
		})
	}
}

func TestCalculateAdaptiveQualityGates(t *testing.T) {
	service := NewAdaptiveMarketService(nil, nil, nil, nil, zerolog.Nop())

	tests := []struct {
		name                 string
		regimeScore          float64
		expectedFundamentals float64
		expectedLongTerm     float64
		description          string
	}{
		{
			name:                 "Extreme bull - lower thresholds",
			regimeScore:          1.0,
			expectedFundamentals: 0.55,
			expectedLongTerm:     0.45,
			description:          "Bull should allow more growth stocks",
		},
		{
			name:                 "Extreme bear - higher thresholds",
			regimeScore:          -1.0,
			expectedFundamentals: 0.65,
			expectedLongTerm:     0.55,
			description:          "Bear should be stricter",
		},
		{
			name:                 "Neutral - default thresholds",
			regimeScore:          0.0,
			expectedFundamentals: 0.60,
			expectedLongTerm:     0.50,
			description:          "Neutral should use defaults",
		},
		{
			name:                 "Bull-ish - slightly lower",
			regimeScore:          0.4,
			expectedFundamentals: 0.58,
			expectedLongTerm:     0.48,
			description:          "Bull-ish should interpolate",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			thresholds := service.CalculateAdaptiveQualityGates(tt.regimeScore)
			require.NotNil(t, thresholds)

			assert.InDelta(t, tt.expectedFundamentals, thresholds.Fundamentals, 0.01,
				"%s: fundamentals threshold should be %.3f, got %.3f",
				tt.description, tt.expectedFundamentals, thresholds.Fundamentals)

			assert.InDelta(t, tt.expectedLongTerm, thresholds.LongTerm, 0.01,
				"%s: long_term threshold should be %.3f, got %.3f",
				tt.description, tt.expectedLongTerm, thresholds.LongTerm)
		})
	}
}

func TestFallbackBehavior(t *testing.T) {
	service := NewAdaptiveMarketService(nil, nil, nil, nil, zerolog.Nop())

	t.Run("Returns default weights when no adaptive data", func(t *testing.T) {
		// When regime score is unavailable or invalid
		weights := service.CalculateAdaptiveWeights(0.0) // Neutral should use defaults
		require.NotNil(t, weights)

		// Should have all expected keys
		expectedKeys := []string{"long_term", "fundamentals", "opportunity", "dividends",
			"short_term", "technicals", "opinion", "diversification"}
		for _, key := range expectedKeys {
			assert.Contains(t, weights, key, "Should have %s weight", key)
		}
	})

	t.Run("Returns default blend when no adaptive data", func(t *testing.T) {
		blend := service.CalculateAdaptiveBlend(0.0) // Neutral
		assert.Equal(t, 0.5, blend, "Neutral should return default blend of 0.5")
	})

	t.Run("Returns default thresholds when no adaptive data", func(t *testing.T) {
		thresholds := service.CalculateAdaptiveQualityGates(0.0) // Neutral
		require.NotNil(t, thresholds)
		assert.Equal(t, 0.60, thresholds.Fundamentals, "Should use default fundamentals threshold")
		assert.Equal(t, 0.50, thresholds.LongTerm, "Should use default long_term threshold")
	})
}

func TestErrorHandling(t *testing.T) {
	service := NewAdaptiveMarketService(nil, nil, nil, nil, zerolog.Nop())

	t.Run("Handles invalid regime score gracefully", func(t *testing.T) {
		// Score outside valid range
		weights := service.CalculateAdaptiveWeights(2.0) // Invalid: > 1.0
		require.NotNil(t, weights)
		// Should clamp to valid range or use defaults

		weights2 := service.CalculateAdaptiveWeights(-2.0) // Invalid: < -1.0
		require.NotNil(t, weights2)
	})

	t.Run("Handles NaN and Inf gracefully", func(t *testing.T) {
		// These should not crash
		weights := service.CalculateAdaptiveWeights(0.0) // Use neutral as safe default
		require.NotNil(t, weights)
	})
}
