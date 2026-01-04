package formulas

import (
	"math"
	"testing"
)

func TestCalculateAnnualReturn(t *testing.T) {
	tests := []struct {
		name      string
		returns   []float64
		expected  float64
		tolerance float64
	}{
		{
			name:      "empty returns",
			returns:   []float64{},
			expected:  0.0,
			tolerance: 0.0,
		},
		{
			name:      "one year of small positive returns",
			returns:   makeReturns(0.001, 252), // 252 daily returns of 0.1%
			expected:  0.286,                   // Approximately 28.6% annualized
			tolerance: 0.01,
		},
		{
			name:      "half year of returns",
			returns:   makeReturns(0.002, 126), // 126 days (half year) of 0.2% returns
			expected:  0.654,                   // CAGR: (1.002^126)^(252/126) - 1 ≈ 65.4%
			tolerance: 0.01,
		},
		{
			name:      "one year of negative returns",
			returns:   makeReturns(-0.001, 252),
			expected:  -0.221, // Negative annualized return
			tolerance: 0.01,
		},
		{
			name:      "very short period",
			returns:   []float64{0.01, 0.02},
			expected:  0.0302, // Simple cumulative for very short periods
			tolerance: 0.001,
		},
		{
			name:      "mixed returns",
			returns:   []float64{0.01, -0.005, 0.02, -0.01, 0.015},
			expected:  3.44, // CAGR over 5 days: (1.0303)^(252/5) - 1 ≈ 3.44
			tolerance: 0.1,
		},
		{
			name:      "zero returns",
			returns:   makeReturns(0.0, 252),
			expected:  0.0,
			tolerance: 0.001,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := CalculateAnnualReturn(tt.returns)
			if math.Abs(result-tt.expected) > tt.tolerance {
				t.Errorf("CalculateAnnualReturn() = %v, want %v (±%v)", result, tt.expected, tt.tolerance)
			}
		})
	}
}

func TestAnnualizedVolatility(t *testing.T) {
	tests := []struct {
		name      string
		returns   []float64
		expected  float64
		tolerance float64
	}{
		{
			name:      "empty returns",
			returns:   []float64{},
			expected:  0.0,
			tolerance: 0.0,
		},
		{
			name:      "constant returns",
			returns:   makeReturns(0.001, 252),
			expected:  0.0, // No volatility when all returns are same
			tolerance: 0.001,
		},
		{
			name:      "mixed returns",
			returns:   []float64{0.01, -0.01, 0.02, -0.02, 0.015, -0.015},
			expected:  0.244, // Some volatility
			tolerance: 0.05,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := AnnualizedVolatility(tt.returns)
			if math.Abs(result-tt.expected) > tt.tolerance {
				t.Errorf("AnnualizedVolatility() = %v, want %v (±%v)", result, tt.expected, tt.tolerance)
			}
		})
	}
}

func TestCalculateReturns(t *testing.T) {
	tests := []struct {
		name        string
		prices      []float64
		want        []float64
		tolerance   float64
		description string
	}{
		{
			name:        "empty prices",
			prices:      []float64{},
			want:        []float64{},
			tolerance:   0.0,
			description: "Empty prices should return empty returns",
		},
		{
			name:        "single price",
			prices:      []float64{100.0},
			want:        []float64{},
			tolerance:   0.0,
			description: "Single price cannot calculate return",
		},
		{
			name:        "two prices positive return",
			prices:      []float64{100.0, 110.0},
			want:        []float64{0.10},
			tolerance:   0.0001,
			description: "10% return from 100 to 110",
		},
		{
			name:        "two prices negative return",
			prices:      []float64{100.0, 90.0},
			want:        []float64{-0.10},
			tolerance:   0.0001,
			description: "-10% return from 100 to 90",
		},
		{
			name:        "three prices sequence",
			prices:      []float64{100.0, 110.0, 105.0},
			want:        []float64{0.10, -0.04545},
			tolerance:   0.0001,
			description: "10% up then ~4.5% down",
		},
		{
			name:        "price sequence with zero",
			prices:      []float64{100.0, 0.0, 110.0},
			want:        []float64{-1.0, 0.0}, // Second return is 0 because division by zero
			tolerance:   0.0001,
			description: "Handles zero price (division by zero results in 0)",
		},
		{
			name:        "steady prices",
			prices:      []float64{100.0, 100.0, 100.0},
			want:        []float64{0.0, 0.0},
			tolerance:   0.0,
			description: "No change means zero returns",
		},
		{
			name:        "increasing sequence",
			prices:      []float64{100.0, 105.0, 110.25, 115.76},
			want:        []float64{0.05, 0.05, 0.05}, // 5% each period
			tolerance:   0.0001,
			description: "Compound 5% returns",
		},
		{
			name:        "volatile sequence",
			prices:      []float64{100.0, 120.0, 90.0, 108.0},
			want:        []float64{0.20, -0.25, 0.20},
			tolerance:   0.0001,
			description: "Volatile price movements",
		},
		{
			name:        "very small price changes",
			prices:      []float64{100.0, 100.01, 100.02},
			want:        []float64{0.0001, 0.00009999},
			tolerance:   0.00001,
			description: "Very small price changes",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := CalculateReturns(tt.prices)

			if len(tt.want) == 0 {
				if len(result) != 0 {
					t.Errorf("CalculateReturns() = %v, want empty slice", result)
				}
				return
			}

			if len(result) != len(tt.want) {
				t.Errorf("CalculateReturns() length = %v, want %v", len(result), len(tt.want))
				return
			}

			for i := range result {
				if math.Abs(result[i]-tt.want[i]) > tt.tolerance {
					t.Errorf("CalculateReturns()[%d] = %v, want %v (±%v) - %s",
						i, result[i], tt.want[i], tt.tolerance, tt.description)
				}
			}
		})
	}
}

// Helper function to create a slice of identical returns
func makeReturns(value float64, count int) []float64 {
	returns := make([]float64, count)
	for i := range returns {
		returns[i] = value
	}
	return returns
}
