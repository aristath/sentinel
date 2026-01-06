package optimization

import (
	"math"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestMVOptimizer_EfficientReturn(t *testing.T) {
	// Simple 2-asset case
	expectedReturns := map[string]float64{
		"A": 0.12, // 12% expected return
		"B": 0.08, // 8% expected return
	}
	covMatrix := [][]float64{
		{0.04, 0.01},
		{0.01, 0.03},
	}
	symbols := []string{"A", "B"}
	bounds := [][2]float64{
		{0.0, 1.0},
		{0.0, 1.0},
	}
	targetReturn := 0.10 // 10%

	optimizer := NewMVOptimizer()
	weights, achievedReturn, err := optimizer.Optimize(
		expectedReturns,
		covMatrix,
		symbols,
		bounds,
		nil, // no sector constraints
		"efficient_return",
		&targetReturn,
		nil, // no target volatility
	)

	require.NoError(t, err)
	require.NotNil(t, weights)
	require.Len(t, weights, len(symbols))

	// Check weights sum to approximately 1
	sum := 0.0
	for _, w := range weights {
		sum += w
		assert.GreaterOrEqual(t, w, 0.0, "weights should be non-negative")
		assert.LessOrEqual(t, w, 1.0, "weights should be <= 1")
	}
	assert.InDelta(t, 1.0, sum, 1e-4, "weights should sum to 1")

	// Check achieved return is close to target
	if achievedReturn != nil {
		assert.InDelta(t, targetReturn, *achievedReturn, 0.01, "achieved return should be close to target")
	}

	// Check bounds are satisfied
	for i, symbol := range symbols {
		w := weights[symbol]
		assert.GreaterOrEqual(t, w, bounds[i][0], "weight should satisfy lower bound")
		assert.LessOrEqual(t, w, bounds[i][1], "weight should satisfy upper bound")
	}
}

func TestMVOptimizer_MinVolatility(t *testing.T) {
	expectedReturns := map[string]float64{
		"A": 0.12,
		"B": 0.08,
		"C": 0.10,
	}
	covMatrix := [][]float64{
		{0.04, 0.01, 0.005},
		{0.01, 0.03, 0.008},
		{0.005, 0.008, 0.025},
	}
	symbols := []string{"A", "B", "C"}
	bounds := [][2]float64{
		{0.0, 1.0},
		{0.0, 1.0},
		{0.0, 1.0},
	}

	optimizer := NewMVOptimizer()
	weights1, _, err1 := optimizer.Optimize(
		expectedReturns,
		covMatrix,
		symbols,
		bounds,
		nil,
		"min_volatility",
		nil, // target return not used
		nil,
	)

	require.NoError(t, err1)
	require.NotNil(t, weights1)

	// Calculate portfolio volatility for min_volatility solution
	vol1 := calculatePortfolioVolatility(weights1, covMatrix, symbols)

	// Try another solution and verify min_volatility is lower
	targetRet := 0.11
	weights2, _, err2 := optimizer.Optimize(
		expectedReturns,
		covMatrix,
		symbols,
		bounds,
		nil,
		"efficient_return",
		&targetRet, // higher return target
		nil,
	)
	require.NoError(t, err2)
	vol2 := calculatePortfolioVolatility(weights2, covMatrix, symbols)

	// Min volatility portfolio should have lower or equal volatility
	assert.LessOrEqual(t, vol1, vol2, "min_volatility should have lower volatility than efficient_return")
}

func TestMVOptimizer_MaxSharpe(t *testing.T) {
	expectedReturns := map[string]float64{
		"A": 0.12,
		"B": 0.08,
	}
	covMatrix := [][]float64{
		{0.04, 0.01},
		{0.01, 0.03},
	}
	symbols := []string{"A", "B"}
	bounds := [][2]float64{
		{0.0, 1.0},
		{0.0, 1.0},
	}

	optimizer := NewMVOptimizer()
	weights, achievedReturn, err := optimizer.Optimize(
		expectedReturns,
		covMatrix,
		symbols,
		bounds,
		nil,
		"max_sharpe",
		nil,
		nil,
	)

	require.NoError(t, err)
	require.NotNil(t, weights)

	sum := 0.0
	for _, w := range weights {
		sum += w
	}
	assert.InDelta(t, 1.0, sum, 1e-4)

	// Calculate Sharpe ratio (assuming risk-free rate = 0)
	if achievedReturn != nil {
		vol := math.Sqrt(calculatePortfolioVolatility(weights, covMatrix, symbols))
		sharpe := *achievedReturn / vol
		assert.Greater(t, sharpe, 0.0, "Sharpe ratio should be positive")
	}
}

func TestMVOptimizer_WithSectorConstraints(t *testing.T) {
	expectedReturns := map[string]float64{
		"TECH1": 0.15,
		"TECH2": 0.14,
		"FIN1":  0.10,
		"FIN2":  0.09,
	}
	covMatrix := [][]float64{
		{0.04, 0.03, 0.01, 0.01},
		{0.03, 0.04, 0.01, 0.01},
		{0.01, 0.01, 0.03, 0.02},
		{0.01, 0.01, 0.02, 0.03},
	}
	symbols := []string{"TECH1", "TECH2", "FIN1", "FIN2"}
	bounds := [][2]float64{
		{0.0, 1.0},
		{0.0, 1.0},
		{0.0, 1.0},
		{0.0, 1.0},
	}

	sectorConstraints := []SectorConstraint{
		{
			SectorMapper: map[string]string{
				"TECH1": "TECH",
				"TECH2": "TECH",
			},
			SectorLower: map[string]float64{"TECH": 0.3},
			SectorUpper: map[string]float64{"TECH": 0.6},
		},
		{
			SectorMapper: map[string]string{
				"FIN1": "FIN",
				"FIN2": "FIN",
			},
			SectorLower: map[string]float64{"FIN": 0.2},
			SectorUpper: map[string]float64{"FIN": 0.5},
		},
	}

	optimizer := NewMVOptimizer()
	weights, _, err := optimizer.Optimize(
		expectedReturns,
		covMatrix,
		symbols,
		bounds,
		sectorConstraints,
		"min_volatility",
		nil,
		nil,
	)

	require.NoError(t, err)
	require.NotNil(t, weights)

	// Check sector constraints are satisfied
	techWeight := weights["TECH1"] + weights["TECH2"]
	finWeight := weights["FIN1"] + weights["FIN2"]

	// Allow small tolerance for numerical precision
	tol := 1e-2
	assert.GreaterOrEqual(t, techWeight, 0.3-tol, "TECH sector should meet lower bound")
	assert.LessOrEqual(t, techWeight, 0.6+tol, "TECH sector should meet upper bound")
	assert.GreaterOrEqual(t, finWeight, 0.2-tol, "FIN sector should meet lower bound")
	assert.LessOrEqual(t, finWeight, 0.5+tol, "FIN sector should meet upper bound")
}

func TestMVOptimizer_InfeasibleConstraints(t *testing.T) {
	expectedReturns := map[string]float64{
		"A": 0.12,
		"B": 0.08,
	}
	covMatrix := [][]float64{
		{0.04, 0.01},
		{0.01, 0.03},
	}
	symbols := []string{"A", "B"}
	bounds := [][2]float64{
		{0.0, 0.3}, // Upper bound 30%
		{0.0, 0.3}, // Upper bound 30%
	}
	targetReturn := 0.11 // Higher return than achievable with these bounds

	optimizer := NewMVOptimizer()
	weights, _, err := optimizer.Optimize(
		expectedReturns,
		covMatrix,
		symbols,
		bounds,
		nil,
		"efficient_return",
		&targetReturn,
		nil,
	)

	// Should either return error or return best-effort solution
	if err != nil {
		assert.Contains(t, err.Error(), "infeasible", "should indicate infeasibility")
	} else {
		// If it returns weights, verify they're valid even if not meeting target
		require.NotNil(t, weights)
		sum := 0.0
		for _, w := range weights {
			sum += w
		}
		assert.InDelta(t, 1.0, sum, 1e-4)
	}
}

// Helper function to calculate portfolio volatility: sqrt(w' * Σ * w)
func calculatePortfolioVolatility(weights map[string]float64, covMatrix [][]float64, symbols []string) float64 {
	var variance float64

	for i, symbolI := range symbols {
		wi := weights[symbolI]
		for j, symbolJ := range symbols {
			wj := weights[symbolJ]
			variance += wi * wj * covMatrix[i][j]
		}
	}

	return variance // Return variance (volatility would be sqrt(variance))
}
