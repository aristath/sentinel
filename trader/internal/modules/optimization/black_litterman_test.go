package optimization

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestBlackLittermanOptimizer_CalculateMarketEquilibrium(t *testing.T) {
	bl := NewBlackLittermanOptimizer(nil, nil, zerolog.Nop())

	tests := []struct {
		name         string
		weights      map[string]float64
		covMatrix    [][]float64
		riskAversion float64
		want         map[string]float64
		tolerance    float64
	}{
		{
			name: "two asset equal weights",
			weights: map[string]float64{
				"A": 0.5,
				"B": 0.5,
			},
			covMatrix: [][]float64{
				{0.04, 0.01},
				{0.01, 0.01},
			},
			riskAversion: 3.0,
			want: map[string]float64{
				"A": 0.075, // riskAversion * (Σ * w) = 3.0 * (0.04*0.5 + 0.01*0.5) = 3.0 * 0.025 = 0.075
				"B": 0.03,  // riskAversion * (Σ * w) = 3.0 * (0.01*0.5 + 0.01*0.5) = 3.0 * 0.01 = 0.03
			},
			tolerance: 0.01,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			symbols := []string{"A", "B"}
			result, err := bl.CalculateMarketEquilibrium(tt.weights, tt.covMatrix, symbols, tt.riskAversion)
			assert.NoError(t, err)
			assert.NotNil(t, result)
			for symbol, expected := range tt.want {
				if actual, hasActual := result[symbol]; hasActual {
					assert.InDelta(t, expected, actual, tt.tolerance, "Equilibrium return for %s", symbol)
				}
			}
		})
	}
}

func TestBlackLittermanOptimizer_BlendViewsWithEquilibrium(t *testing.T) {
	bl := NewBlackLittermanOptimizer(nil, nil, zerolog.Nop())

	equilibriumReturns := map[string]float64{
		"A": 0.10,
		"B": 0.08,
	}
	covMatrix := [][]float64{
		{0.04, 0.01},
		{0.01, 0.01},
	}
	symbols := []string{"A", "B"}

	// Simple view: A will outperform by 2%
	views := []View{
		{
			Type:       "absolute",
			Symbol:     "A",
			Return:     0.12, // 2% above equilibrium
			Confidence: 0.5,
		},
	}

	result, err := bl.BlendViewsWithEquilibrium(equilibriumReturns, views, covMatrix, symbols, 0.05, 0.5)
	assert.NoError(t, err)
	assert.NotNil(t, result)

	// A should have higher return than equilibrium due to positive view
	if aReturn, hasA := result["A"]; hasA {
		assert.Greater(t, aReturn, equilibriumReturns["A"], "A return should be higher than equilibrium")
	}
}

func TestBlackLittermanOptimizer_CalculateBLReturns(t *testing.T) {
	bl := NewBlackLittermanOptimizer(nil, nil, zerolog.Nop())

	equilibriumReturns := map[string]float64{
		"A": 0.10,
		"B": 0.08,
	}
	covMatrix := [][]float64{
		{0.04, 0.01},
		{0.01, 0.01},
	}
	symbols := []string{"A", "B"}
	views := []View{
		{
			Type:       "absolute",
			Symbol:     "A",
			Return:     0.12,
			Confidence: 0.5,
		},
	}

	result, err := bl.CalculateBLReturns(equilibriumReturns, views, covMatrix, symbols, 0.05, 0.5)
	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Len(t, result, 2, "Should return returns for all symbols")
}
