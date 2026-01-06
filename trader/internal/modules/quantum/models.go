package quantum

// QuantumState represents a security's quantum state
type QuantumState struct {
	// Probability amplitude for "value" state
	ValueAmplitude complex128

	// Probability amplitude for "bubble" state
	BubbleAmplitude complex128

	// Energy level for value state (discrete, quantized)
	ValueEnergy float64

	// Energy level for bubble state (discrete, quantized)
	BubbleEnergy float64

	// Interference term (captures quantum effects)
	Interference float64
}

// QuantumBubbleState represents bubble-specific quantum state
type QuantumBubbleState struct {
	State       QuantumState
	Probability float64
}

// QuantumValueState represents value trap quantum state
type QuantumValueState struct {
	State       QuantumState
	Probability float64
}

// QuantumMetrics represents quantum-enhanced scoring metrics
type QuantumMetrics struct {
	RiskAdjusted float64 // Quantum-inspired risk metric
	Interference float64 // Interference effect score
	Multimodal   float64 // Multimodal distribution indicator
}
