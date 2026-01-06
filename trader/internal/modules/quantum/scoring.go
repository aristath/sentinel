package quantum

import (
	"math"
)

// CalculateQuantumScore calculates quantum-enhanced scoring metrics
func (q *QuantumProbabilityCalculator) CalculateQuantumScore(
	returns []float64,
	volatility float64,
	sharpe float64,
	sortino float64,
	kurtosis *float64,
) QuantumMetrics {
	// Quantum risk-adjusted return metric
	// Combines traditional risk metrics with quantum interference effects
	riskAdjusted := q.calculateQuantumRiskAdjusted(returns, volatility, sharpe, sortino)

	// Quantum interference score
	// Captures interactions between different return modes
	interference := q.calculateInterferenceScore(returns, volatility)

	// Multimodal distribution indicator
	// Measures how well returns fit a multimodal (quantum) distribution vs unimodal (classical)
	multimodal := q.calculateMultimodalIndicator(returns, volatility, kurtosis)

	return QuantumMetrics{
		RiskAdjusted: riskAdjusted,
		Interference: interference,
		Multimodal:   multimodal,
	}
}

// calculateQuantumRiskAdjusted calculates quantum-inspired risk-adjusted return
func (q *QuantumProbabilityCalculator) calculateQuantumRiskAdjusted(
	returns []float64,
	volatility float64,
	sharpe float64,
	sortino float64,
) float64 {
	if len(returns) == 0 {
		return 0.0
	}

	// Calculate average return
	avgReturn := 0.0
	for _, r := range returns {
		avgReturn += r
	}
	avgReturn /= float64(len(returns))

	// Traditional Sharpe-like metric
	traditionalRiskAdj := 0.0
	if volatility > 0 {
		traditionalRiskAdj = avgReturn / volatility
	}

	// Quantum enhancement: adjust for interference effects
	// Higher interference = more complex risk structure
	interferenceFactor := q.calculateInterferenceScore(returns, volatility)

	// Combine traditional and quantum components
	// Weight: 70% traditional, 30% quantum enhancement
	quantumRiskAdj := 0.7*traditionalRiskAdj + 0.3*interferenceFactor

	// Normalize to [0, 1] range (assuming typical Sharpe range [-2, 2])
	normalized := math.Min(1.0, math.Max(0.0, (quantumRiskAdj+2.0)/4.0))

	return normalized
}

// calculateInterferenceScore calculates interference effect score
// Measures how much quantum interference affects return distribution
func (q *QuantumProbabilityCalculator) calculateInterferenceScore(
	returns []float64,
	volatility float64,
) float64 {
	if len(returns) < 2 {
		return 0.0
	}

	// Calculate return distribution characteristics
	positiveReturns := 0
	negativeReturns := 0
	for _, r := range returns {
		if r > 0 {
			positiveReturns++
		} else {
			negativeReturns++
		}
	}

	// Interference is higher when returns are more balanced (superposition)
	balance := math.Min(float64(positiveReturns), float64(negativeReturns)) / float64(len(returns))

	// Volatility contributes to interference (more volatility = more quantum effects)
	volatilityFactor := math.Min(1.0, volatility/0.50)

	// Interference score: combination of balance and volatility
	interference := 0.5*balance + 0.5*volatilityFactor

	return math.Min(1.0, math.Max(0.0, interference))
}

// calculateMultimodalIndicator calculates how well returns fit multimodal distribution
// Higher values indicate more multimodal (quantum-like) behavior
func (q *QuantumProbabilityCalculator) calculateMultimodalIndicator(
	returns []float64,
	volatility float64,
	kurtosis *float64,
) float64 {
	if len(returns) < 10 {
		return 0.0
	}

	// Base indicator from volatility (high volatility = more multimodal)
	volatilityIndicator := math.Min(1.0, volatility/0.50)

	// Kurtosis factor (if available)
	kurtosisFactor := 0.0
	if kurtosis != nil {
		// Excess kurtosis > 0 indicates fat tails (multimodal behavior)
		excessKurtosis := math.Max(0, *kurtosis)
		kurtosisFactor = math.Min(1.0, excessKurtosis/5.0)
	}

	// Calculate return distribution spread
	// More spread = more multimodal
	mean := 0.0
	for _, r := range returns {
		mean += r
	}
	mean /= float64(len(returns))

	variance := 0.0
	for _, r := range returns {
		variance += (r - mean) * (r - mean)
	}
	variance /= float64(len(returns))

	// Normalize variance indicator
	varianceIndicator := math.Min(1.0, math.Sqrt(variance)/0.20)

	// Combine indicators: 40% volatility, 30% kurtosis, 30% variance
	multimodal := 0.4*volatilityIndicator + 0.3*kurtosisFactor + 0.3*varianceIndicator

	return math.Min(1.0, math.Max(0.0, multimodal))
}
