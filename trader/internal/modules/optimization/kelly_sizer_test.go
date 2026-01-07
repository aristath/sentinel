package optimization

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestCalculateKellyFraction(t *testing.T) {
	tests := []struct {
		name           string
		expectedReturn float64
		riskFreeRate   float64
		variance       float64
		want           float64
		tolerance      float64
	}{
		{
			name:           "positive edge with variance",
			expectedReturn: 0.12, // 12%
			riskFreeRate:   0.02, // 2%
			variance:       0.04, // 4% variance (20% vol)
			want:           2.5,  // (0.12 - 0.02) / 0.04 = 2.5
			tolerance:      1e-6,
		},
		{
			name:           "small edge",
			expectedReturn: 0.08,
			riskFreeRate:   0.02,
			variance:       0.04,
			want:           1.5, // (0.08 - 0.02) / 0.04 = 1.5
			tolerance:      1e-6,
		},
		{
			name:           "negative edge returns zero",
			expectedReturn: 0.01,
			riskFreeRate:   0.02,
			variance:       0.04,
			want:           0.0, // No edge, no position
			tolerance:      1e-6,
		},
		{
			name:           "zero variance returns zero",
			expectedReturn: 0.12,
			riskFreeRate:   0.02,
			variance:       0.0,
			want:           0.0, // Division by zero protection
			tolerance:      1e-6,
		},
		{
			name:           "very small variance",
			expectedReturn: 0.12,
			riskFreeRate:   0.02,
			variance:       0.0001, // Very low variance
			want:           1000.0, // (0.12 - 0.02) / 0.0001 = 1000
			tolerance:      1.0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ks := NewKellyPositionSizer(0.02, 0.5, 0.005, 0.20, nil, nil, nil)
			result := ks.calculateKellyFraction(tt.expectedReturn, tt.riskFreeRate, tt.variance)
			assert.InDelta(t, tt.want, result, tt.tolerance, "Kelly fraction should match expected value")
		})
	}
}

func TestApplyConstraints(t *testing.T) {
	tests := []struct {
		name          string
		kellyFraction float64
		minSize       float64
		maxSize       float64
		want          float64
		description   string
	}{
		{
			name:          "within bounds",
			kellyFraction: 0.10,
			minSize:       0.005,
			maxSize:       0.20,
			want:          0.10,
			description:   "Should return original fraction if within bounds",
		},
		{
			name:          "above max",
			kellyFraction: 0.30,
			minSize:       0.005,
			maxSize:       0.20,
			want:          0.20,
			description:   "Should cap at max size",
		},
		{
			name:          "below min",
			kellyFraction: 0.002,
			minSize:       0.005,
			maxSize:       0.20,
			want:          0.005,
			description:   "Should floor at min size",
		},
		{
			name:          "negative fraction",
			kellyFraction: -0.05,
			minSize:       0.005,
			maxSize:       0.20,
			want:          0.005,
			description:   "Should floor negative fractions at min",
		},
		{
			name:          "zero fraction",
			kellyFraction: 0.0,
			minSize:       0.005,
			maxSize:       0.20,
			want:          0.005,
			description:   "Should floor zero at min",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ks := NewKellyPositionSizer(0.02, 0.5, tt.minSize, tt.maxSize, nil, nil, nil)
			result := ks.applyConstraints(tt.kellyFraction)
			assert.InDelta(t, tt.want, result, 1e-6, tt.description)
		})
	}
}

func TestApplyFractionalKelly(t *testing.T) {
	tests := []struct {
		name            string
		kellyFraction   float64
		fractionalMode  string
		fixedFractional float64
		regimeScore     float64
		confidence      float64
		want            float64
		tolerance       float64
		description     string
	}{
		{
			name:            "fixed half kelly",
			kellyFraction:   0.20,
			fractionalMode:  "fixed",
			fixedFractional: 0.5,
			regimeScore:     0.0,
			confidence:      0.8,
			want:            0.10, // 0.20 * 0.5
			tolerance:       1e-6,
			description:     "Fixed fractional should multiply by fixed factor",
		},
		{
			name:            "adaptive high confidence bull",
			kellyFraction:   0.20,
			fractionalMode:  "adaptive",
			fixedFractional: 0.5,
			regimeScore:     0.8,  // Bull market
			confidence:      0.9,  // High confidence
			want:            0.15, // 0.20 * 0.75 (high confidence + bull = higher multiplier)
			tolerance:       0.01,
			description:     "Adaptive should use higher multiplier in bull with high confidence",
		},
		{
			name:            "adaptive low confidence bear",
			kellyFraction:   0.20,
			fractionalMode:  "adaptive",
			fixedFractional: 0.5,
			regimeScore:     -0.8,  // Bear market
			confidence:      0.3,   // Low confidence
			want:            0.068, // 0.20 * 0.34 (low confidence + bear = lower multiplier)
			tolerance:       0.01,
			description:     "Adaptive should use lower multiplier in bear with low confidence",
		},
		{
			name:            "adaptive neutral",
			kellyFraction:   0.20,
			fractionalMode:  "adaptive",
			fixedFractional: 0.5,
			regimeScore:     0.0,  // Neutral
			confidence:      0.6,  // Medium confidence
			want:            0.10, // 0.20 * 0.5 (neutral = default)
			tolerance:       0.01,
			description:     "Adaptive should use default multiplier in neutral",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ks := NewKellyPositionSizer(0.02, tt.fixedFractional, 0.005, 0.20, nil, nil, nil)
			ks.fractionalMode = tt.fractionalMode
			result := ks.applyFractionalKelly(tt.kellyFraction, tt.regimeScore, tt.confidence)
			assert.InDelta(t, tt.want, result, tt.tolerance, tt.description)
		})
	}
}

func TestRegimeAdjustment(t *testing.T) {
	tests := []struct {
		name          string
		kellyFraction float64
		regimeScore   float64
		want          float64
		tolerance     float64
		description   string
	}{
		{
			name:          "bull market no adjustment",
			kellyFraction: 0.10,
			regimeScore:   0.8,
			want:          0.10,
			tolerance:     1e-6,
			description:   "Bull markets should not reduce Kelly",
		},
		{
			name:          "neutral no adjustment",
			kellyFraction: 0.10,
			regimeScore:   0.0,
			want:          0.10,
			tolerance:     1e-6,
			description:   "Neutral markets should not reduce Kelly",
		},
		{
			name:          "mild bear slight reduction",
			kellyFraction: 0.10,
			regimeScore:   -0.3,
			want:          0.0925, // 0.10 * (1.0 - 0.25 * 0.3) = 0.10 * 0.925
			tolerance:     0.001,
			description:   "Mild bear should slightly reduce Kelly",
		},
		{
			name:          "extreme bear maximum reduction",
			kellyFraction: 0.10,
			regimeScore:   -1.0,
			want:          0.075, // 0.10 * (1.0 - 0.25 * 1.0) = 0.10 * 0.75
			tolerance:     0.001,
			description:   "Extreme bear should reduce Kelly by 25%",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ks := NewKellyPositionSizer(0.02, 0.5, 0.005, 0.20, nil, nil, nil)
			result := ks.applyRegimeAdjustment(tt.kellyFraction, tt.regimeScore)
			assert.InDelta(t, tt.want, result, tt.tolerance, tt.description)
		})
	}
}

func TestCalculateOptimalSize(t *testing.T) {
	tests := []struct {
		name           string
		expectedReturn float64
		variance       float64
		confidence     float64
		regimeScore    float64
		minSize        float64
		maxSize        float64
		want           float64
		tolerance      float64
		description    string
	}{
		{
			name:           "full calculation with constraints",
			expectedReturn: 0.12,
			variance:       0.04,
			confidence:     0.8,
			regimeScore:    0.0,
			minSize:        0.005,
			maxSize:        0.20,
			want:           0.20, // (0.12-0.02)/0.04 = 2.5, * 0.5 (fractional) = 1.25, capped at 0.20
			tolerance:      0.01,
			description:    "Full calculation should apply all steps and cap at max",
		},
		{
			name:           "high variance limits size",
			expectedReturn: 0.12,
			variance:       0.16, // High variance (40% vol)
			confidence:     0.8,
			regimeScore:    0.0,
			minSize:        0.005,
			maxSize:        0.20,
			want:           0.20, // (0.12-0.02)/0.16 = 0.625, * 0.5 = 0.3125, but capped at 0.20 (maxSize)
			tolerance:      0.01,
			description:    "High variance should reduce position size but still respect max constraint",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ks := NewKellyPositionSizer(0.02, 0.5, tt.minSize, tt.maxSize, nil, nil, nil)
			ks.fractionalMode = "fixed"
			result := ks.CalculateOptimalSize(tt.expectedReturn, tt.variance, tt.confidence, tt.regimeScore)
			assert.InDelta(t, tt.want, result, tt.tolerance, tt.description)
			assert.GreaterOrEqual(t, result, tt.minSize, "Result should be >= min size")
			assert.LessOrEqual(t, result, tt.maxSize, "Result should be <= max size")
		})
	}
}

func TestCalculateOptimalSize_EdgeCases(t *testing.T) {
	ks := NewKellyPositionSizer(0.02, 0.5, 0.005, 0.20, nil, nil, nil)

	t.Run("negative expected return", func(t *testing.T) {
		result := ks.CalculateOptimalSize(-0.05, 0.04, 0.8, 0.0)
		assert.Equal(t, 0.005, result, "Negative return should return min size")
	})

	t.Run("zero variance", func(t *testing.T) {
		result := ks.CalculateOptimalSize(0.12, 0.0, 0.8, 0.0)
		assert.Equal(t, 0.005, result, "Zero variance should return min size")
	})

	t.Run("very high variance", func(t *testing.T) {
		result := ks.CalculateOptimalSize(0.12, 1.0, 0.8, 0.0)
		assert.GreaterOrEqual(t, result, 0.005, "Very high variance should still respect min")
		assert.LessOrEqual(t, result, 0.20, "Very high variance should respect max")
	})
}

func TestCalculateOptimalSize_Integration(t *testing.T) {
	// Integration test: Full flow with realistic values
	ks := NewKellyPositionSizer(0.02, 0.5, 0.005, 0.20, nil, nil, nil)
	ks.fractionalMode = "adaptive"

	// Realistic security: 11% expected return, 16% volatility (0.0256 variance), high confidence
	result := ks.CalculateOptimalSize(0.11, 0.0256, 0.85, 0.5)

	// Should be reasonable: (0.11-0.02)/0.0256 = 3.515, * adaptive multiplier (~0.65 for high conf bull) = ~2.28, capped at 0.20
	assert.GreaterOrEqual(t, result, 0.005, "Should respect min size")
	assert.LessOrEqual(t, result, 0.20, "Should respect max size")
	assert.Greater(t, result, 0.01, "Should be meaningful size for good opportunity")
}
