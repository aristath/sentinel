package optimization

import (
	"fmt"
	"math"

	"github.com/aristath/arduino-trader/pkg/formulas"
)

// HRPOptimizer performs Hierarchical Risk Parity portfolio optimization.
type HRPOptimizer struct{}

// NewHRPOptimizer creates a new HRP optimizer.
func NewHRPOptimizer() *HRPOptimizer {
	return &HRPOptimizer{}
}

type hrpClusterNode struct {
	left    *hrpClusterNode
	right   *hrpClusterNode
	leaves  []int
	minLeaf int
}

// Optimize solves the HRP optimization problem using a full HRP implementation:
// 1) Correlation from covariance
// 2) Distance: d_ij = sqrt(2 * (1 - ρ_ij))
// 3) Hierarchical clustering (single linkage, deterministic tie-break)
// 4) Quasi-diagonalization (leaf order from dendrogram)
// 5) Recursive bisection allocation (cluster variance via IVP)
func (hrp *HRPOptimizer) Optimize(
	covMatrix [][]float64,
	symbols []string,
) (map[string]float64, error) {
	if len(symbols) == 0 {
		return nil, fmt.Errorf("no symbols provided")
	}

	if len(symbols) == 1 {
		// Single asset: all weight to that asset
		return map[string]float64{symbols[0]: 1.0}, nil
	}

	if len(covMatrix) != len(symbols) {
		return nil, fmt.Errorf("covariance matrix size %d does not match symbols %d", len(covMatrix), len(symbols))
	}
	for i := 0; i < len(covMatrix); i++ {
		if len(covMatrix[i]) != len(symbols) {
			return nil, fmt.Errorf("covariance matrix is not square")
		}
	}

	corrMatrix, err := formulas.CorrelationMatrixFromCovariance(covMatrix)
	if err != nil {
		return nil, fmt.Errorf("failed to calculate correlation matrix from covariance: %w", err)
	}

	distMatrix := formulas.CorrelationToDistance(corrMatrix)

	root := hrp.singleLinkageDendrogram(distMatrix)
	order := hrp.quasiDiagonalOrder(root)
	if len(order) != len(symbols) {
		return nil, fmt.Errorf("invalid HRP order length %d", len(order))
	}

	weights := make([]float64, len(symbols))
	for i := range weights {
		weights[i] = 1.0
	}
	hrp.recursiveBisectionAllocate(weights, covMatrix, order)

	// Normalize and map back to symbols
	sum := 0.0
	for _, w := range weights {
		sum += w
	}
	if sum <= 0 || math.IsNaN(sum) || math.IsInf(sum, 0) {
		return nil, fmt.Errorf("invalid HRP weight sum: %v", sum)
	}

	result := make(map[string]float64)
	for i, symbol := range symbols {
		result[symbol] = weights[i] / sum
	}

	return result, nil
}

func (hrp *HRPOptimizer) singleLinkageDendrogram(dist [][]float64) *hrpClusterNode {
	n := len(dist)
	clusters := make([]*hrpClusterNode, 0, n)
	for i := 0; i < n; i++ {
		clusters = append(clusters, &hrpClusterNode{
			left:    nil,
			right:   nil,
			leaves:  []int{i},
			minLeaf: i,
		})
	}

	// Agglomerative clustering with deterministic tie-break.
	for len(clusters) > 1 {
		bestI := 0
		bestJ := 1
		bestD := hrp.clusterDistanceSingleLinkage(dist, clusters[0], clusters[1])

		for i := 0; i < len(clusters); i++ {
			for j := i + 1; j < len(clusters); j++ {
				d := hrp.clusterDistanceSingleLinkage(dist, clusters[i], clusters[j])
				if d < bestD || (d == bestD && hrp.clusterPairLess(clusters[i], clusters[j], clusters[bestI], clusters[bestJ])) {
					bestD = d
					bestI = i
					bestJ = j
				}
			}
		}

		a := clusters[bestI]
		b := clusters[bestJ]
		left := a
		right := b
		if right.minLeaf < left.minLeaf {
			left, right = right, left
		}

		mergedLeaves := make([]int, 0, len(a.leaves)+len(b.leaves))
		mergedLeaves = append(mergedLeaves, a.leaves...)
		mergedLeaves = append(mergedLeaves, b.leaves...)
		minLeaf := left.minLeaf
		if right.minLeaf < minLeaf {
			minLeaf = right.minLeaf
		}

		merged := &hrpClusterNode{
			left:    left,
			right:   right,
			leaves:  mergedLeaves,
			minLeaf: minLeaf,
		}

		// Remove indices bestI and bestJ, append merged.
		next := make([]*hrpClusterNode, 0, len(clusters)-1)
		for k := 0; k < len(clusters); k++ {
			if k == bestI || k == bestJ {
				continue
			}
			next = append(next, clusters[k])
		}
		next = append(next, merged)
		clusters = next
	}

	return clusters[0]
}

func (hrp *HRPOptimizer) clusterPairLess(a1, b1, a2, b2 *hrpClusterNode) bool {
	// Tie-break by (minLeaf, then second minLeaf) of the pair.
	x1, y1 := a1.minLeaf, b1.minLeaf
	if y1 < x1 {
		x1, y1 = y1, x1
	}
	x2, y2 := a2.minLeaf, b2.minLeaf
	if y2 < x2 {
		x2, y2 = y2, x2
	}
	if x1 != x2 {
		return x1 < x2
	}
	return y1 < y2
}

func (hrp *HRPOptimizer) clusterDistanceSingleLinkage(dist [][]float64, a, b *hrpClusterNode) float64 {
	best := math.Inf(1)
	for _, i := range a.leaves {
		for _, j := range b.leaves {
			d := dist[i][j]
			if d < best {
				best = d
			}
		}
	}
	return best
}

func (hrp *HRPOptimizer) quasiDiagonalOrder(node *hrpClusterNode) []int {
	if node == nil {
		return nil
	}
	if node.left == nil && node.right == nil {
		return []int{node.leaves[0]}
	}
	left := hrp.quasiDiagonalOrder(node.left)
	right := hrp.quasiDiagonalOrder(node.right)
	out := make([]int, 0, len(left)+len(right))
	out = append(out, left...)
	out = append(out, right...)
	return out
}

func (hrp *HRPOptimizer) recursiveBisectionAllocate(weights []float64, cov [][]float64, order []int) {
	if len(order) <= 1 {
		return
	}
	split := len(order) / 2
	left := order[:split]
	right := order[split:]

	vLeft := hrp.clusterVariance(cov, left)
	vRight := hrp.clusterVariance(cov, right)

	alpha := 0.5
	if vLeft+vRight > 0 {
		alpha = 1.0 - (vLeft / (vLeft + vRight))
	}
	alpha = math.Max(0.0, math.Min(1.0, alpha))

	for _, idx := range left {
		weights[idx] *= alpha
	}
	for _, idx := range right {
		weights[idx] *= (1.0 - alpha)
	}

	hrp.recursiveBisectionAllocate(weights, cov, left)
	hrp.recursiveBisectionAllocate(weights, cov, right)
}

func (hrp *HRPOptimizer) clusterVariance(cov [][]float64, idxs []int) float64 {
	if len(idxs) == 0 {
		return 0.0
	}
	if len(idxs) == 1 {
		i := idxs[0]
		return math.Max(cov[i][i], 0.0)
	}

	// Inverse-variance portfolio (IVP) within the cluster.
	eps := 1e-12
	inv := make([]float64, len(idxs))
	sumInv := 0.0
	for k, i := range idxs {
		v := cov[i][i]
		if v < eps {
			v = eps
		}
		inv[k] = 1.0 / v
		sumInv += inv[k]
	}
	if sumInv <= 0 {
		return 0.0
	}
	for k := range inv {
		inv[k] /= sumInv
	}

	// variance = w^T Σ w
	variance := 0.0
	for a, i := range idxs {
		for b, j := range idxs {
			variance += inv[a] * cov[i][j] * inv[b]
		}
	}
	return math.Max(variance, 0.0)
}
