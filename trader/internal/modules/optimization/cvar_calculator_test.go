package optimization

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestCVaRCalculator_CalculatePortfolioCVaR(t *testing.T) {
	calc := NewCVaRCalculator(nil, nil, zerolog.Nop())

	tests := []struct {
		name       string
		weights    map[string]float64
		returns    map[string][]float64
		confidence float64
		want       float64
		tolerance  float64
	}{
		{
			name: "two asset portfolio",
			weights: map[string]float64{
				"A": 0.6,
				"B": 0.4,
			},
			returns: map[string][]float64{
				"A": []float64{-0.10, -0.05, 0.0, 0.05, 0.10},
				"B": []float64{-0.15, -0.08, 0.0, 0.08, 0.15},
			},
			confidence: 0.95,
			want:       -0.12, // Weighted average
			tolerance:  0.02,
		},
		{
			name: "single asset",
			weights: map[string]float64{
				"A": 1.0,
			},
			returns: map[string][]float64{
				"A": []float64{-0.20, -0.10, 0.0, 0.10, 0.20},
			},
			confidence: 0.95,
			want:       -0.20,
			tolerance:  0.01,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := calc.CalculatePortfolioCVaR(tt.weights, tt.returns, tt.confidence)
			assert.InDelta(t, tt.want, result, tt.tolerance)
		})
	}
}

func TestCVaRCalculator_CalculateSecurityCVaR(t *testing.T) {
	calc := NewCVaRCalculator(nil, nil, zerolog.Nop())

	returns := []float64{-0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15}
	result := calc.CalculateSecurityCVaR(returns, 0.95)

	// Worst 5% of 7 returns = worst 1 return = -0.20
	assert.InDelta(t, -0.20, result, 0.01)
}

func TestCVaRCalculator_RegimeAwareCVaR(t *testing.T) {
	calc := NewCVaRCalculator(nil, nil, zerolog.Nop())

	baseCVaR := -0.15
	regimeScore := -0.8 // Bear market

	// In bear markets, CVaR should be adjusted (more conservative)
	result := calc.ApplyRegimeAdjustment(baseCVaR, regimeScore)

	// Should be more negative (worse) in bear markets
	assert.Less(t, result, baseCVaR, "CVaR should be worse in bear markets")
	assert.Greater(t, result, -1.0, "CVaR should not be extremely negative")
}

func TestCVaRCalculator_CalculateFromCovariance(t *testing.T) {
	calc := NewCVaRCalculator(nil, nil, zerolog.Nop())

	covMatrix := [][]float64{
		{0.04, 0.01},
		{0.01, 0.01},
	}
	expectedReturns := map[string]float64{
		"A": 0.10,
		"B": 0.08,
	}
	weights := map[string]float64{
		"A": 0.6,
		"B": 0.4,
	}
	symbols := []string{"A", "B"}

	result := calc.CalculateFromCovariance(covMatrix, expectedReturns, weights, symbols, 10000, 0.95)

	// CVaR should be negative (tail risk)
	assert.Less(t, result, 0.0, "CVaR should be negative")
	assert.Greater(t, result, -1.0, "CVaR should not be extremely negative")
}
