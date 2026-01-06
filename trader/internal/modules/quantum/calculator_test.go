package quantum

import (
	"math"
	"testing"
)

func TestQuantumProbabilityCalculator_CalculateEnergyLevel(t *testing.T) {
	calc := NewQuantumProbabilityCalculator()

	tests := []struct {
		name      string
		rawEnergy float64
		expected  float64
	}{
		{"Negative energy (π)", -3.5, -math.Pi},
		{"Zero energy", 0.0, 0.0},
		{"Positive energy (π)", 3.5, math.Pi},
		{"Small negative (-π/2)", -2.0, -math.Pi / 2.0},
		{"Small positive (π/2)", 2.0, math.Pi / 2.0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := calc.CalculateEnergyLevel(tt.rawEnergy)
			if math.Abs(result-tt.expected) > 0.01 {
				t.Errorf("CalculateEnergyLevel() = %v, want %v", result, tt.expected)
			}
		})
	}
}

func TestQuantumProbabilityCalculator_NormalizeState(t *testing.T) {
	calc := NewQuantumProbabilityCalculator()

	tests := []struct {
		name      string
		pValue    float64
		pBubble   float64
		wantSum   float64
		wantRatio float64
	}{
		{"Equal probabilities", 0.5, 0.5, 1.0, 1.0},
		{"Value dominant", 0.8, 0.2, 1.0, 4.0},
		{"Bubble dominant", 0.2, 0.8, 1.0, 0.25},
		{"Zero values", 0.0, 0.0, 1.0, 1.0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			normValue, normBubble := calc.NormalizeState(tt.pValue, tt.pBubble)
			sum := normValue + normBubble
			if math.Abs(sum-tt.wantSum) > 0.001 {
				t.Errorf("NormalizeState() sum = %v, want %v", sum, tt.wantSum)
			}
			ratio := normValue / normBubble
			if math.Abs(ratio-tt.wantRatio) > 0.01 {
				t.Errorf("NormalizeState() ratio = %v, want %v", ratio, tt.wantRatio)
			}
		})
	}
}

func TestQuantumProbabilityCalculator_CalculateInterference(t *testing.T) {
	calc := NewQuantumProbabilityCalculator()

	tests := []struct {
		name      string
		p1        float64
		p2        float64
		energy1   float64
		energy2   float64
		wantRange [2]float64 // [min, max] expected range
	}{
		{"Same energy (constructive)", 0.5, 0.5, 0.0, 0.0, [2]float64{0.9, 1.1}},
		{"Opposite energy", 0.5, 0.5, -math.Pi, math.Pi, [2]float64{0.9, 1.1}}, // cos(2π) = 1
		{"Different probabilities", 0.8, 0.2, 0.0, math.Pi / 2.0, [2]float64{-0.5, 0.5}},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := calc.CalculateInterference(tt.p1, tt.p2, tt.energy1, tt.energy2)
			if result < tt.wantRange[0] || result > tt.wantRange[1] {
				t.Errorf("CalculateInterference() = %v, want in range %v", result, tt.wantRange)
			}
		})
	}
}

func TestQuantumProbabilityCalculator_CalculateBubbleProbability(t *testing.T) {
	calc := NewQuantumProbabilityCalculator()

	tests := []struct {
		name           string
		cagr           float64
		sharpe         float64
		sortino        float64
		volatility     float64
		fundamentals   float64
		regimeScore    float64
		wantRange      [2]float64
		wantHighBubble bool
	}{
		{
			name:           "High CAGR, poor risk (bubble)",
			cagr:           0.20, // 20%
			sharpe:         0.3,  // Poor
			sortino:        0.3,  // Poor
			volatility:     0.45, // High
			fundamentals:   0.5,  // Low
			regimeScore:    0.0,
			wantRange:      [2]float64{0.6, 1.0},
			wantHighBubble: true,
		},
		{
			name:           "High CAGR, good risk (not bubble)",
			cagr:           0.18, // 18%
			sharpe:         1.5,  // Good
			sortino:        1.5,  // Good
			volatility:     0.25, // Moderate
			fundamentals:   0.8,  // High
			regimeScore:    0.0,
			wantRange:      [2]float64{0.0, 0.5},
			wantHighBubble: false,
		},
		{
			name:           "Low CAGR (not bubble)",
			cagr:           0.10, // 10%
			sharpe:         0.5,
			sortino:        0.5,
			volatility:     0.30,
			fundamentals:   0.7,
			regimeScore:    0.0,
			wantRange:      [2]float64{0.0, 0.4},
			wantHighBubble: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := calc.CalculateBubbleProbability(
				tt.cagr,
				tt.sharpe,
				tt.sortino,
				tt.volatility,
				tt.fundamentals,
				tt.regimeScore,
				nil,
			)

			if result < tt.wantRange[0] || result > tt.wantRange[1] {
				t.Errorf("CalculateBubbleProbability() = %v, want in range %v", result, tt.wantRange)
			}

			isHighBubble := result > 0.7
			if isHighBubble != tt.wantHighBubble {
				t.Errorf("CalculateBubbleProbability() high bubble = %v, want %v", isHighBubble, tt.wantHighBubble)
			}
		})
	}
}

func TestQuantumProbabilityCalculator_CalculateValueTrapProbability(t *testing.T) {
	calc := NewQuantumProbabilityCalculator()

	tests := []struct {
		name         string
		peVsMarket   float64
		fundamentals float64
		longTerm     float64
		momentum     float64
		volatility   float64
		regimeScore  float64
		wantRange    [2]float64
		wantTrap     bool
	}{
		{
			name:         "Cheap with poor fundamentals (trap)",
			peVsMarket:   -0.30, // 30% cheaper
			fundamentals: 0.4,   // Poor
			longTerm:     0.3,   // Poor
			momentum:     -0.1,  // Negative
			volatility:   0.40,  // High
			regimeScore:  0.0,
			wantRange:    [2]float64{0.6, 1.0},
			wantTrap:     true,
		},
		{
			name:         "Cheap with good fundamentals (value)",
			peVsMarket:   -0.25, // 25% cheaper
			fundamentals: 0.8,   // Good
			longTerm:     0.8,   // Good
			momentum:     0.1,   // Positive
			volatility:   0.20,  // Low
			regimeScore:  0.0,
			wantRange:    [2]float64{0.0, 0.4},
			wantTrap:     false,
		},
		{
			name:         "Not cheap (not trap)",
			peVsMarket:   -0.10, // Only 10% cheaper
			fundamentals: 0.5,
			longTerm:     0.5,
			momentum:     0.0,
			volatility:   0.30,
			regimeScore:  0.0,
			wantRange:    [2]float64{0.0, 0.3},
			wantTrap:     false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := calc.CalculateValueTrapProbability(
				tt.peVsMarket,
				tt.fundamentals,
				tt.longTerm,
				tt.momentum,
				tt.volatility,
				tt.regimeScore,
			)

			if result < tt.wantRange[0] || result > tt.wantRange[1] {
				t.Errorf("CalculateValueTrapProbability() = %v, want in range %v", result, tt.wantRange)
			}

			isTrap := result > 0.7
			if isTrap != tt.wantTrap {
				t.Errorf("CalculateValueTrapProbability() trap = %v, want %v", isTrap, tt.wantTrap)
			}
		})
	}
}

func TestQuantumProbabilityCalculator_BornRule(t *testing.T) {
	calc := NewQuantumProbabilityCalculator()

	tests := []struct {
		name      string
		amplitude complex128
		want      float64
	}{
		{"Real amplitude 1", complex(1.0, 0.0), 1.0},
		{"Real amplitude 0.5", complex(0.5, 0.0), 0.25},
		{"Complex amplitude", complex(0.707, 0.707), 1.0}, // |0.707+0.707i|² = 1.0
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := calc.BornRule(tt.amplitude)
			if math.Abs(result-tt.want) > 0.01 {
				t.Errorf("BornRule() = %v, want %v", result, tt.want)
			}
		})
	}
}

func TestQuantumProbabilityCalculator_CalculateAdaptiveInterferenceWeight(t *testing.T) {
	calc := NewQuantumProbabilityCalculator()

	tests := []struct {
		name        string
		regimeScore float64
		want        float64
	}{
		{"Bull market", 0.6, 0.4},
		{"Bear market", -0.6, 0.2},
		{"Sideways", 0.0, 0.3},
		{"Neutral", 0.2, 0.3},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := calc.CalculateAdaptiveInterferenceWeight(tt.regimeScore)
			if math.Abs(result-tt.want) > 0.01 {
				t.Errorf("CalculateAdaptiveInterferenceWeight() = %v, want %v", result, tt.want)
			}
		})
	}
}

func BenchmarkCalculateBubbleProbability(b *testing.B) {
	calc := NewQuantumProbabilityCalculator()
	cagr := 0.18
	sharpe := 0.5
	sortino := 0.5
	volatility := 0.35
	fundamentals := 0.7
	regimeScore := 0.0

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		calc.CalculateBubbleProbability(cagr, sharpe, sortino, volatility, fundamentals, regimeScore, nil)
	}
}

func BenchmarkCalculateValueTrapProbability(b *testing.B) {
	calc := NewQuantumProbabilityCalculator()
	peVsMarket := -0.25
	fundamentals := 0.6
	longTerm := 0.6
	momentum := 0.0
	volatility := 0.30
	regimeScore := 0.0

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		calc.CalculateValueTrapProbability(peVsMarket, fundamentals, longTerm, momentum, volatility, regimeScore)
	}
}
