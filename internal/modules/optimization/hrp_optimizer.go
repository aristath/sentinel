package optimization

import (
	"fmt"
	"math"

	"github.com/aristath/sentinel/pkg/formulas"
)

type hrpLinkage string

const (
	hrpLinkageSingle   hrpLinkage = "single"
	hrpLinkageComplete hrpLinkage = "complete"
	hrpLinkageAverage  hrpLinkage = "average"
)

type HRPOptions struct {
	Linkage hrpLinkage
}

func defaultHRPOptions() HRPOptions {
	return HRPOptions{Linkage: hrpLinkageSingle}
}

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
// 3) Hierarchical clustering (configurable linkage, deterministic tie-break)
// 4) Quasi-diagonalization (leaf order from dendrogram)
// 5) Recursive bisection allocation (cluster variance via IVP)
// All parameters and returns use ISIN keys (not Symbol keys).
func (hrp *HRPOptimizer) Optimize(
	covMatrix [][]float64,
	isins []string, // ISIN array ✅ (renamed from symbols)
) (map[string]float64, error) {
	return hrp.OptimizeWithOptions(covMatrix, isins, defaultHRPOptions())
}

func (hrp *HRPOptimizer) OptimizeWithOptions(
	covMatrix [][]float64,
	isins []string, // ISIN array ✅ (renamed from symbols)
	opts HRPOptions,
) (map[string]float64, error) {
	if len(isins) == 0 {
		return nil, fmt.Errorf("no ISINs provided")
	}

	if len(isins) == 1 {
		// Single asset: all weight to that asset
		return map[string]float64{isins[0]: 1.0}, nil // ISIN key ✅
	}

	if len(covMatrix) != len(isins) {
		return nil, fmt.Errorf("covariance matrix size %d does not match ISINs %d", len(covMatrix), len(isins))
	}
	for i := 0; i < len(covMatrix); i++ {
		if len(covMatrix[i]) != len(isins) {
			return nil, fmt.Errorf("covariance matrix is not square")
		}
	}

	corrMatrix, err := formulas.CorrelationMatrixFromCovariance(covMatrix)
	if err != nil {
		return nil, fmt.Errorf("failed to calculate correlation matrix from covariance: %w", err)
	}

	distMatrix := formulas.CorrelationToDistance(corrMatrix)

	linkage := opts.Linkage
	if linkage == "" {
		linkage = hrpLinkageSingle
	}

	root := hrp.buildDendrogram(distMatrix, linkage)
	order := hrp.quasiDiagonalOrder(root)
	if len(order) != len(isins) {
		return nil, fmt.Errorf("invalid HRP order length %d", len(order))
	}

	weights := make([]float64, len(isins))
	for i := range weights {
		weights[i] = 1.0
	}
	hrp.recursiveBisectionAllocate(weights, covMatrix, order)

	// Normalize and map back to ISINs
	sum := 0.0
	for _, w := range weights {
		sum += w
	}
	if sum <= 0 || math.IsNaN(sum) || math.IsInf(sum, 0) {
		return nil, fmt.Errorf("invalid HRP weight sum: %v", sum)
	}

	result := make(map[string]float64)
	for i, isin := range isins { // Use ISIN ✅
		result[isin] = weights[i] / sum // ISIN key ✅
	}

	return result, nil
}

func (hrp *HRPOptimizer) buildDendrogram(dist [][]float64, linkage hrpLinkage) *hrpClusterNode {
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
		bestD := hrp.clusterDistance(dist, clusters[0], clusters[1], linkage)

		for i := 0; i < len(clusters); i++ {
			for j := i + 1; j < len(clusters); j++ {
				d := hrp.clusterDistance(dist, clusters[i], clusters[j], linkage)
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

func (hrp *HRPOptimizer) clusterDistance(dist [][]float64, a, b *hrpClusterNode, linkage hrpLinkage) float64 {
	switch linkage {
	case hrpLinkageComplete:
		best := 0.0
		first := true
		for _, i := range a.leaves {
			for _, j := range b.leaves {
				d := dist[i][j]
				if first || d > best {
					best = d
					first = false
				}
			}
		}
		return best
	case hrpLinkageAverage:
		sum := 0.0
		count := 0
		for _, i := range a.leaves {
			for _, j := range b.leaves {
				sum += dist[i][j]
				count++
			}
		}
		if count == 0 {
			return math.Inf(1)
		}
		return sum / float64(count)
	case hrpLinkageSingle:
		fallthrough
	default:
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
