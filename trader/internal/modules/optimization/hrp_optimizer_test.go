package optimization

import (
	"math"
	"testing"

	"github.com/aristath/arduino-trader/pkg/formulas"
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

	distMatrix := formulas.CorrelationToDistance(corrMatrix)

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
	symbols := []string{"A", "B", "C"}
	// Covariance with two correlated assets (A,B) and one diversifier (C)
	cov := [][]float64{
		{0.0400, 0.0300, 0.0000},
		{0.0300, 0.0450, 0.0000},
		{0.0000, 0.0000, 0.0100},
	}

	optimizer := NewHRPOptimizer()
	weights, err := optimizer.Optimize(cov, symbols)

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
	symbols := []string{"A", "B"}
	cov := [][]float64{
		{0.0100, 0.0000},
		{0.0000, 0.0400},
	}

	optimizer := NewHRPOptimizer()
	weights, err := optimizer.Optimize(cov, symbols)

	require.NoError(t, err)
	require.NotNil(t, weights)

	sum := 0.0
	for _, w := range weights {
		sum += w
	}
	assert.InDelta(t, 1.0, sum, 1e-4)

	// For 2 assets, HRP reduces to inverse-variance weighting.
	// Expected weights: wA = vB/(vA+vB), wB = vA/(vA+vB)
	vA := cov[0][0]
	vB := cov[1][1]
	require.Greater(t, vA, 0.0)
	require.Greater(t, vB, 0.0)
	expectedA := vB / (vA + vB)
	expectedB := vA / (vA + vB)
	assert.InDelta(t, expectedA, weights["A"], 1e-6)
	assert.InDelta(t, expectedB, weights["B"], 1e-6)
}

func TestHRPOptimizer_HighCorrelation(t *testing.T) {
	symbols := []string{"A", "B", "C"}
	// A and B are highly correlated; C is less correlated and lower variance.
	cov := [][]float64{
		{0.0400, 0.0380, 0.0020},
		{0.0380, 0.0410, 0.0020},
		{0.0020, 0.0020, 0.0100},
	}

	optimizer := NewHRPOptimizer()
	weights, err := optimizer.Optimize(cov, symbols)

	require.NoError(t, err)

	// A and B should have similar weights (they're highly correlated)
	// This is a property of HRP - it groups correlated assets
	weightDiff := math.Abs(weights["A"] - weights["B"])
	assert.Less(t, weightDiff, 0.2, "highly correlated assets should have similar weights")
}

func TestHRPOptimizer_Deterministic(t *testing.T) {
	symbols := []string{"A", "B", "C", "D"}
	cov := [][]float64{
		{0.0400, 0.0350, 0.0000, 0.0000},
		{0.0350, 0.0450, 0.0000, 0.0000},
		{0.0000, 0.0000, 0.0200, 0.0150},
		{0.0000, 0.0000, 0.0150, 0.0250},
	}

	optimizer := NewHRPOptimizer()
	w1, err := optimizer.Optimize(cov, symbols)
	require.NoError(t, err)
	w2, err := optimizer.Optimize(cov, symbols)
	require.NoError(t, err)

	require.Len(t, w1, len(symbols))
	require.Len(t, w2, len(symbols))
	for _, s := range symbols {
		assert.InDelta(t, w1[s], w2[s], 1e-12, "weights should be deterministic")
	}
}
