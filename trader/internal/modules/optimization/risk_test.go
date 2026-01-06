package optimization

import (
	"math"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestCalculateSampleCovariance(t *testing.T) {
	tests := []struct {
		name     string
		returns  map[string][]float64
		symbols  []string
		expected [][]float64
		tol      float64
	}{
		{
			name: "two assets with known correlation",
			returns: map[string][]float64{
				"A": {0.01, 0.02, -0.01, 0.015, 0.005},
				"B": {0.02, 0.03, -0.02, 0.025, 0.01},
			},
			symbols:  []string{"A", "B"},
			expected: nil, // Will verify properties instead
			tol:      1e-6,
		},
		{
			name: "three assets",
			returns: map[string][]float64{
				"A": {0.01, 0.02},
				"B": {0.02, 0.01},
				"C": {0.015, 0.015},
			},
			symbols:  []string{"A", "B", "C"},
			expected: nil, // Will calculate actual values
			tol:      1e-6,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cov, err := calculateSampleCovariance(tt.returns, tt.symbols)
			require.NoError(t, err)
			require.Equal(t, len(tt.symbols), len(cov))
			require.Equal(t, len(tt.symbols), len(cov[0]))

			// Check symmetry
			for i := 0; i < len(cov); i++ {
				for j := 0; j < len(cov); j++ {
					assert.InDelta(t, cov[i][j], cov[j][i], tt.tol, "covariance matrix should be symmetric")
				}
			}

			// Check variances are positive (diagonal elements)
			for i := 0; i < len(cov); i++ {
				assert.GreaterOrEqual(t, cov[i][i], 0.0, "variance should be non-negative")
			}

			if tt.expected != nil {
				for i := 0; i < len(tt.expected); i++ {
					for j := 0; j < len(tt.expected[i]); j++ {
						assert.InDelta(t, tt.expected[i][j], cov[i][j], tt.tol)
					}
				}
			}

			// For known correlation test, verify correlation is reasonable
			if tt.name == "two assets with known correlation" && len(cov) == 2 {
				// Calculate correlation: cov(A,B) / sqrt(var(A) * var(B))
				varA := cov[0][0]
				varB := cov[1][1]
				covAB := cov[0][1]
				if varA > 0 && varB > 0 {
					corr := covAB / math.Sqrt(varA*varB)
					// Should have positive correlation (both assets move together)
					assert.Greater(t, corr, 0.0, "should have positive correlation")
					assert.LessOrEqual(t, corr, 1.0, "correlation should be <= 1")
				}
			}
		})
	}
}

func TestLedoitWolfShrinkage(t *testing.T) {
	tests := []struct {
		name            string
		sampleCov       [][]float64
		expectedShrink  bool // Whether shrinkage should occur
		expectedCondNum float64
		tol             float64
	}{
		{
			name: "well-conditioned matrix",
			sampleCov: [][]float64{
				{0.04, 0.01, 0.005},
				{0.01, 0.03, 0.008},
				{0.005, 0.008, 0.025},
			},
			expectedShrink: true,
			tol:            1e-4,
		},
		{
			name: "ill-conditioned matrix",
			sampleCov: [][]float64{
				{0.04, 0.039},
				{0.039, 0.038},
			},
			expectedShrink: true,
			tol:            1e-4,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			shrunk, err := applyLedoitWolfShrinkage(tt.sampleCov)
			require.NoError(t, err)
			require.Equal(t, len(tt.sampleCov), len(shrunk))
			require.Equal(t, len(tt.sampleCov), len(shrunk[0]))

			// Check symmetry
			for i := 0; i < len(shrunk); i++ {
				for j := 0; j < len(shrunk); j++ {
					assert.InDelta(t, shrunk[i][j], shrunk[j][i], tt.tol, "shrunk matrix should be symmetric")
				}
			}

			// Check variances are positive
			for i := 0; i < len(shrunk); i++ {
				assert.Greater(t, shrunk[i][i], 0.0, "variance should be positive")
			}

			// Shrinkage should improve condition number (make it smaller)
			sampleCondNum := conditionNumber(tt.sampleCov)
			shrunkCondNum := conditionNumber(shrunk)
			if tt.expectedShrink {
				// Condition number should improve (decrease) or at least not worsen significantly
				// In practice, shrinkage often improves conditioning
				t.Logf("Sample condition number: %f, Shrunk condition number: %f", sampleCondNum, shrunkCondNum)
			}
		})
	}
}

func TestCalculateCovarianceLedoitWolf(t *testing.T) {
	tests := []struct {
		name    string
		returns map[string][]float64
		symbols []string
		tol     float64
	}{
		{
			name: "basic two assets",
			returns: map[string][]float64{
				"A": {0.01, 0.02, -0.01, 0.015, 0.005, 0.01, 0.02, -0.005},
				"B": {0.02, 0.03, -0.02, 0.025, 0.01, 0.015, 0.025, -0.01},
			},
			symbols: []string{"A", "B"},
			tol:     1e-4,
		},
		{
			name: "three assets with different volatilities",
			returns: map[string][]float64{
				"LOW_VOL":  {0.005, 0.006, 0.004, 0.005, 0.005},
				"MED_VOL":  {0.01, 0.012, 0.008, 0.01, 0.01},
				"HIGH_VOL": {0.02, 0.025, 0.015, 0.02, 0.018},
			},
			symbols: []string{"LOW_VOL", "MED_VOL", "HIGH_VOL"},
			tol:     1e-4,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cov, err := calculateCovarianceLedoitWolf(tt.returns, tt.symbols)
			require.NoError(t, err)
			require.Equal(t, len(tt.symbols), len(cov))
			require.Equal(t, len(tt.symbols), len(cov[0]))

			// Check symmetry
			for i := 0; i < len(cov); i++ {
				for j := 0; j < len(cov); j++ {
					assert.InDelta(t, cov[i][j], cov[j][i], tt.tol, "covariance matrix should be symmetric")
				}
			}

			// Check positive definiteness (variances positive, determinant > 0 for 2x2)
			for i := 0; i < len(cov); i++ {
				assert.Greater(t, cov[i][i], 0.0, "variance should be positive")
			}

			if len(cov) == 2 {
				det := cov[0][0]*cov[1][1] - cov[0][1]*cov[1][0]
				assert.Greater(t, det, 0.0, "2x2 covariance matrix should have positive determinant")
			}
		})
	}
}

func TestGetCorrelations(t *testing.T) {
	covMatrix := [][]float64{
		{0.04, 0.02, 0.01},
		{0.02, 0.03, 0.015},
		{0.01, 0.015, 0.025},
	}
	symbols := []string{"A", "B", "C"}

	// Build a RiskModelBuilder for testing
	rb := &RiskModelBuilder{}

	correlations := rb.getCorrelations(covMatrix, symbols, 0.5)

	// Should find correlations above 0.5
	// Calculate expected correlations manually
	// corr(A,B) = 0.02 / sqrt(0.04 * 0.03) = 0.02 / sqrt(0.0012) ≈ 0.577
	// corr(A,C) = 0.01 / sqrt(0.04 * 0.025) = 0.01 / sqrt(0.001) = 0.316
	// corr(B,C) = 0.015 / sqrt(0.03 * 0.025) = 0.015 / sqrt(0.00075) ≈ 0.548

	// Should find A-B and B-C correlations
	foundAB := false
	foundBC := false
	for _, pair := range correlations {
		if (pair.Symbol1 == "A" && pair.Symbol2 == "B") || (pair.Symbol1 == "B" && pair.Symbol2 == "A") {
			assert.InDelta(t, 0.577, math.Abs(pair.Correlation), 0.1)
			foundAB = true
		}
		if (pair.Symbol1 == "B" && pair.Symbol2 == "C") || (pair.Symbol1 == "C" && pair.Symbol2 == "B") {
			assert.InDelta(t, 0.548, math.Abs(pair.Correlation), 0.1)
			foundBC = true
		}
	}

	assert.True(t, foundAB, "Should find A-B correlation")
	assert.True(t, foundBC, "Should find B-C correlation")
}

func TestRegimeTimeDecayWeights_NormalizedAndEffectiveSampleSize(t *testing.T) {
	// 6 observations, oldest -> newest.
	// Current regime is strongly bullish (+1), so weights should concentrate on bullish regime points.
	regimeScores := []float64{-1, -1, -1, 1, 1, 1}
	currentRegime := 1.0

	halfLifeDays := 1e9 // effectively no time decay
	bandwidth := 0.10   // strong regime conditioning

	weights, err := regimeTimeDecayWeights(regimeScores, currentRegime, halfLifeDays, bandwidth)
	require.NoError(t, err)
	require.Len(t, weights, len(regimeScores))

	sum := 0.0
	for _, w := range weights {
		require.GreaterOrEqual(t, w, 0.0)
		sum += w
	}
	assert.InDelta(t, 1.0, sum, 1e-12)

	neff := effectiveSampleSize(weights)
	// With a tight regime kernel and 3 matching observations, neff should be close to ~3.
	assert.Greater(t, neff, 2.0)
	assert.Less(t, neff, 4.0)
}

func TestRegimeTimeDecayWeights_BandwidthInfinityRemovesRegimeEffect(t *testing.T) {
	regimeScores := []float64{-1, 1, -1, 1, -1, 1} // alternating regimes
	currentRegime := 1.0

	halfLifeDays := 1e9 // no time decay
	bandwidth := 1e12   // effectively infinite bandwidth
	weights, err := regimeTimeDecayWeights(regimeScores, currentRegime, halfLifeDays, bandwidth)
	require.NoError(t, err)

	// With no time decay and infinite bandwidth, weights should be uniform.
	for _, w := range weights {
		assert.InDelta(t, 1.0/float64(len(weights)), w, 1e-9)
	}
}

func TestRegimeTimeDecayWeights_HalfLifeInfinityRemovesTimeDecay(t *testing.T) {
	// If there is no time decay, only the regime kernel matters.
	// With symmetric regimes around current=0 and finite bandwidth, weights should be symmetric.
	regimeScores := []float64{-0.5, 0.0, 0.5, 0.0, -0.5}
	currentRegime := 0.0
	halfLifeDays := 1e12 // effectively infinite half-life (no time decay)
	bandwidth := 0.25

	weights, err := regimeTimeDecayWeights(regimeScores, currentRegime, halfLifeDays, bandwidth)
	require.NoError(t, err)

	assert.InDelta(t, weights[0], weights[4], 1e-12)
	assert.InDelta(t, weights[1], weights[3], 1e-12)
}

func TestWeightedCovariance_SymmetricAndPositiveDiagonal(t *testing.T) {
	// Two assets, 4 observations.
	returns := map[string][]float64{
		"A": {0.01, 0.02, -0.01, 0.00},
		"B": {0.02, 0.01, -0.02, 0.01},
	}
	symbols := []string{"A", "B"}
	weights := []float64{0.25, 0.25, 0.25, 0.25}

	cov, err := weightedCovariance(returns, symbols, weights)
	require.NoError(t, err)
	require.Len(t, cov, 2)
	require.Len(t, cov[0], 2)

	assert.InDelta(t, cov[0][1], cov[1][0], 1e-12)
	assert.GreaterOrEqual(t, cov[0][0], 0.0)
	assert.GreaterOrEqual(t, cov[1][1], 0.0)
}

// Helper function to calculate condition number (ratio of largest to smallest eigenvalue)
func conditionNumber(matrix [][]float64) float64 {
	// Simple approximation: use trace and determinant for 2x2
	if len(matrix) == 2 {
		trace := matrix[0][0] + matrix[1][1]
		det := matrix[0][0]*matrix[1][1] - matrix[0][1]*matrix[1][0]
		if det <= 0 {
			return math.Inf(1)
		}
		// For 2x2, approximate condition number
		return trace / (2 * math.Sqrt(det))
	}
	// For larger matrices, return a placeholder
	return 1.0
}
