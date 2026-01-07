package formulas

import (
	"math"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestCalculateCVaR(t *testing.T) {
	tests := []struct {
		name        string
		returns     []float64
		confidence  float64
		want        float64
		tolerance   float64
		description string
	}{
		{
			name:        "normal distribution 95% confidence",
			returns:     []float64{-0.10, -0.05, -0.02, 0.0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.25},
			confidence:  0.95,
			want:        -0.10, // Worst 5% (10 * 0.05 = 0.5, rounded up to 1 return: -0.10)
			tolerance:   0.01,
			description: "CVaR should be average of worst 5% of returns",
		},
		{
			name:        "all negative returns",
			returns:     []float64{-0.20, -0.15, -0.10, -0.05, -0.02},
			confidence:  0.95,
			want:        -0.20, // Worst 5% (only 1 value)
			tolerance:   0.01,
			description: "CVaR should be worst return when all negative",
		},
		{
			name:        "mixed returns 99% confidence",
			returns:     []float64{-0.30, -0.20, -0.10, 0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60},
			confidence:  0.99,
			want:        -0.30, // Worst 1% (only 1 value)
			tolerance:   0.01,
			description: "CVaR at 99% should be worst return",
		},
		{
			name:        "single return",
			returns:     []float64{-0.10},
			confidence:  0.95,
			want:        -0.10,
			tolerance:   0.01,
			description: "CVaR with single return should be that return",
		},
		{
			name:        "empty returns",
			returns:     []float64{},
			confidence:  0.95,
			want:        0.0,
			tolerance:   0.01,
			description: "CVaR with no returns should be 0",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := CalculateCVaR(tt.returns, tt.confidence)
			assert.InDelta(t, tt.want, result, tt.tolerance, tt.description)
		})
	}
}

func TestCalculatePortfolioCVaR(t *testing.T) {
	tests := []struct {
		name        string
		weights     map[string]float64
		returns     map[string][]float64
		confidence  float64
		want        float64
		tolerance   float64
		description string
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
			confidence:  0.95,
			want:        -0.12, // Weighted average of worst returns
			tolerance:   0.02,
			description: "Portfolio CVaR should be weighted average of component CVaRs",
		},
		{
			name: "single asset",
			weights: map[string]float64{
				"A": 1.0,
			},
			returns: map[string][]float64{
				"A": []float64{-0.20, -0.10, 0.0, 0.10, 0.20},
			},
			confidence:  0.95,
			want:        -0.20,
			tolerance:   0.01,
			description: "Single asset portfolio CVaR should equal asset CVaR",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := CalculatePortfolioCVaR(tt.weights, tt.returns, tt.confidence)
			assert.InDelta(t, tt.want, result, tt.tolerance, tt.description)
		})
	}
}

func TestMonteCarloCVaR(t *testing.T) {
	// Test with known covariance matrix and expected returns
	covMatrix := [][]float64{
		{0.04, 0.01}, // 20% vol, 10% vol, 25% correlation
		{0.01, 0.01},
	}
	expectedReturns := map[string]float64{
		"A": 0.10,
		"B": 0.08,
	}
	symbols := []string{"A", "B"}

	// Run Monte Carlo simulation
	result := MonteCarloCVaR(covMatrix, expectedReturns, symbols, 10000, 0.95)

	// CVaR should be negative (tail risk)
	assert.Less(t, result, 0.0, "CVaR should be negative (tail risk)")

	// CVaR should be reasonable (not extreme)
	assert.Greater(t, result, -1.0, "CVaR should not be extremely negative")

	// CVaR should be less than worst-case single asset (portfolio diversification)
	worstAssetCVaR := -math.Sqrt(covMatrix[0][0]) * 1.645 // 95% VaR approximation
	assert.Less(t, math.Abs(result), math.Abs(worstAssetCVaR), "Portfolio CVaR should be better than worst asset due to diversification")
}

func TestCalculateCVaR_EdgeCases(t *testing.T) {
	t.Run("all positive returns", func(t *testing.T) {
		returns := []float64{0.05, 0.10, 0.15, 0.20}
		result := CalculateCVaR(returns, 0.95)
		// CVaR should be the worst return (least positive)
		assert.InDelta(t, 0.05, result, 0.01, "CVaR of all positive returns should be least positive")
	})

	t.Run("very small sample", func(t *testing.T) {
		returns := []float64{-0.10, 0.05}
		result := CalculateCVaR(returns, 0.95)
		// With 2 returns, 95% confidence = worst return
		assert.InDelta(t, -0.10, result, 0.01, "CVaR with 2 returns should be worst")
	})

	t.Run("duplicate returns", func(t *testing.T) {
		returns := []float64{-0.10, -0.10, -0.10, 0.05, 0.05, 0.05}
		result := CalculateCVaR(returns, 0.95)
		// Worst 5% = worst return
		assert.InDelta(t, -0.10, result, 0.01, "CVaR with duplicates should handle correctly")
	})
}
