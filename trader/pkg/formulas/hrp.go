package formulas

import (
	"fmt"
	"math"
)

// CorrelationMatrixFromCovariance calculates the correlation matrix from a covariance matrix.
//
// Formula: corr(i,j) = cov(i,j) / sqrt(cov(i,i) * cov(j,j))
func CorrelationMatrixFromCovariance(cov [][]float64) ([][]float64, error) {
	n := len(cov)
	if n == 0 {
		return nil, fmt.Errorf("empty covariance matrix")
	}
	for i := 0; i < n; i++ {
		if len(cov[i]) != n {
			return nil, fmt.Errorf("covariance matrix is not square")
		}
	}

	vars := make([]float64, n)
	for i := 0; i < n; i++ {
		v := cov[i][i]
		if v <= 0 || math.IsNaN(v) || math.IsInf(v, 0) {
			return nil, fmt.Errorf("invalid variance on diagonal at %d: %v", i, v)
		}
		vars[i] = v
	}

	corr := make([][]float64, n)
	for i := 0; i < n; i++ {
		corr[i] = make([]float64, n)
	}

	for i := 0; i < n; i++ {
		corr[i][i] = 1.0
		for j := i + 1; j < n; j++ {
			den := math.Sqrt(vars[i] * vars[j])
			val := 0.0
			if den > 0 {
				val = cov[i][j] / den
			}
			// Clamp to valid range.
			val = math.Max(-1.0, math.Min(1.0, val))
			corr[i][j] = val
			corr[j][i] = val
		}
	}

	return corr, nil
}

// CorrelationToDistance converts correlation matrix to distance matrix.
// Distance formula: d_ij = sqrt(2 * (1 - ρ_ij))
// where ρ_ij is the correlation between assets i and j.
//
// This is used in hierarchical clustering for HRP optimization.
//
// Args:
//   - corrMatrix: Correlation matrix
//
// Returns:
//   - Distance matrix where distance[i][j] is the distance between assets i and j
func CorrelationToDistance(corrMatrix [][]float64) [][]float64 {
	n := len(corrMatrix)
	distMatrix := make([][]float64, n)

	for i := 0; i < n; i++ {
		distMatrix[i] = make([]float64, n)
		for j := 0; j < n; j++ {
			corr := corrMatrix[i][j]
			// Clamp correlation to valid range
			corr = math.Max(-1.0, math.Min(1.0, corr))
			distMatrix[i][j] = math.Sqrt(2.0 * (1.0 - corr))
		}
	}

	return distMatrix
}

// InverseVarianceWeights calculates risk parity weights using inverse variance weighting.
// This is a simplified HRP implementation that achieves risk parity without full dendrogram traversal.
//
// Formula: w_i = (1/v_i) / Σ(1/v_j)
// where v_i is the variance of asset i.
//
// This gives higher weights to assets with lower variance (lower risk).
//
// Args:
//   - variances: Vector of variances for each asset
//
// Returns:
//   - Vector of weights (sums to 1.0)
func InverseVarianceWeights(variances []float64) []float64 {
	n := len(variances)
	weights := make([]float64, n)

	var totalInvVariance float64
	for _, v := range variances {
		if v > 0 {
			totalInvVariance += 1.0 / v
		}
	}

	if totalInvVariance == 0 {
		// If all variances are zero or invalid, use equal weights
		for i := range weights {
			weights[i] = 1.0 / float64(n)
		}
		return weights
	}

	for i, v := range variances {
		if v > 0 {
			weights[i] = (1.0 / v) / totalInvVariance
		} else {
			weights[i] = 0.0
		}
	}

	return weights
}
