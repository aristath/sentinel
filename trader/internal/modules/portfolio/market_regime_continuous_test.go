package portfolio

import (
	"math"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

// TestCalculateRegimeScore tests the continuous regime score calculation with tanh transformation
func TestCalculateRegimeScore(t *testing.T) {
	detector := NewMarketRegimeDetector(zerolog.Nop())

	tests := []struct {
		name            string
		returnComponent float64 // Normalized return component (-1.0 to +1.0)
		volComponent    float64 // Normalized volatility component (-1.0 to +1.0, inverted)
		ddComponent     float64 // Normalized drawdown component (-1.0 to +1.0, inverted)
		expectedMin     float64 // Minimum expected score
		expectedMax     float64 // Maximum expected score
		description     string
	}{
		{
			name:            "Extreme bull - all positive components",
			returnComponent: 1.0, // Strong positive returns
			volComponent:    0.8, // Low volatility (inverted, so positive)
			ddComponent:     0.9, // Small drawdown (inverted, so positive)
			expectedMin:     0.8,
			expectedMax:     1.0,
			description:     "Should be close to +1.0 (extreme bull)",
		},
		{
			name:            "Extreme bear - all negative components",
			returnComponent: -1.0, // Strong negative returns
			volComponent:    -0.8, // High volatility (inverted, so negative)
			ddComponent:     -0.9, // Large drawdown (inverted, so negative)
			expectedMin:     -1.0,
			expectedMax:     -0.8,
			description:     "Should be close to -1.0 (extreme bear)",
		},
		{
			name:            "Neutral - all zero components",
			returnComponent: 0.0,
			volComponent:    0.0,
			ddComponent:     0.0,
			expectedMin:     -0.1,
			expectedMax:     0.1,
			description:     "Should be close to 0.0 (neutral/sideways)",
		},
		{
			name:            "Bull-ish - moderate positive",
			returnComponent: 0.5, // Moderate positive returns
			volComponent:    0.3, // Moderate volatility
			ddComponent:     0.4, // Moderate drawdown
			expectedMin:     0.4,
			expectedMax:     0.8,
			description:     "Should be positive but not extreme (bull-ish)",
		},
		{
			name:            "Bear-ish - moderate negative",
			returnComponent: -0.5, // Moderate negative returns
			volComponent:    -0.3, // Moderate volatility
			ddComponent:     -0.4, // Moderate drawdown
			expectedMin:     -0.8,
			expectedMax:     -0.4,
			description:     "Should be negative but not extreme (bear-ish)",
		},
		{
			name:            "Mixed - positive return but high volatility",
			returnComponent: 0.6,  // Positive returns
			volComponent:    -0.5, // High volatility (negative)
			ddComponent:     0.3,  // Small drawdown
			expectedMin:     0.0,
			expectedMax:     0.5,
			description:     "High volatility should reduce score",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			score := detector.CalculateRegimeScore(tt.returnComponent, tt.volComponent, tt.ddComponent)

			assert.GreaterOrEqual(t, score, tt.expectedMin,
				"%s: score %.3f should be >= %.3f", tt.description, score, tt.expectedMin)
			assert.LessOrEqual(t, score, tt.expectedMax,
				"%s: score %.3f should be <= %.3f", tt.description, score, tt.expectedMax)

			// Verify score is in valid range
			assert.GreaterOrEqual(t, score, -1.0, "Score should be >= -1.0")
			assert.LessOrEqual(t, score, 1.0, "Score should be <= 1.0")
		})
	}
}

// TestTanhTransformation tests the tanh transformation behavior
func TestTanhTransformation(t *testing.T) {
	detector := NewMarketRegimeDetector(zerolog.Nop())

	tests := []struct {
		name        string
		rawScore    float64
		expectedMin float64
		expectedMax float64
		description string
	}{
		{
			name:        "Raw score 1.0 - should compress",
			rawScore:    1.0,
			expectedMin: 0.90, // tanh(2.0) ≈ 0.964
			expectedMax: 1.0,
			description: "Extreme positive should compress to ~0.96",
		},
		{
			name:        "Raw score -1.0 - should compress",
			rawScore:    -1.0,
			expectedMin: -1.0,
			expectedMax: -0.90, // tanh(-2.0) ≈ -0.964
			description: "Extreme negative should compress to ~-0.96",
		},
		{
			name:        "Raw score 0.5 - moderate compression",
			rawScore:    0.5,
			expectedMin: 0.70, // tanh(1.0) ≈ 0.762
			expectedMax: 0.80,
			description: "Moderate positive should compress less",
		},
		{
			name:        "Raw score 0.2 - minimal compression",
			rawScore:    0.2,
			expectedMin: 0.35, // tanh(0.4) ≈ 0.380
			expectedMax: 0.42,
			description: "Small positive should compress minimally (more sensitive)",
		},
		{
			name:        "Raw score -0.3 - minimal compression",
			rawScore:    -0.3,
			expectedMin: -0.55, // tanh(-0.6) ≈ -0.537
			expectedMax: -0.50,
			description: "Small negative should compress minimally (more sensitive)",
		},
		{
			name:        "Raw score 0.0 - no change",
			rawScore:    0.0,
			expectedMin: -0.01,
			expectedMax: 0.01,
			description: "Zero should remain zero",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Calculate components that would give this raw score
			// rawScore = (return * 0.5) + (vol * 0.25) + (dd * 0.25)
			// For simplicity, assume equal components
			component := tt.rawScore // Simplified: all components equal

			score := detector.CalculateRegimeScore(component, component, component)

			// The score should be tanh(rawScore * 2.0)
			expectedTanh := math.Tanh(tt.rawScore * 2.0)

			// Convert MarketRegimeScore to float64 for comparison
			scoreFloat := float64(score)
			assert.InDelta(t, expectedTanh, scoreFloat, 0.01,
				"%s: tanh transformation should give %.3f, got %.3f",
				tt.description, expectedTanh, scoreFloat)
		})
	}
}

// TestNormalizeComponents tests component normalization
func TestNormalizeComponents(t *testing.T) {
	detector := NewMarketRegimeDetector(zerolog.Nop())

	tests := []struct {
		name           string
		dailyReturn    float64
		volatility     float64
		maxDrawdown    float64
		expectedReturn float64 // Expected normalized return component
		expectedVol    float64 // Expected normalized vol component (inverted)
		expectedDD     float64 // Expected normalized DD component (inverted)
		description    string
	}{
		{
			name:           "Positive return normalizes to positive",
			dailyReturn:    0.001, // 0.1% daily
			volatility:     0.025, // 2.5% daily (above base of 2%, so negative)
			maxDrawdown:    -0.10, // 10% drawdown
			expectedReturn: 0.4,   // Should normalize to positive
			expectedVol:    -0.3,  // High vol should be negative (inverted)
			expectedDD:     -0.4,  // Large DD should be negative (inverted)
			description:    "Positive return should give positive component",
		},
		{
			name:           "Negative return normalizes to negative",
			dailyReturn:    -0.001, // -0.1% daily
			volatility:     0.025,  // 2.5% daily (above base of 2%, so negative)
			maxDrawdown:    -0.10,  // 10% drawdown
			expectedReturn: -0.4,   // Should normalize to negative
			expectedVol:    -0.3,   // High vol should be negative (inverted)
			expectedDD:     -0.4,   // Large DD should be negative (inverted)
			description:    "Negative return should give negative component",
		},
		{
			name:           "Low volatility normalizes to positive (inverted)",
			dailyReturn:    0.0005,
			volatility:     0.01,  // 1% daily (low)
			maxDrawdown:    -0.05, // 5% drawdown
			expectedReturn: 0.2,
			expectedVol:    0.2,  // Low vol should be positive (inverted)
			expectedDD:     -0.2, // Small DD should be less negative
			description:    "Low volatility should give positive component (inverted)",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			returnComp := detector.NormalizeReturn(tt.dailyReturn)
			volComp := detector.NormalizeVolatility(tt.volatility)
			ddComp := detector.NormalizeDrawdown(tt.maxDrawdown)

			// Verify components are in valid range
			assert.GreaterOrEqual(t, returnComp, -1.0)
			assert.LessOrEqual(t, returnComp, 1.0)
			assert.GreaterOrEqual(t, volComp, -1.0)
			assert.LessOrEqual(t, volComp, 1.0)
			assert.GreaterOrEqual(t, ddComp, -1.0)
			assert.LessOrEqual(t, ddComp, 1.0)

			// Check direction (sign) matches expectation
			if tt.expectedReturn > 0 {
				assert.Greater(t, returnComp, 0.0, "Return component should be positive")
			} else if tt.expectedReturn < 0 {
				assert.Less(t, returnComp, 0.0, "Return component should be negative")
			}

			if tt.expectedVol > 0 {
				assert.Greater(t, volComp, 0.0, "Vol component should be positive (low vol)")
			} else if tt.expectedVol < 0 {
				assert.Less(t, volComp, 0.0, "Vol component should be negative (high vol)")
			}
		})
	}
}

// TestExponentialSmoothing tests the exponential moving average smoothing
func TestExponentialSmoothing(t *testing.T) {
	detector := NewMarketRegimeDetector(zerolog.Nop())

	tests := []struct {
		name         string
		currentScore float64
		lastSmoothed float64
		alpha        float64
		expectedMin  float64
		expectedMax  float64
		description  string
	}{
		{
			name:         "First score - no smoothing",
			currentScore: 0.5,
			lastSmoothed: 0.0, // No previous value
			alpha:        0.1,
			expectedMin:  0.4,
			expectedMax:  0.6,
			description:  "First score should be close to current",
		},
		{
			name:         "Smooth transition - gradual change",
			currentScore: 0.8,
			lastSmoothed: 0.2,
			alpha:        0.1,
			expectedMin:  0.25, // 0.1 * 0.8 + 0.9 * 0.2 = 0.26
			expectedMax:  0.30,
			description:  "Smoothing should prevent sudden jumps",
		},
		{
			name:         "High alpha - more responsive",
			currentScore: 0.8,
			lastSmoothed: 0.2,
			alpha:        0.5,
			expectedMin:  0.45, // 0.5 * 0.8 + 0.5 * 0.2 = 0.5
			expectedMax:  0.55,
			description:  "Higher alpha should be more responsive",
		},
		{
			name:         "Low alpha - very smooth",
			currentScore: 0.8,
			lastSmoothed: 0.2,
			alpha:        0.05,
			expectedMin:  0.22, // 0.05 * 0.8 + 0.95 * 0.2 = 0.23
			expectedMax:  0.25,
			description:  "Lower alpha should be smoother",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			smoothed := detector.ApplySmoothing(tt.currentScore, tt.lastSmoothed, tt.alpha)

			assert.GreaterOrEqual(t, smoothed, tt.expectedMin,
				"%s: smoothed %.3f should be >= %.3f", tt.description, smoothed, tt.expectedMin)
			assert.LessOrEqual(t, smoothed, tt.expectedMax,
				"%s: smoothed %.3f should be <= %.3f", tt.description, smoothed, tt.expectedMax)

			// Verify smoothed score is in valid range
			assert.GreaterOrEqual(t, smoothed, -1.0)
			assert.LessOrEqual(t, smoothed, 1.0)
		})
	}
}

// TestCalculateRegimeScoreFromReturns tests calculating regime score from raw returns
func TestCalculateRegimeScoreFromReturns(t *testing.T) {
	detector := NewMarketRegimeDetector(zerolog.Nop())

	tests := []struct {
		name        string
		returns     []float64
		expectedMin float64
		expectedMax float64
		description string
	}{
		{
			name:        "Bull market returns",
			returns:     []float64{0.001, 0.002, 0.0015, 0.001, 0.002}, // Positive returns
			expectedMin: 0.3,
			expectedMax: 0.8,
			description: "Positive returns should give positive score",
		},
		{
			name:        "Bear market returns",
			returns:     []float64{-0.001, -0.002, -0.0015, -0.001, -0.002}, // Negative returns
			expectedMin: -0.8,
			expectedMax: -0.3,
			description: "Negative returns should give negative score",
		},
		{
			name:        "Sideways returns",
			returns:     []float64{0.0001, -0.0001, 0.0002, -0.0002, 0.0}, // Near zero
			expectedMin: -0.3,
			expectedMax: 0.3,
			description: "Near-zero returns should give near-zero score",
		},
		{
			name:        "High volatility returns",
			returns:     []float64{0.03, -0.02, 0.025, -0.015, 0.02}, // High volatility
			expectedMin: -0.2,
			expectedMax: 0.75, // Adjusted for tanh compression and normalization
			description: "High volatility should reduce score (but positive returns still matter)",
		},
		{
			name:        "Empty returns",
			returns:     []float64{},
			expectedMin: -0.1,
			expectedMax: 0.1,
			description: "Empty returns should give neutral score",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			score := detector.CalculateRegimeScoreFromReturns(tt.returns)

			assert.GreaterOrEqual(t, score, tt.expectedMin,
				"%s: score %.3f should be >= %.3f", tt.description, score, tt.expectedMin)
			assert.LessOrEqual(t, score, tt.expectedMax,
				"%s: score %.3f should be <= %.3f", tt.description, score, tt.expectedMax)

			// Verify score is in valid range
			assert.GreaterOrEqual(t, score, -1.0)
			assert.LessOrEqual(t, score, 1.0)
		})
	}
}

// TestToDiscreteRegime tests backward compatibility conversion
func TestToDiscreteRegime(t *testing.T) {
	detector := NewMarketRegimeDetector(zerolog.Nop())

	tests := []struct {
		name           string
		regimeScore    float64
		expectedRegime MarketRegime
		description    string
	}{
		{
			name:           "Extreme bull converts to bull",
			regimeScore:    0.8,
			expectedRegime: MarketRegimeBull,
			description:    "Score > 0.33 should be bull",
		},
		{
			name:           "Moderate bull converts to bull",
			regimeScore:    0.5,
			expectedRegime: MarketRegimeBull,
			description:    "Score > 0.33 should be bull",
		},
		{
			name:           "Extreme bear converts to bear",
			regimeScore:    -0.8,
			expectedRegime: MarketRegimeBear,
			description:    "Score < -0.33 should be bear",
		},
		{
			name:           "Moderate bear converts to bear",
			regimeScore:    -0.5,
			expectedRegime: MarketRegimeBear,
			description:    "Score < -0.33 should be bear",
		},
		{
			name:           "Neutral converts to sideways",
			regimeScore:    0.0,
			expectedRegime: MarketRegimeSideways,
			description:    "Score between -0.33 and 0.33 should be sideways",
		},
		{
			name:           "Bull-ish converts to bull",
			regimeScore:    0.2, // Above 0.15 threshold
			expectedRegime: MarketRegimeBull,
			description:    "Score above 0.15 threshold should be bull",
		},
		{
			name:           "Bear-ish converts to bear",
			regimeScore:    -0.2, // Below -0.15 threshold
			expectedRegime: MarketRegimeBear,
			description:    "Score below -0.15 threshold should be bear",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			regime := detector.ToDiscreteRegime(tt.regimeScore)
			assert.Equal(t, tt.expectedRegime, regime,
				"%s: score %.3f should convert to %v, got %v",
				tt.description, tt.regimeScore, tt.expectedRegime, regime)
		})
	}
}
