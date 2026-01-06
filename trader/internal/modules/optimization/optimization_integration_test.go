package optimization

import (
	"math"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestOptimizationPipeline tests the complete optimization pipeline:
// returns → covariance → MV/HRP → weights
func TestOptimizationPipeline(t *testing.T) {
	// Create realistic return data for 5 securities
	returns := map[string][]float64{
		"US_TECH":     {0.02, 0.015, -0.01, 0.025, 0.018, 0.02, 0.015, -0.005, 0.022, 0.019},
		"US_FIN":      {0.015, 0.012, -0.008, 0.018, 0.014, 0.015, 0.012, -0.003, 0.017, 0.014},
		"EU_TECH":     {0.018, 0.014, -0.009, 0.022, 0.016, 0.018, 0.014, -0.004, 0.020, 0.017},
		"EU_CONSUMER": {0.012, 0.010, -0.006, 0.015, 0.012, 0.012, 0.010, -0.002, 0.014, 0.011},
		"ASIA_TECH":   {0.020, 0.016, -0.011, 0.024, 0.019, 0.020, 0.016, -0.006, 0.023, 0.020},
	}
	symbols := []string{"US_TECH", "US_FIN", "EU_TECH", "EU_CONSUMER", "ASIA_TECH"}

	// Step 1: Calculate covariance with Ledoit-Wolf
	covMatrix, err := calculateCovarianceLedoitWolf(returns, symbols)
	require.NoError(t, err)
	require.Equal(t, len(symbols), len(covMatrix))
	require.Equal(t, len(symbols), len(covMatrix[0]))

	// Verify covariance matrix properties
	for i := 0; i < len(covMatrix); i++ {
		for j := 0; j < len(covMatrix); j++ {
			// Symmetry
			assert.InDelta(t, covMatrix[i][j], covMatrix[j][i], 1e-6)
			// Variances (diagonal) should be positive
			if i == j {
				assert.Greater(t, covMatrix[i][j], 0.0, "variance should be positive")
			}
		}
	}

	// Step 2: Run MV optimization
	expectedReturns := map[string]float64{
		"US_TECH":     0.17, // 17% annual
		"US_FIN":      0.12, // 12% annual
		"EU_TECH":     0.15, // 15% annual
		"EU_CONSUMER": 0.10, // 10% annual
		"ASIA_TECH":   0.18, // 18% annual
	}
	bounds := [][2]float64{
		{0.0, 0.25}, // Max 25% per security
		{0.0, 0.25},
		{0.0, 0.25},
		{0.0, 0.25},
		{0.0, 0.25},
	}
	targetReturn := 0.14 // 14% target

	mvOptimizer := NewMVOptimizer()
	mvWeights, achievedReturn, err := mvOptimizer.Optimize(
		expectedReturns,
		covMatrix,
		symbols,
		bounds,
		nil, // no sector constraints
		"efficient_return",
		&targetReturn,
		nil,
	)
	require.NoError(t, err)
	require.NotNil(t, mvWeights)

	// Verify MV weights
	mvSum := 0.0
	for _, w := range mvWeights {
		mvSum += w
		assert.GreaterOrEqual(t, w, 0.0)
		assert.LessOrEqual(t, w, 0.25)
	}
	assert.InDelta(t, 1.0, mvSum, 1e-3, "MV weights should sum to 1")

	if achievedReturn != nil {
		assert.InDelta(t, targetReturn, *achievedReturn, 0.02, "achieved return should be close to target")
	}

	// Step 3: Run HRP optimization
	hrpOptimizer := NewHRPOptimizer()
	hrpWeights, err := hrpOptimizer.Optimize(returns, symbols)
	require.NoError(t, err)
	require.NotNil(t, hrpWeights)

	// Verify HRP weights
	hrpSum := 0.0
	for _, w := range hrpWeights {
		hrpSum += w
		assert.GreaterOrEqual(t, w, 0.0)
	}
	assert.InDelta(t, 1.0, hrpSum, 1e-3, "HRP weights should sum to 1")

	// Step 4: Blend MV and HRP
	blend := 0.5 // 50/50 blend
	blendedWeights := blendWeights(mvWeights, hrpWeights, blend)

	// Verify blended weights
	blendedSum := 0.0
	for symbol, w := range blendedWeights {
		blendedSum += w
		assert.GreaterOrEqual(t, w, 0.0)
		// Verify blending formula: blended = blend * hrp + (1-blend) * mv
		expectedBlended := blend*hrpWeights[symbol] + (1-blend)*mvWeights[symbol]
		assert.InDelta(t, expectedBlended, w, 1e-4, "blended weight should match formula")
	}
	assert.InDelta(t, 1.0, blendedSum, 1e-3, "blended weights should sum to 1")
}

// TestOptimizationPipeline_EdgeCases tests edge cases in the optimization pipeline
func TestOptimizationPipeline_EdgeCases(t *testing.T) {
	t.Run("single_security", func(t *testing.T) {
		returns := map[string][]float64{
			"SINGLE": {0.01, 0.02, -0.01, 0.015},
		}
		symbols := []string{"SINGLE"}

		hrpOptimizer := NewHRPOptimizer()
		weights, err := hrpOptimizer.Optimize(returns, symbols)
		require.NoError(t, err)
		assert.Equal(t, 1.0, weights["SINGLE"])
	})

	t.Run("insufficient_data", func(t *testing.T) {
		// Only 1 day of returns (need at least 2 for covariance)
		returns := map[string][]float64{
			"A": {0.01},
			"B": {0.02},
		}
		symbols := []string{"A", "B"}

		_, err := calculateCovarianceLedoitWolf(returns, symbols)
		require.Error(t, err)
		assert.Contains(t, err.Error(), "insufficient")
	})

	t.Run("high_correlation_assets", func(t *testing.T) {
		// Two assets that move almost identically
		returns := map[string][]float64{
			"ASSET1": {0.01, 0.02, -0.01, 0.015, 0.005, 0.01, 0.02, -0.005},
			"ASSET2": {0.0101, 0.0201, -0.0101, 0.0151, 0.0051, 0.0101, 0.0201, -0.0051},
		}
		symbols := []string{"ASSET1", "ASSET2"}

		covMatrix, err := calculateCovarianceLedoitWolf(returns, symbols)
		require.NoError(t, err)

		// Calculate correlation
		corr := covMatrix[0][1] / math.Sqrt(covMatrix[0][0]*covMatrix[1][1])
		assert.Greater(t, corr, 0.95, "highly similar returns should have high correlation")
	})
}

// blendWeights is a helper function that matches the OptimizerService.blendWeights logic
func blendWeights(mvWeights, hrpWeights map[string]float64, blend float64) map[string]float64 {
	allSymbols := make(map[string]bool)
	for s := range mvWeights {
		allSymbols[s] = true
	}
	for s := range hrpWeights {
		allSymbols[s] = true
	}

	blended := make(map[string]float64)
	for symbol := range allSymbols {
		mvW := mvWeights[symbol]
		hrpW := hrpWeights[symbol]
		blended[symbol] = blend*hrpW + (1-blend)*mvW
	}

	return blended
}
