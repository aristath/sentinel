package quantum

import (
	"math"
	"math/cmplx"
)

// QuantumProbabilityCalculator implements quantum-inspired probability calculations
type QuantumProbabilityCalculator struct {
	// Energy scale factor for normalization
	energyScale float64

	// Time parameter (normalized, can be adaptive)
	timeParam float64
}

// NewQuantumProbabilityCalculator creates a new quantum probability calculator
func NewQuantumProbabilityCalculator() *QuantumProbabilityCalculator {
	return &QuantumProbabilityCalculator{
		energyScale: math.Pi / 2.0, // k = π/2 for normalization to [-π, π]
		timeParam:   1.0,           // t = 1.0 (normalized time)
	}
}

// SetTimeParameter sets the time parameter (for adaptive use)
func (q *QuantumProbabilityCalculator) SetTimeParameter(t float64) {
	q.timeParam = t
}

// CalculateEnergyLevel calculates discrete energy level for a state
// Energy levels are quantized to: {-π, -π/2, 0, π/2, π}
func (q *QuantumProbabilityCalculator) CalculateEnergyLevel(
	rawEnergy float64,
) float64 {
	// Normalize to [-π, π] range
	normalized := math.Max(-math.Pi, math.Min(math.Pi, rawEnergy))

	// Quantize to discrete levels: {-π, -π/2, 0, π/2, π}
	levels := []float64{-math.Pi, -math.Pi / 2.0, 0.0, math.Pi / 2.0, math.Pi}

	// Find closest discrete level
	closest := levels[0]
	minDist := math.Abs(normalized - levels[0])
	for _, level := range levels[1:] {
		dist := math.Abs(normalized - level)
		if dist < minDist {
			minDist = dist
			closest = level
		}
	}

	return closest
}

// CalculateInterference calculates quantum interference between two states
// interference = 2√(P₁·P₂)·cos(ΔE·t)
func (q *QuantumProbabilityCalculator) CalculateInterference(
	p1, p2 float64,
	energy1, energy2 float64,
) float64 {
	// Energy difference (phase difference)
	deltaE := energy2 - energy1

	// Interference term: 2√(P₁·P₂)·cos(ΔE·t)
	sqrtProduct := math.Sqrt(p1 * p2)
	interference := 2.0 * sqrtProduct * math.Cos(deltaE*q.timeParam)

	return interference
}

// NormalizeState normalizes quantum state to ensure |α|² + |β|² = 1
func (q *QuantumProbabilityCalculator) NormalizeState(
	pValue, pBubble float64,
) (float64, float64) {
	total := pValue + pBubble
	if total <= 0 {
		// If both are zero or negative, return equal probabilities
		return 0.5, 0.5
	}

	// Normalize so they sum to 1
	normalizedValue := pValue / total
	normalizedBubble := pBubble / total

	return normalizedValue, normalizedBubble
}

// CalculateMultimodalCorrection calculates correction for fat tails
// Uses quantum Student's t-distribution concepts
func (q *QuantumProbabilityCalculator) CalculateMultimodalCorrection(
	volatility float64,
	kurtosis *float64,
) float64 {
	volatilityFactor := volatility

	// Kurtosis factor (if available)
	kurtosisFactor := 1.0
	if kurtosis != nil {
		// Normalize kurtosis (excess kurtosis, typically -2 to +10)
		normalizedKurtosis := math.Max(0, math.Min(10, *kurtosis))
		kurtosisFactor = 1.0 + normalizedKurtosis/3.0
	}

	// Multimodal correction: accounts for fat tails
	correction := 0.1 * volatilityFactor * kurtosisFactor

	return math.Min(0.2, correction) // Cap at 0.2
}

// CalculateAdaptiveInterferenceWeight calculates adaptive interference weight based on regime
func (q *QuantumProbabilityCalculator) CalculateAdaptiveInterferenceWeight(
	regimeScore float64,
) float64 {
	if regimeScore > 0.5 {
		// Bull market: favor quantum (earlier detection)
		return 0.4
	} else if regimeScore < -0.5 {
		// Bear market: favor classical (proven reliability)
		return 0.2
	}
	// Sideways: balanced
	return 0.3
}

// CalculateQuantumAmplitude calculates quantum amplitude from probability and energy
// amplitude = √(P) * exp(i·E·t)
func (q *QuantumProbabilityCalculator) CalculateQuantumAmplitude(
	probability float64,
	energy float64,
) complex128 {
	// Ensure probability is in [0, 1]
	prob := math.Max(0.0, math.Min(1.0, probability))

	// Calculate amplitude: √(P) * exp(i·E·t)
	sqrtProb := math.Sqrt(prob)
	phase := energy * q.timeParam
	amplitude := cmplx.Exp(complex(0, phase)) // exp(i·phase)

	return complex(sqrtProb*real(amplitude), sqrtProb*imag(amplitude))
}

// BornRule calculates probability using Born rule: P = |ψ|²
func (q *QuantumProbabilityCalculator) BornRule(amplitude complex128) float64 {
	return cmplx.Abs(amplitude) * cmplx.Abs(amplitude)
}
