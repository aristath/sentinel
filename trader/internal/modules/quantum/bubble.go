package quantum

import (
	"math"
)

// CalculateBubbleProbability calculates quantum probability of bubble state
// Uses quantum superposition: |security⟩ = α|value⟩ + β|bubble⟩
// Based on improved formulas with discrete energy levels
func (q *QuantumProbabilityCalculator) CalculateBubbleProbability(
	cagr float64,
	sharpe float64,
	sortino float64,
	volatility float64,
	fundamentalsScore float64,
	regimeScore float64,
	kurtosis *float64,
) float64 {
	// Normalize inputs to [0, 1] range
	normCAGR := math.Min(1.0, cagr/0.20)                           // Cap at 20% CAGR
	normSharpe := math.Min(1.0, math.Max(0.0, (sharpe+2.0)/4.0))   // Map [-2, 2] to [0, 1]
	normSortino := math.Min(1.0, math.Max(0.0, (sortino+2.0)/4.0)) // Map [-2, 2] to [0, 1]
	normVol := math.Min(1.0, volatility/0.50)                      // Cap at 50% volatility

	// Step 1: Calculate Energy Levels (discrete, quantized)
	// Value energy: negative = stable state
	valueEnergyRaw := -q.energyScale * (fundamentalsScore + (1.0 - normVol) + normSortino*0.5)
	valueEnergy := q.CalculateEnergyLevel(valueEnergyRaw)

	// Bubble energy: positive = unstable state
	bubbleEnergyRaw := q.energyScale * (normCAGR - (1.0 - normSharpe) - normVol)
	bubbleEnergy := q.CalculateEnergyLevel(bubbleEnergyRaw)

	// Step 2: Calculate Probability Amplitudes (normalized)
	// Value state: strong fundamentals, reasonable returns
	pValue := fundamentalsScore * (1.0 - normVol) * (1.0 + normSortino*0.5)
	// Bubble state: high returns with poor risk metrics
	pBubble := normCAGR * (1.0 - normSharpe) * normVol

	// Normalize probabilities so they sum to 1
	pValue, pBubble = q.NormalizeState(pValue, pBubble)

	// Step 3: Calculate Quantum Amplitudes (with energy-based phases)
	bubbleAmplitude := q.CalculateQuantumAmplitude(pBubble, bubbleEnergy)

	// Step 4: Calculate Interference (improved with energy difference)
	interference := q.CalculateInterference(pValue, pBubble, valueEnergy, bubbleEnergy)

	// Step 5: Calculate Multimodal Correction (for fat tails)
	multimodalCorrection := q.CalculateMultimodalCorrection(volatility, kurtosis)

	// Step 6: Calculate Adaptive Interference Weight
	lambda := q.CalculateAdaptiveInterferenceWeight(regimeScore)

	// Step 7: Final Probability (with all corrections)
	// P(bubble) = |β|² + λ·interference + μ·multimodal_correction
	bubbleProb := q.BornRule(bubbleAmplitude)
	bubbleProb += lambda * interference
	bubbleProb += 0.15 * multimodalCorrection // μ = 0.15

	// Clamp to [0, 1]
	return math.Min(1.0, math.Max(0.0, bubbleProb))
}

// CalculateBubbleState calculates complete quantum bubble state
func (q *QuantumProbabilityCalculator) CalculateBubbleState(
	cagr float64,
	sharpe float64,
	sortino float64,
	volatility float64,
	fundamentalsScore float64,
	regimeScore float64,
	kurtosis *float64,
) QuantumBubbleState {
	// Normalize inputs
	normCAGR := math.Min(1.0, cagr/0.20)
	normSharpe := math.Min(1.0, math.Max(0.0, (sharpe+2.0)/4.0))
	normSortino := math.Min(1.0, math.Max(0.0, (sortino+2.0)/4.0))
	normVol := math.Min(1.0, volatility/0.50)

	// Calculate energy levels
	valueEnergyRaw := -q.energyScale * (fundamentalsScore + (1.0 - normVol) + normSortino*0.5)
	valueEnergy := q.CalculateEnergyLevel(valueEnergyRaw)
	bubbleEnergyRaw := q.energyScale * (normCAGR - (1.0 - normSharpe) - normVol)
	bubbleEnergy := q.CalculateEnergyLevel(bubbleEnergyRaw)

	// Calculate probabilities
	pValue := fundamentalsScore * (1.0 - normVol) * (1.0 + normSortino*0.5)
	pBubble := normCAGR * (1.0 - normSharpe) * normVol
	pValue, pBubble = q.NormalizeState(pValue, pBubble)

	// Calculate amplitudes
	valueAmplitude := q.CalculateQuantumAmplitude(pValue, valueEnergy)
	bubbleAmplitude := q.CalculateQuantumAmplitude(pBubble, bubbleEnergy)

	// Calculate interference
	interference := q.CalculateInterference(pValue, pBubble, valueEnergy, bubbleEnergy)

	// Calculate probability
	lambda := q.CalculateAdaptiveInterferenceWeight(regimeScore)
	multimodalCorrection := q.CalculateMultimodalCorrection(volatility, kurtosis)
	bubbleProb := q.BornRule(bubbleAmplitude)
	bubbleProb += lambda * interference
	bubbleProb += 0.15 * multimodalCorrection
	bubbleProb = math.Min(1.0, math.Max(0.0, bubbleProb))

	return QuantumBubbleState{
		State: QuantumState{
			ValueAmplitude:  valueAmplitude,
			BubbleAmplitude: bubbleAmplitude,
			ValueEnergy:     valueEnergy,
			BubbleEnergy:    bubbleEnergy,
			Interference:    interference,
		},
		Probability: bubbleProb,
	}
}
