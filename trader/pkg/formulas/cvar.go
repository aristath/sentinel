package formulas

import (
	"math"
	"sort"

	"gonum.org/v1/gonum/stat/distuv"
)

// CalculateCVaR calculates Conditional Value at Risk (CVaR) at the specified confidence level.
// CVaR is the expected loss given that the loss exceeds the VaR threshold.
//
// Args:
//   - returns: Historical returns (can be negative for losses)
//   - confidence: Confidence level (e.g., 0.95 for 95%)
//
// Returns:
//   - CVaR value (negative for losses, positive for gains in tail)
func CalculateCVaR(returns []float64, confidence float64) float64 {
	if len(returns) == 0 {
		return 0.0
	}

	if len(returns) == 1 {
		return returns[0]
	}

	// Sort returns in ascending order (worst first)
	sorted := make([]float64, len(returns))
	copy(sorted, returns)
	sort.Float64s(sorted)

	// Calculate VaR threshold (percentile)
	// For 95% confidence, we want the worst 5% of returns
	tailProbability := 1.0 - confidence
	tailCount := int(math.Ceil(float64(len(sorted)) * tailProbability))

	if tailCount == 0 {
		tailCount = 1
	}
	if tailCount > len(sorted) {
		tailCount = len(sorted)
	}

	// CVaR is the average of returns in the tail
	tailReturns := sorted[:tailCount]
	sum := 0.0
	for _, r := range tailReturns {
		sum += r
	}

	return sum / float64(len(tailReturns))
}

// CalculatePortfolioCVaR calculates portfolio-level CVaR by aggregating individual security CVaRs.
// This is a simplified approach; for more accuracy, use Monte Carlo simulation.
//
// Args:
//   - weights: Portfolio weights by symbol
//   - returns: Historical returns by symbol
//   - confidence: Confidence level (e.g., 0.95)
//
// Returns:
//   - Portfolio CVaR
func CalculatePortfolioCVaR(weights map[string]float64, returns map[string][]float64, confidence float64) float64 {
	if len(weights) == 0 {
		return 0.0
	}

	// Calculate CVaR for each security
	cvarBySymbol := make(map[string]float64)
	for symbol, rets := range returns {
		cvarBySymbol[symbol] = CalculateCVaR(rets, confidence)
	}

	// Weighted average of CVaRs
	portfolioCVaR := 0.0
	for symbol, weight := range weights {
		if cvar, hasCVaR := cvarBySymbol[symbol]; hasCVaR {
			portfolioCVaR += weight * cvar
		}
	}

	return portfolioCVaR
}

// MonteCarloCVaR calculates CVaR using Monte Carlo simulation from covariance matrix.
// This is more accurate than historical CVaR when historical data is limited.
//
// Args:
//   - covMatrix: Covariance matrix (must be square, same size as symbols)
//   - expectedReturns: Expected returns by symbol
//   - symbols: Ordered list of symbols (must match covariance matrix)
//   - numSimulations: Number of Monte Carlo simulations (e.g., 10000)
//   - confidence: Confidence level (e.g., 0.95)
//
// Returns:
//   - CVaR value (negative for tail risk)
func MonteCarloCVaR(covMatrix [][]float64, expectedReturns map[string]float64, symbols []string, numSimulations int, confidence float64) float64 {
	if len(covMatrix) == 0 || len(symbols) == 0 {
		return 0.0
	}

	n := len(symbols)
	if len(covMatrix) != n {
		return 0.0
	}

	// Build expected returns vector
	mu := make([]float64, n)
	for i, symbol := range symbols {
		if ret, hasRet := expectedReturns[symbol]; hasRet {
			mu[i] = ret
		}
	}

	// Convert covariance matrix to gonum matrix format
	// For simplicity, we'll use a multivariate normal approximation
	// In practice, you'd use gonum's distmv package for proper multivariate normal

	// Generate random returns using Cholesky decomposition approach
	// For now, use a simplified approach: sample from univariate normals with correlation
	simulatedReturns := make([]float64, numSimulations)

	for i := 0; i < numSimulations; i++ {
		// Simplified: sample portfolio return directly
		// In practice, would use proper multivariate normal
		portfolioReturn := 0.0
		for j := range symbols {
			weight := 1.0 / float64(n) // Equal weights for simulation
			// Sample from normal distribution: N(mu[j], sqrt(covMatrix[j][j]))
			stdDev := math.Sqrt(math.Max(covMatrix[j][j], 1e-10))
			sample := distuv.Normal{
				Mu:    mu[j],
				Sigma: stdDev,
			}.Rand()
			portfolioReturn += weight * sample
		}
		simulatedReturns[i] = portfolioReturn
	}

	// Calculate CVaR from simulated returns
	return CalculateCVaR(simulatedReturns, confidence)
}

// MonteCarloCVaRWithWeights calculates CVaR using Monte Carlo simulation with specific portfolio weights.
// This is more accurate than the equal-weight version.
func MonteCarloCVaRWithWeights(
	covMatrix [][]float64,
	expectedReturns map[string]float64,
	weights map[string]float64,
	symbols []string,
	numSimulations int,
	confidence float64,
) float64 {
	if len(covMatrix) == 0 || len(symbols) == 0 {
		return 0.0
	}

	n := len(symbols)
	if len(covMatrix) != n {
		return 0.0
	}

	// Build expected returns vector and weights vector
	mu := make([]float64, n)
	w := make([]float64, n)
	for i, symbol := range symbols {
		if ret, hasRet := expectedReturns[symbol]; hasRet {
			mu[i] = ret
		}
		if weight, hasWeight := weights[symbol]; hasWeight {
			w[i] = weight
		}
	}

	// Calculate portfolio expected return: w' * mu
	portfolioMu := 0.0
	for i := 0; i < n; i++ {
		portfolioMu += w[i] * mu[i]
	}

	// Calculate portfolio variance: w' * Σ * w
	portfolioVariance := 0.0
	for i := 0; i < n; i++ {
		for j := 0; j < n; j++ {
			portfolioVariance += w[i] * w[j] * covMatrix[i][j]
		}
	}
	portfolioStdDev := math.Sqrt(math.Max(portfolioVariance, 1e-10))

	// Generate portfolio returns using normal distribution
	simulatedReturns := make([]float64, numSimulations)

	// Use multivariate normal if available, otherwise approximate with univariate
	// For simplicity, use portfolio-level normal distribution
	normal := distuv.Normal{
		Mu:    portfolioMu,
		Sigma: portfolioStdDev,
	}

	for i := 0; i < numSimulations; i++ {
		simulatedReturns[i] = normal.Rand()
	}

	// Calculate CVaR from simulated returns
	return CalculateCVaR(simulatedReturns, confidence)
}
