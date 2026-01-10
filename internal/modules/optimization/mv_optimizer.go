package optimization

import (
	"fmt"
	"math"

	"github.com/aristath/sentinel/internal/modules/settings"
	"gonum.org/v1/gonum/mat"
	"gonum.org/v1/gonum/optimize"
)

// MVOptimizer performs mean-variance portfolio optimization.
type MVOptimizer struct {
	cvarCalculator  *CVaRCalculator
	settingsService *settings.Service
}

// NewMVOptimizer creates a new mean-variance optimizer.
func NewMVOptimizer(cvarCalculator *CVaRCalculator, settingsService *settings.Service) *MVOptimizer {
	return &MVOptimizer{
		cvarCalculator:  cvarCalculator,
		settingsService: settingsService,
	}
}

// Optimize solves the mean-variance optimization problem.
// ALL PARAMETERS USE ISIN KEYS (not Symbol keys).
//
// Mathematical formulation:
//   - Objective depends on strategy:
//   - efficient_return: maximize μ'w - λ(w'Σw) subject to μ'w = target_return
//   - min_volatility: minimize w'Σw
//   - max_sharpe: maximize (μ'w - r_f) / sqrt(w'Σw) where r_f = 0
//   - efficient_risk: maximize μ'w subject to sqrt(w'Σw) = target_volatility
//
// Constraints:
//   - Σw = 1 (weights sum to 1)
//   - lower_i ≤ w_i ≤ upper_i (bounds from minWeights/maxWeights maps)
//   - Σ(w in sector) ≥ sector_lower, ≤ sector_upper (sector constraints)
func (mvo *MVOptimizer) Optimize(
	expectedReturns map[string]float64,  // ISIN-keyed ✅
	covMatrix [][]float64,
	isins []string,                      // ISIN array ✅ (renamed from symbols)
	minWeights map[string]float64,      // ISIN-keyed ✅ (replaces bounds array)
	maxWeights map[string]float64,      // ISIN-keyed ✅ (replaces bounds array)
	sectorConstraints []SectorConstraint,
	strategy string,
	targetReturn *float64,
	targetVolatility *float64,
) (map[string]float64, *float64, error) {
	n := len(isins)
	if n == 0 {
		return nil, nil, fmt.Errorf("no ISINs provided")
	}

	if len(covMatrix) != n {
		return nil, nil, fmt.Errorf("covariance matrix size %d doesn't match ISINs count %d", len(covMatrix), n)
	}

	for i := range covMatrix {
		if len(covMatrix[i]) != n {
			return nil, nil, fmt.Errorf("covariance matrix row %d has size %d, expected %d", i, len(covMatrix[i]), n)
		}
	}

	// Convert expected returns to vector (ordered by isins array)
	mu := make([]float64, n)
	for i, isin := range isins {
		ret, ok := expectedReturns[isin] // ISIN lookup ✅
		if !ok {
			return nil, nil, fmt.Errorf("missing expected return for ISIN %s", isin)
		}
		mu[i] = ret
	}

	// Convert covariance matrix to gonum matrix
	sigma := mat.NewDense(n, n, nil)
	for i := 0; i < n; i++ {
		for j := 0; j < n; j++ {
			sigma.Set(i, j, covMatrix[i][j])
		}
	}

	// Build optimization problem based on strategy
	switch strategy {
	case "efficient_return":
		if targetReturn == nil {
			return nil, nil, fmt.Errorf("target_return required for efficient_return strategy")
		}
		return mvo.optimizeEfficientReturn(mu, sigma, isins, minWeights, maxWeights, sectorConstraints, *targetReturn)
	case "min_volatility":
		return mvo.optimizeMinVolatility(mu, sigma, isins, minWeights, maxWeights, sectorConstraints)
	case "max_sharpe":
		return mvo.optimizeMaxSharpe(mu, sigma, isins, minWeights, maxWeights, sectorConstraints)
	case "efficient_risk":
		if targetVolatility == nil {
			return nil, nil, fmt.Errorf("target_volatility required for efficient_risk strategy")
		}
		return mvo.optimizeEfficientRisk(mu, sigma, isins, minWeights, maxWeights, sectorConstraints, *targetVolatility)
	default:
		return nil, nil, fmt.Errorf("unknown strategy: %s", strategy)
	}
}

// optimizeEfficientReturn maximizes μ'w - λ(w'Σw) subject to μ'w = target_return.
func (mvo *MVOptimizer) optimizeEfficientReturn(
	mu []float64,
	sigma *mat.Dense,
	isins []string,              // ISIN array ✅
	minWeights map[string]float64, // ISIN-keyed ✅
	maxWeights map[string]float64, // ISIN-keyed ✅
	sectorConstraints []SectorConstraint,
	targetReturn float64,
) (map[string]float64, *float64, error) {
	n := len(mu)
	lambda := 1.0 // Risk aversion parameter

	// Use penalty method for constraints
	penaltyWeight := 1000.0

	problem := optimize.Problem{
		Func: func(x []float64) float64 {
			// Project to bounds first
			xProj := mvo.projectToBoundsMap(x, isins, minWeights, maxWeights) // Use ISIN-keyed maps ✅

			// Calculate portfolio return: μ'w
			var portfolioReturn float64
			for i := 0; i < n; i++ {
				portfolioReturn += mu[i] * xProj[i]
			}

			// Calculate portfolio variance: w'Σw
			var portfolioVariance float64
			for i := 0; i < n; i++ {
				for j := 0; j < n; j++ {
					portfolioVariance += xProj[i] * xProj[j] * sigma.At(i, j)
				}
			}

			// Objective: minimize -(return - lambda * variance)
			obj := -(portfolioReturn - lambda*portfolioVariance)

			// Penalty for sum constraint: (sum - 1)^2
			sum := 0.0
			for i := 0; i < n; i++ {
				sum += xProj[i]
			}
			obj += penaltyWeight * (sum - 1.0) * (sum - 1.0)

			// Penalty for return constraint: (return - target)^2
			obj += penaltyWeight * (portfolioReturn - targetReturn) * (portfolioReturn - targetReturn)

			// Penalty for sector constraints
			obj += mvo.sectorConstraintPenalty(xProj, isins, sectorConstraints, penaltyWeight) // Use ISINs ✅

			return obj
		},
		Grad: func(grad, x []float64) {
			xProj := mvo.projectToBoundsMap(x, isins, minWeights, maxWeights) // Use ISIN maps ✅

			// Gradient of objective
			for i := 0; i < n; i++ {
				grad[i] = -mu[i]
				for j := 0; j < n; j++ {
					grad[i] += 2 * lambda * sigma.At(i, j) * xProj[j]
				}
			}

			// Gradient of sum penalty
			sum := 0.0
			for i := 0; i < n; i++ {
				sum += xProj[i]
			}
			for i := 0; i < n; i++ {
				grad[i] += 2 * penaltyWeight * (sum - 1.0)
			}

			// Gradient of return penalty
			var portfolioReturn float64
			for i := 0; i < n; i++ {
				portfolioReturn += mu[i] * xProj[i]
			}
			for i := 0; i < n; i++ {
				grad[i] += 2 * penaltyWeight * (portfolioReturn - targetReturn) * mu[i]
			}

			// Gradient of sector constraint penalty
			mvo.addSectorConstraintPenaltyGradient(grad, xProj, isins, sectorConstraints, penaltyWeight) // Use ISINs ✅
		},
	}

	initial := make([]float64, n)
	for i := range initial {
		initial[i] = 1.0 / float64(n)
	}

	result, err := optimize.Minimize(problem, initial, &optimize.Settings{}, &optimize.NelderMead{})
	if err != nil {
		return nil, nil, fmt.Errorf("optimization failed: %w", err)
	}

	// Accept various successful convergence statuses
	successStatuses := map[optimize.Status]bool{
		optimize.Success:             true,
		optimize.GradientThreshold:   true,
		optimize.FunctionConvergence: true,
	}
	if !successStatuses[result.Status] {
		// Try with different method
		result, err = optimize.Minimize(problem, initial, &optimize.Settings{}, &optimize.BFGS{})
		if err != nil {
			return nil, nil, fmt.Errorf("optimization failed: %w", err)
		}
		if !successStatuses[result.Status] {
			return nil, nil, fmt.Errorf("optimization did not converge: status=%v", result.Status)
		}
	}

	// Project final solution to bounds and normalize
	weights := make(map[string]float64)
	xFinal := mvo.projectToBoundsMap(result.X, isins, minWeights, maxWeights) // Use ISIN maps ✅
	sum := 0.0
	for i := range xFinal {
		sum += xFinal[i]
	}
	var portfolioReturn float64
	for i, isin := range isins { // Use ISIN ✅
		w := xFinal[i] / math.Max(sum, 1e-10)
		weights[isin] = math.Max(0.0, w) // ISIN key ✅
		portfolioReturn += mu[i] * weights[isin]
	}

	// Final normalization
	sum = 0.0
	for _, w := range weights {
		sum += w
	}
	if sum > 0 {
		for isin := range weights { // Use ISIN ✅
			weights[isin] /= sum
		}
		portfolioReturn /= sum
	}

	// Validate CVaR constraint
	if err := mvo.validateCVaR(weights, mu, sigma, isins); err != nil { // Use ISINs ✅
		return nil, nil, err
	}

	return weights, &portfolioReturn, nil
}

// optimizeMinVolatility minimizes w'Σw.
func (mvo *MVOptimizer) optimizeMinVolatility(
	mu []float64,
	sigma *mat.Dense,
	isins []string,                // ISIN array ✅
	minWeights map[string]float64, // ISIN-keyed ✅
	maxWeights map[string]float64, // ISIN-keyed ✅
	sectorConstraints []SectorConstraint,
) (map[string]float64, *float64, error) {
	n := len(mu)
	penaltyWeight := 1000.0

	problem := optimize.Problem{
		Func: func(x []float64) float64 {
			xProj := mvo.projectToBoundsMap(x, isins, minWeights, maxWeights) // Use ISIN maps ✅

			var variance float64
			for i := 0; i < n; i++ {
				for j := 0; j < n; j++ {
					variance += xProj[i] * xProj[j] * sigma.At(i, j)
				}
			}

			sum := 0.0
			for i := 0; i < n; i++ {
				sum += xProj[i]
			}

			obj := variance
			obj += penaltyWeight * (sum - 1.0) * (sum - 1.0)
			obj += mvo.sectorConstraintPenalty(xProj, isins, sectorConstraints, penaltyWeight) // Use ISINs ✅

			return obj
		},
		Grad: func(grad, x []float64) {
			xProj := mvo.projectToBoundsMap(x, isins, minWeights, maxWeights) // Use ISIN maps ✅

			for i := 0; i < n; i++ {
				grad[i] = 0
				for j := 0; j < n; j++ {
					grad[i] += 2 * sigma.At(i, j) * xProj[j]
				}
			}

			sum := 0.0
			for i := 0; i < n; i++ {
				sum += xProj[i]
			}
			for i := 0; i < n; i++ {
				grad[i] += 2 * penaltyWeight * (sum - 1.0)
			}

			mvo.addSectorConstraintPenaltyGradient(grad, xProj, isins, sectorConstraints, penaltyWeight) // Use ISINs ✅
		},
	}

	initial := make([]float64, n)
	for i := range initial {
		initial[i] = 1.0 / float64(n)
	}

	result, err := optimize.Minimize(problem, initial, &optimize.Settings{}, &optimize.BFGS{})
	if err != nil {
		result, err = optimize.Minimize(problem, initial, &optimize.Settings{}, &optimize.NelderMead{})
		if err != nil {
			return nil, nil, fmt.Errorf("optimization failed: %w", err)
		}
	}

	if result.Status != optimize.Success && result.Status != optimize.GradientThreshold && result.Status != optimize.FunctionConvergence {
		return nil, nil, fmt.Errorf("optimization did not converge: status=%v", result.Status)
	}

	weights := make(map[string]float64)
	xFinal := mvo.projectToBoundsMap(result.X, isins, minWeights, maxWeights) // Use ISIN maps ✅
	sum := 0.0
	for i := range xFinal {
		sum += xFinal[i]
	}
	var portfolioReturn float64
	for i, isin := range isins { // Use ISIN ✅
		w := xFinal[i] / math.Max(sum, 1e-10)
		weights[isin] = math.Max(0.0, w) // ISIN key ✅
		portfolioReturn += mu[i] * weights[isin]
	}

	sum = 0.0
	for _, w := range weights {
		sum += w
	}
	if sum > 0 {
		for isin := range weights { // Use ISIN ✅
			weights[isin] /= sum
		}
		portfolioReturn /= sum
	}

	// Validate CVaR constraint
	if err := mvo.validateCVaR(weights, mu, sigma, isins); err != nil { // Use ISINs ✅
		return nil, nil, err
	}

	return weights, &portfolioReturn, nil
}

// optimizeMaxSharpe maximizes (μ'w) / sqrt(w'Σw).
func (mvo *MVOptimizer) optimizeMaxSharpe(
	mu []float64,
	sigma *mat.Dense,
	isins []string,                // ISIN array ✅
	minWeights map[string]float64, // ISIN-keyed ✅
	maxWeights map[string]float64, // ISIN-keyed ✅
	sectorConstraints []SectorConstraint,
) (map[string]float64, *float64, error) {
	n := len(mu)
	penaltyWeight := 1000.0

	problem := optimize.Problem{
		Func: func(x []float64) float64 {
			xProj := mvo.projectToBoundsMap(x, isins, minWeights, maxWeights) // Use ISIN maps ✅

			var returnVal, variance float64
			for i := 0; i < n; i++ {
				returnVal += mu[i] * xProj[i]
				for j := 0; j < n; j++ {
					variance += xProj[i] * xProj[j] * sigma.At(i, j)
				}
			}
			stdDev := math.Sqrt(math.Max(variance, 1e-10))

			sum := 0.0
			for i := 0; i < n; i++ {
				sum += xProj[i]
			}

			obj := -returnVal / stdDev
			obj += penaltyWeight * (sum - 1.0) * (sum - 1.0)
			obj += mvo.sectorConstraintPenalty(xProj, isins, sectorConstraints, penaltyWeight) // Use ISINs ✅

			return obj
		},
		Grad: func(grad, x []float64) {
			xProj := mvo.projectToBoundsMap(x, isins, minWeights, maxWeights) // Use ISIN maps ✅

			var returnVal, variance float64
			for i := 0; i < n; i++ {
				returnVal += mu[i] * xProj[i]
				for j := 0; j < n; j++ {
					variance += xProj[i] * xProj[j] * sigma.At(i, j)
				}
			}
			stdDev := math.Sqrt(math.Max(variance, 1e-10))

			for i := 0; i < n; i++ {
				var dVariance float64
				for j := 0; j < n; j++ {
					dVariance += 2 * sigma.At(i, j) * xProj[j]
				}
				grad[i] = -mu[i]/stdDev + returnVal*dVariance/(2*stdDev*stdDev*stdDev)
			}

			sum := 0.0
			for i := 0; i < n; i++ {
				sum += xProj[i]
			}
			for i := 0; i < n; i++ {
				grad[i] += 2 * penaltyWeight * (sum - 1.0)
			}

			mvo.addSectorConstraintPenaltyGradient(grad, xProj, isins, sectorConstraints, penaltyWeight) // Use ISINs ✅
		},
	}

	initial := make([]float64, n)
	for i := range initial {
		initial[i] = 1.0 / float64(n)
	}

	result, err := optimize.Minimize(problem, initial, &optimize.Settings{}, &optimize.BFGS{})
	if err != nil {
		result, err = optimize.Minimize(problem, initial, &optimize.Settings{}, &optimize.NelderMead{})
		if err != nil {
			return nil, nil, fmt.Errorf("optimization failed: %w", err)
		}
	}

	if result.Status != optimize.Success && result.Status != optimize.GradientThreshold && result.Status != optimize.FunctionConvergence {
		return nil, nil, fmt.Errorf("optimization did not converge: status=%v", result.Status)
	}

	weights := make(map[string]float64)
	xFinal := mvo.projectToBoundsMap(result.X, isins, minWeights, maxWeights) // Use ISIN maps ✅
	sum := 0.0
	for i := range xFinal {
		sum += xFinal[i]
	}
	var portfolioReturn float64
	for i, isin := range isins { // Use ISIN ✅
		w := xFinal[i] / math.Max(sum, 1e-10)
		weights[isin] = math.Max(0.0, w) // ISIN key ✅
		portfolioReturn += mu[i] * weights[isin]
	}

	sum = 0.0
	for _, w := range weights {
		sum += w
	}
	if sum > 0 {
		for isin := range weights { // Use ISIN ✅
			weights[isin] /= sum
		}
		portfolioReturn /= sum
	}

	// Validate CVaR constraint
	if err := mvo.validateCVaR(weights, mu, sigma, isins); err != nil { // Use ISINs ✅
		return nil, nil, err
	}

	return weights, &portfolioReturn, nil
}

// optimizeEfficientRisk maximizes μ'w subject to sqrt(w'Σw) = target_volatility.
func (mvo *MVOptimizer) optimizeEfficientRisk(
	mu []float64,
	sigma *mat.Dense,
	isins []string,                // ISIN array ✅
	minWeights map[string]float64, // ISIN-keyed ✅
	maxWeights map[string]float64, // ISIN-keyed ✅
	sectorConstraints []SectorConstraint,
	targetVolatility float64,
) (map[string]float64, *float64, error) {
	n := len(mu)
	penaltyWeight := 1000.0

	problem := optimize.Problem{
		Func: func(x []float64) float64 {
			xProj := mvo.projectToBoundsMap(x, isins, minWeights, maxWeights) // Use ISIN maps ✅

			var returnVal, variance float64
			for i := 0; i < n; i++ {
				returnVal += mu[i] * xProj[i]
				for j := 0; j < n; j++ {
					variance += xProj[i] * xProj[j] * sigma.At(i, j)
				}
			}

			sum := 0.0
			for i := 0; i < n; i++ {
				sum += xProj[i]
			}

			obj := -returnVal
			obj += penaltyWeight * (sum - 1.0) * (sum - 1.0)
			obj += penaltyWeight * (variance - targetVolatility*targetVolatility) * (variance - targetVolatility*targetVolatility)
			obj += mvo.sectorConstraintPenalty(xProj, isins, sectorConstraints, penaltyWeight) // Use ISINs ✅

			return obj
		},
		Grad: func(grad, x []float64) {
			xProj := mvo.projectToBoundsMap(x, isins, minWeights, maxWeights) // Use ISIN maps ✅

			var returnVal, variance float64
			for i := 0; i < n; i++ {
				returnVal += mu[i] * xProj[i]
				for j := 0; j < n; j++ {
					variance += xProj[i] * xProj[j] * sigma.At(i, j)
				}
			}

			for i := 0; i < n; i++ {
				grad[i] = -mu[i]
				for j := 0; j < n; j++ {
					grad[i] += 2 * penaltyWeight * (variance - targetVolatility*targetVolatility) * 2 * sigma.At(i, j) * xProj[j]
				}
			}

			sum := 0.0
			for i := 0; i < n; i++ {
				sum += xProj[i]
			}
			for i := 0; i < n; i++ {
				grad[i] += 2 * penaltyWeight * (sum - 1.0)
			}

			mvo.addSectorConstraintPenaltyGradient(grad, xProj, isins, sectorConstraints, penaltyWeight) // Use ISINs ✅
		},
	}

	initial := make([]float64, n)
	for i := range initial {
		initial[i] = 1.0 / float64(n)
	}

	result, err := optimize.Minimize(problem, initial, &optimize.Settings{}, &optimize.BFGS{})
	if err != nil {
		result, err = optimize.Minimize(problem, initial, &optimize.Settings{}, &optimize.NelderMead{})
		if err != nil {
			return nil, nil, fmt.Errorf("optimization failed: %w", err)
		}
	}

	if result.Status != optimize.Success && result.Status != optimize.GradientThreshold && result.Status != optimize.FunctionConvergence {
		return nil, nil, fmt.Errorf("optimization did not converge: status=%v", result.Status)
	}

	weights := make(map[string]float64)
	xFinal := mvo.projectToBoundsMap(result.X, isins, minWeights, maxWeights) // Use ISIN maps ✅
	sum := 0.0
	for i := range xFinal {
		sum += xFinal[i]
	}
	var portfolioReturn float64
	for i, isin := range isins { // Use ISIN ✅
		w := xFinal[i] / math.Max(sum, 1e-10)
		weights[isin] = math.Max(0.0, w) // ISIN key ✅
		portfolioReturn += mu[i] * weights[isin]
	}

	sum = 0.0
	for _, w := range weights {
		sum += w
	}
	if sum > 0 {
		for isin := range weights { // Use ISIN ✅
			weights[isin] /= sum
		}
		portfolioReturn /= sum
	}

	// Validate CVaR constraint
	if err := mvo.validateCVaR(weights, mu, sigma, isins); err != nil { // Use ISINs ✅
		return nil, nil, err
	}

	return weights, &portfolioReturn, nil
}

// Helper functions

// projectToBounds projects weights to their bounds.
func (mvo *MVOptimizer) projectToBounds(x []float64, bounds [][2]float64) []float64 {
	if len(bounds) == 0 {
		return x
	}
	proj := make([]float64, len(x))
	for i := range x {
		proj[i] = math.Max(bounds[i][0], math.Min(bounds[i][1], x[i]))
	}
	return proj
}

// projectToBoundsMap projects weights to their bounds using ISIN-keyed maps.
func (mvo *MVOptimizer) projectToBoundsMap(
	x []float64,
	isins []string,
	minWeights map[string]float64,
	maxWeights map[string]float64,
) []float64 {
	proj := make([]float64, len(x))
	for i, isin := range isins {
		minW := minWeights[isin]
		maxW := maxWeights[isin]
		proj[i] = math.Max(minW, math.Min(maxW, x[i]))
	}
	return proj
}

// sectorConstraintPenalty calculates penalty for sector constraint violations.
// Uses ISIN-keyed maps.
func (mvo *MVOptimizer) sectorConstraintPenalty(
	x []float64,
	isins []string, // ISIN array ✅ (renamed from symbols)
	constraints []SectorConstraint,
	penaltyWeight float64,
) float64 {
	if len(constraints) == 0 {
		return 0
	}

	var penalty float64
	for _, constraint := range constraints {
		// Group ISINs by sector
		sectorWeights := make(map[string]float64)
		for i, isin := range isins { // Use ISIN ✅
			sector := constraint.SectorMapper[isin] // ISIN lookup ✅
			if sector != "" {
				sectorWeights[sector] += x[i]
			}
		}

		// Check lower bound violations
		for sector, lower := range constraint.SectorLower {
			weight := sectorWeights[sector]
			if weight < lower {
				penalty += penaltyWeight * (lower - weight) * (lower - weight)
			}
		}

		// Check upper bound violations
		for sector, upper := range constraint.SectorUpper {
			weight := sectorWeights[sector]
			if weight > upper {
				penalty += penaltyWeight * (weight - upper) * (weight - upper)
			}
		}
	}

	return penalty
}

// addSectorConstraintPenaltyGradient adds gradient of sector constraint penalty.
// Uses ISIN-keyed maps.
func (mvo *MVOptimizer) addSectorConstraintPenaltyGradient(
	grad []float64,
	x []float64,
	isins []string, // ISIN array ✅ (renamed from symbols)
	constraints []SectorConstraint,
	penaltyWeight float64,
) {
	if len(constraints) == 0 {
		return
	}

	for _, constraint := range constraints {
		// Group ISINs by sector
		sectorWeights := make(map[string]float64)
		for i, isin := range isins { // Use ISIN ✅
			sector := constraint.SectorMapper[isin] // ISIN lookup ✅
			if sector != "" {
				sectorWeights[sector] += x[i]
			}
		}

		// Add gradient for lower bound violations
		for sector, lower := range constraint.SectorLower {
			weight := sectorWeights[sector]
			if weight < lower {
				penalty := 2 * penaltyWeight * (lower - weight)
				for i, isin := range isins { // Use ISIN ✅
					if constraint.SectorMapper[isin] == sector { // ISIN lookup ✅
						grad[i] -= penalty
					}
				}
			}
		}

		// Add gradient for upper bound violations
		for sector, upper := range constraint.SectorUpper {
			weight := sectorWeights[sector]
			if weight > upper {
				penalty := 2 * penaltyWeight * (weight - upper)
				for i, isin := range isins { // Use ISIN ✅
					if constraint.SectorMapper[isin] == sector { // ISIN lookup ✅
						grad[i] += penalty
					}
				}
			}
		}
	}
}

// validateCVaR validates that portfolio CVaR doesn't exceed maximum threshold.
// Returns error if CVaR validation fails or threshold is exceeded.
func (mvo *MVOptimizer) validateCVaR(
	weights map[string]float64,  // ISIN-keyed ✅
	mu []float64,
	sigma *mat.Dense,
	isins []string, // ISIN array ✅ (renamed from symbols)
) error {
	// Skip validation if CVaR calculator or settings service unavailable
	if mvo.cvarCalculator == nil || mvo.settingsService == nil {
		return nil
	}

	// Get max CVaR threshold from settings (default -0.15 = max 15% loss at 95% confidence)
	maxCVaR := -0.15
	if val, err := mvo.settingsService.Get("optimizer_max_cvar_95"); err == nil {
		if cvar, ok := val.(float64); ok {
			maxCVaR = cvar
		}
	}

	// Convert covariance matrix to [][]float64
	n, _ := sigma.Dims()
	covMatrixSlice := make([][]float64, n)
	for i := 0; i < n; i++ {
		covMatrixSlice[i] = make([]float64, n)
		for j := 0; j < n; j++ {
			covMatrixSlice[i][j] = sigma.At(i, j)
		}
	}

	// Convert mu to ISIN-keyed map
	expectedReturnsMap := make(map[string]float64)
	for i, isin := range isins { // Use ISIN ✅
		expectedReturnsMap[isin] = mu[i]
	}

	// Calculate portfolio CVaR using Monte Carlo simulation
	portfolioCVaR := mvo.cvarCalculator.CalculateFromCovariance(
		covMatrixSlice,
		expectedReturnsMap,
		weights,
		isins, // Use ISINs ✅
		10000, // numSimulations
		0.95,  // confidence (95%)
	)

	// Check if CVaR exceeds threshold (CVaR is negative, so check if it's MORE negative than threshold)
	if portfolioCVaR < maxCVaR {
		return fmt.Errorf(
			"portfolio CVaR (%.2f%%) exceeds maximum (%.2f%%) - portfolio rejected due to excessive tail risk",
			portfolioCVaR*100,
			maxCVaR*100,
		)
	}

	return nil
}
