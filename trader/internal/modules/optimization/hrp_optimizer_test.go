package optimization

import (
	"math"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestHRPOptimizer_DistanceMatrix(t *testing.T) {
	// Test correlation to distance conversion
	corrMatrix := [][]float64{
		{1.0, 0.8, 0.6},
		{0.8, 1.0, 0.7},
		{0.6, 0.7, 1.0},
	}

	distMatrix := correlationToDistance(corrMatrix)

	// Distance should be symmetric
	for i := 0; i < len(distMatrix); i++ {
		for j := 0; j < len(distMatrix); j++ {
			assert.InDelta(t, distMatrix[i][j], distMatrix[j][i], 1e-6, "distance matrix should be symmetric")
		}
	}

	// Distance should be non-negative
	for i := 0; i < len(distMatrix); i++ {
		for j := 0; j < len(distMatrix); j++ {
			assert.GreaterOrEqual(t, distMatrix[i][j], 0.0, "distances should be non-negative")
		}
		// Diagonal should be 0 (self-correlation = 1)
		assert.InDelta(t, 0.0, distMatrix[i][i], 1e-6, "self-distance should be 0")
	}

	// Higher correlation should lead to lower distance
	assert.Less(t, distMatrix[0][1], distMatrix[0][2], "higher correlation should have lower distance")
}

func TestHRPOptimizer_BasicOptimization(t *testing.T) {
	returns := map[string][]float64{
		"A": {0.01, 0.02, -0.01, 0.015, 0.005, 0.01, 0.02, -0.005},
		"B": {0.02, 0.03, -0.02, 0.025, 0.01, 0.015, 0.025, -0.01},
		"C": {0.015, 0.025, -0.015, 0.02, 0.008, 0.012, 0.022, -0.008},
	}
	symbols := []string{"A", "B", "C"}

	optimizer := NewHRPOptimizer()
	weights, err := optimizer.Optimize(returns, symbols)

	require.NoError(t, err)
	require.NotNil(t, weights)
	require.Len(t, weights, len(symbols))

	// Check weights sum to 1
	sum := 0.0
	for _, w := range weights {
		sum += w
		assert.GreaterOrEqual(t, w, 0.0, "weights should be non-negative")
		assert.LessOrEqual(t, w, 1.0, "weights should be <= 1")
	}
	assert.InDelta(t, 1.0, sum, 1e-4, "weights should sum to 1")
}

func TestHRPOptimizer_TwoAssets(t *testing.T) {
	returns := map[string][]float64{
		"A": {0.01, 0.02, -0.01, 0.015},
		"B": {0.02, 0.03, -0.02, 0.025},
	}
	symbols := []string{"A", "B"}

	optimizer := NewHRPOptimizer()
	weights, err := optimizer.Optimize(returns, symbols)

	require.NoError(t, err)
	require.NotNil(t, weights)

	sum := 0.0
	for _, w := range weights {
		sum += w
	}
	assert.InDelta(t, 1.0, sum, 1e-4)
}

func TestHRPOptimizer_HighCorrelation(t *testing.T) {
	// Two assets with very high correlation should get similar weights
	returns := map[string][]float64{
		"A": {0.01, 0.02, -0.01, 0.015, 0.005},
		"B": {0.011, 0.021, -0.011, 0.016, 0.006}, // Very similar to A
		"C": {0.05, 0.04, -0.05, 0.03, 0.02},      // Different pattern
	}
	symbols := []string{"A", "B", "C"}

	optimizer := NewHRPOptimizer()
	weights, err := optimizer.Optimize(returns, symbols)

	require.NoError(t, err)

	// A and B should have similar weights (they're highly correlated)
	// This is a property of HRP - it groups correlated assets
	weightDiff := math.Abs(weights["A"] - weights["B"])
	assert.Less(t, weightDiff, 0.2, "highly correlated assets should have similar weights")
}

func TestHRPOptimizer_RecursiveBisection(t *testing.T) {
	// Test that recursive bisection allocates correctly
	// For a simple 2-asset case, weights should be inversely proportional to variance
	returns := map[string][]float64{
		"LOW_VOL":  {0.01, 0.01, 0.01, 0.01, 0.01},   // Low volatility
		"HIGH_VOL": {0.05, -0.05, 0.05, -0.05, 0.05}, // High volatility
	}
	symbols := []string{"LOW_VOL", "HIGH_VOL"}

	optimizer := NewHRPOptimizer()
	weights, err := optimizer.Optimize(returns, symbols)

	require.NoError(t, err)

	// In risk parity, lower volatility should get higher weight
	// HRP should allocate more to LOW_VOL
	assert.Greater(t, weights["LOW_VOL"], weights["HIGH_VOL"], "lower volatility asset should get higher weight in HRP")
}
