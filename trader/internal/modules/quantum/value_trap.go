package quantum

import (
	"math"
)

// CalculateValueTrapProbability calculates quantum probability of value trap state
// Models cheap securities in superposition between "value" and "trap" states
func (q *QuantumProbabilityCalculator) CalculateValueTrapProbability(
	peVsMarket float64,
	fundamentalsScore float64,
	longTermScore float64,
	momentumScore float64,
	volatility float64,
	regimeScore float64,
) float64 {
	// Only consider if security is cheap (P/E < market - 20%)
	if peVsMarket >= -0.20 {
		return 0.0 // Not cheap enough to be a value trap
	}

	// Normalize inputs
	normVol := math.Min(1.0, volatility/0.50)
	normMomentum := math.Min(1.0, math.Max(0.0, (momentumScore+1.0)/2.0)) // Map [-1, 1] to [0, 1]
	cheapness := math.Min(1.0, math.Abs(peVsMarket)/0.50)                 // How cheap (0 to 1)

	// Step 1: Calculate Energy Levels
	// Value energy: negative = stable value opportunity
	valueEnergyRaw := -q.energyScale * (fundamentalsScore + longTermScore + (1.0 - normVol))
	valueEnergy := q.CalculateEnergyLevel(valueEnergyRaw)

	// Trap energy: positive = declining value trap
	trapEnergyRaw := q.energyScale * (cheapness - fundamentalsScore - longTermScore - normMomentum - normVol)
	trapEnergy := q.CalculateEnergyLevel(trapEnergyRaw)

	// Step 2: Calculate Probability Amplitudes
	// Value state: cheap with good fundamentals and momentum
	pValue := cheapness * fundamentalsScore * longTermScore * (1.0 + normMomentum) * (1.0 - normVol)

	// Trap state: cheap but declining (poor fundamentals, negative momentum, high volatility)
	pTrap := cheapness * (1.0 - fundamentalsScore) * (1.0 - longTermScore) * (1.0 - normMomentum) * normVol

	// Normalize probabilities
	pValue, pTrap = q.NormalizeState(pValue, pTrap)

	// Step 3: Calculate Quantum Amplitudes (only need trap amplitude for probability)
	trapAmplitude := q.CalculateQuantumAmplitude(pTrap, trapEnergy)

	// Step 4: Calculate Interference
	interference := q.CalculateInterference(pValue, pTrap, valueEnergy, trapEnergy)

	// Step 5: Calculate Adaptive Interference Weight
	lambda := q.CalculateAdaptiveInterferenceWeight(regimeScore)

	// Step 6: Final Probability
	// P(trap) = |trap_amplitude|² + λ·interference
	trapProb := q.BornRule(trapAmplitude)
	trapProb += lambda * interference

	// Clamp to [0, 1]
	return math.Min(1.0, math.Max(0.0, trapProb))
}

// CalculateValueTrapState calculates complete quantum value trap state
func (q *QuantumProbabilityCalculator) CalculateValueTrapState(
	peVsMarket float64,
	fundamentalsScore float64,
	longTermScore float64,
	momentumScore float64,
	volatility float64,
	regimeScore float64,
) QuantumValueState {
	// Only consider if cheap
	if peVsMarket >= -0.20 {
		return QuantumValueState{
			State: QuantumState{
				ValueAmplitude:  0,
				BubbleAmplitude: 0,
				ValueEnergy:     0,
				BubbleEnergy:    0,
				Interference:    0,
			},
			Probability: 0.0,
		}
	}

	// Normalize inputs
	normVol := math.Min(1.0, volatility/0.50)
	normMomentum := math.Min(1.0, math.Max(0.0, (momentumScore+1.0)/2.0))
	cheapness := math.Min(1.0, math.Abs(peVsMarket)/0.50)

	// Calculate energy levels
	valueEnergyRaw := -q.energyScale * (fundamentalsScore + longTermScore + (1.0 - normVol))
	valueEnergy := q.CalculateEnergyLevel(valueEnergyRaw)
	trapEnergyRaw := q.energyScale * (cheapness - fundamentalsScore - longTermScore - normMomentum - normVol)
	trapEnergy := q.CalculateEnergyLevel(trapEnergyRaw)

	// Calculate probabilities
	pValue := cheapness * fundamentalsScore * longTermScore * (1.0 + normMomentum) * (1.0 - normVol)
	pTrap := cheapness * (1.0 - fundamentalsScore) * (1.0 - longTermScore) * (1.0 - normMomentum) * normVol
	pValue, pTrap = q.NormalizeState(pValue, pTrap)

	// Calculate amplitudes
	valueAmplitude := q.CalculateQuantumAmplitude(pValue, valueEnergy)
	trapAmplitude := q.CalculateQuantumAmplitude(pTrap, trapEnergy)

	// Calculate interference
	interference := q.CalculateInterference(pValue, pTrap, valueEnergy, trapEnergy)

	// Calculate probability
	lambda := q.CalculateAdaptiveInterferenceWeight(regimeScore)
	trapProb := q.BornRule(trapAmplitude)
	trapProb += lambda * interference
	trapProb = math.Min(1.0, math.Max(0.0, trapProb))

	return QuantumValueState{
		State: QuantumState{
			ValueAmplitude:  valueAmplitude,
			BubbleAmplitude: trapAmplitude, // Reusing BubbleAmplitude field for trap
			ValueEnergy:     valueEnergy,
			BubbleEnergy:    trapEnergy,
			Interference:    interference,
		},
		Probability: trapProb,
	}
}
