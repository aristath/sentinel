package portfolio

import (
	"testing"
	"time"

	"github.com/rs/zerolog"
)

func TestDetectRegime(t *testing.T) {
	detector := NewMarketRegimeDetector(zerolog.Nop())

	tests := []struct {
		name            string
		portfolioReturn float64 // Average DAILY return
		volatility      float64 // Daily volatility (std dev)
		maxDrawdown     float64
		expectedRegime  MarketRegime
	}{
		{
			name:            "Bull market - strong uptrend",
			portfolioReturn: 0.001, // 0.1% daily = ~36% annualized
			volatility:      0.015, // 1.5% daily volatility
			maxDrawdown:     -0.05, // 5% max drawdown
			expectedRegime:  MarketRegimeBull,
		},
		{
			name:            "Bull market - moderate uptrend",
			portfolioReturn: 0.0006, // 0.06% daily = ~22% annualized
			volatility:      0.02,   // 2% daily volatility
			maxDrawdown:     -0.08,  // 8% max drawdown
			expectedRegime:  MarketRegimeBull,
		},
		{
			name:            "Bear market - declining",
			portfolioReturn: -0.001, // -0.1% daily = ~-36% annualized
			volatility:      0.025,  // 2.5% daily volatility
			maxDrawdown:     -0.15,  // 15% max drawdown
			expectedRegime:  MarketRegimeBear,
		},
		{
			name:            "Bear market - high volatility crash",
			portfolioReturn: -0.0003, // Slightly negative
			volatility:      0.04,    // 4% daily volatility (extreme stress)
			maxDrawdown:     -0.20,   // 20% max drawdown
			expectedRegime:  MarketRegimeBear,
		},
		{
			name:            "Sideways market - choppy neutral",
			portfolioReturn: 0.0002, // 0.02% daily = ~7% annualized (barely positive)
			volatility:      0.015,  // 1.5% daily volatility
			maxDrawdown:     -0.08,  // 8% drawdown
			expectedRegime:  MarketRegimeSideways,
		},
		{
			name:            "Sideways market - range-bound",
			portfolioReturn: -0.0001, // Slightly negative but not bear
			volatility:      0.012,   // Low volatility
			maxDrawdown:     -0.06,   // Small drawdown
			expectedRegime:  MarketRegimeSideways,
		},
		{
			name:            "Bear market - large drawdown only",
			portfolioReturn: 0.0001, // Slightly positive return
			volatility:      0.02,   // Normal volatility
			maxDrawdown:     -0.15,  // But experiencing 15% drawdown
			expectedRegime:  MarketRegimeBear,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			regime := detector.DetectRegime(tt.portfolioReturn, tt.volatility, tt.maxDrawdown)
			if regime != tt.expectedRegime {
				t.Errorf("DetectRegime() = %v, want %v (return=%.4f%%, vol=%.2f%%, dd=%.1f%%)",
					regime, tt.expectedRegime,
					tt.portfolioReturn*100, tt.volatility*100, tt.maxDrawdown*100)
			}
		})
	}
}

func TestDetectRegimeFromHistory(t *testing.T) {
	detector := NewMarketRegimeDetector(zerolog.Nop())

	tests := []struct {
		name           string
		returns        []float64 // DAILY returns
		window         int
		expectedRegime MarketRegime
		description    string
	}{
		{
			name: "Bull market - consistent daily gains",
			returns: []float64{
				0.008, 0.012, 0.005, 0.015, 0.007, // Week 1: strong gains
				0.010, 0.006, 0.009, 0.011, 0.004, // Week 2: continued gains
				0.007, 0.013, 0.006, 0.008, 0.010, // Week 3: steady
				0.009, 0.005, 0.012, 0.007, 0.011, // Week 4: strong
			},
			window:         20,
			expectedRegime: MarketRegimeBull,
			description:    "Average ~0.85% daily = ~300% annualized",
		},
		{
			name: "Bear market - consistent decline",
			returns: []float64{
				-0.008, -0.012, -0.005, -0.015, -0.007, // Week 1: losses
				-0.010, -0.006, -0.009, -0.011, -0.004, // Week 2: continued losses
				-0.007, -0.013, -0.006, -0.008, -0.010, // Week 3: steady decline
				-0.009, -0.005, -0.012, -0.007, -0.011, // Week 4: more losses
			},
			window:         20,
			expectedRegime: MarketRegimeBear,
			description:    "Average ~-0.85% daily = ~-95% annualized",
		},
		{
			name: "Sideways market - oscillating",
			returns: []float64{
				0.003, -0.002, 0.004, -0.003, 0.002, // Week 1: up/down
				-0.001, 0.003, -0.002, 0.001, -0.003, // Week 2: choppy
				0.002, -0.001, 0.003, -0.002, 0.001, // Week 3: mixed
				-0.002, 0.003, -0.001, 0.002, -0.003, // Week 4: range-bound
			},
			window:         20,
			expectedRegime: MarketRegimeSideways,
			description:    "Average ~0% daily, choppy",
		},
		{
			name: "Bear market - high volatility",
			returns: []float64{
				-0.025, 0.015, -0.030, 0.020, -0.018, // Week 1: wild swings
				-0.022, 0.012, -0.028, 0.018, -0.020, // Week 2: continued volatility
				-0.015, 0.010, -0.025, 0.015, -0.012, // Week 3: still volatile
				-0.020, 0.008, -0.015, 0.012, -0.018, // Week 4: stressed
			},
			window:         20,
			expectedRegime: MarketRegimeBear,
			description:    "High volatility triggers bear despite mixed returns",
		},
		{
			name:           "Insufficient data defaults to sideways",
			returns:        []float64{0.01, 0.02},
			window:         10,
			expectedRegime: MarketRegimeSideways,
			description:    "Not enough data points",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			regime := detector.DetectRegimeFromHistory(tt.returns, tt.window)
			if regime != tt.expectedRegime {
				// Calculate actual metrics for debugging
				avgReturn := calculateMean(tt.returns)
				vol := calculateStdDev(tt.returns)
				dd := calculateMaxDrawdown(tt.returns)

				t.Errorf("DetectRegimeFromHistory() = %v, want %v\n"+
					"  Description: %s\n"+
					"  Metrics: avgReturn=%.4f%%, vol=%.2f%%, drawdown=%.1f%%",
					regime, tt.expectedRegime, tt.description,
					avgReturn*100, vol*100, dd*100)
			}
		})
	}
}

func TestDetectRegimeFromTimeSeries(t *testing.T) {
	detector := NewMarketRegimeDetector(zerolog.Nop())

	// Test 1: Bull market - portfolio grows from 100 to 110 over 30 days
	t.Run("Bull market growth", func(t *testing.T) {
		timestamps := make([]time.Time, 30)
		values := make([]float64, 30)
		baseTime := time.Now().AddDate(0, 0, -30)

		// Simulate realistic bull market: +10% over 30 days
		for i := 0; i < 30; i++ {
			timestamps[i] = baseTime.AddDate(0, 0, i)
			// Compound growth: 100 * (1.003)^i gives ~9.4% total
			values[i] = 100.0 * pow(1.003, float64(i))
		}

		regime := detector.DetectRegimeFromTimeSeries(timestamps, values, 20)
		if regime != MarketRegimeBull {
			avgReturn := calculateMean(dailyReturnsFromValues(values))
			t.Errorf("Bull market not detected: regime=%v, avgReturn=%.4f%%",
				regime, avgReturn*100)
		}
	})

	// Test 2: Bear market - portfolio declines from 100 to 90 over 30 days
	t.Run("Bear market decline", func(t *testing.T) {
		timestamps := make([]time.Time, 30)
		values := make([]float64, 30)
		baseTime := time.Now().AddDate(0, 0, -30)

		// Simulate bear market: -10% over 30 days
		for i := 0; i < 30; i++ {
			timestamps[i] = baseTime.AddDate(0, 0, i)
			// Compound decline: 100 * (0.997)^i gives ~-8.7% total
			values[i] = 100.0 * pow(0.997, float64(i))
		}

		regime := detector.DetectRegimeFromTimeSeries(timestamps, values, 20)
		if regime != MarketRegimeBear {
			avgReturn := calculateMean(dailyReturnsFromValues(values))
			t.Errorf("Bear market not detected: regime=%v, avgReturn=%.4f%%",
				regime, avgReturn*100)
		}
	})

	// Test 3: Sideways market - oscillates around 100
	t.Run("Sideways oscillation", func(t *testing.T) {
		timestamps := make([]time.Time, 30)
		values := make([]float64, 30)
		baseTime := time.Now().AddDate(0, 0, -30)

		// Simulate sideways: oscillates symmetrically around 100
		// Pattern: 100, 101, 100, 99, 100, 101, 100, 99... (net zero)
		oscillation := []float64{0, 1, 0, -1} // Offsets from 100
		for i := 0; i < 30; i++ {
			timestamps[i] = baseTime.AddDate(0, 0, i)
			values[i] = 100.0 + oscillation[i%4]
		}

		regime := detector.DetectRegimeFromTimeSeries(timestamps, values, 20)
		if regime != MarketRegimeSideways {
			avgReturn := calculateMean(dailyReturnsFromValues(values))
			t.Errorf("Sideways market not detected: regime=%v, avgReturn=%.4f%%",
				regime, avgReturn*100)
		}
	})

	// Test 4: Error handling - mismatched lengths
	t.Run("Mismatched lengths", func(t *testing.T) {
		timestamps := make([]time.Time, 5)
		values := make([]float64, 10)

		regime := detector.DetectRegimeFromTimeSeries(timestamps, values, 5)
		if regime != MarketRegimeSideways {
			t.Errorf("Expected sideways for error case, got %v", regime)
		}
	})
}

// Helper for test debugging
func dailyReturnsFromValues(values []float64) []float64 {
	returns := make([]float64, 0, len(values)-1)
	for i := 1; i < len(values); i++ {
		if values[i-1] != 0 {
			returns = append(returns, (values[i]-values[i-1])/values[i-1])
		}
	}
	return returns
}

// Simple power function for tests
func pow(base, exp float64) float64 {
	if exp == 0 {
		return 1
	}
	result := 1.0
	for i := 0; i < int(exp); i++ {
		result *= base
	}
	return result
}

func TestCalculateMean(t *testing.T) {
	tests := []struct {
		name     string
		values   []float64
		expected float64
	}{
		{
			name:     "Positive values",
			values:   []float64{0.01, 0.02, 0.03, 0.04, 0.05},
			expected: 0.03,
		},
		{
			name:     "Negative values",
			values:   []float64{-0.01, -0.02, -0.03},
			expected: -0.02,
		},
		{
			name:     "Mixed values",
			values:   []float64{-0.02, 0.0, 0.02},
			expected: 0.0,
		},
		{
			name:     "Empty array",
			values:   []float64{},
			expected: 0.0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := calculateMean(tt.values)
			if abs(result-tt.expected) > 0.0001 {
				t.Errorf("calculateMean() = %v, want %v", result, tt.expected)
			}
		})
	}
}

func TestCalculateMaxDrawdown(t *testing.T) {
	tests := []struct {
		name    string
		returns []float64
		minDD   float64 // Minimum expected (could be worse)
		maxDD   float64 // Maximum expected (shouldn't be better)
	}{
		{
			name:    "No drawdown - only gains",
			returns: []float64{0.01, 0.02, 0.015, 0.01},
			minDD:   -0.001,
			maxDD:   0.001,
		},
		{
			name:    "Simple drawdown",
			returns: []float64{0.10, -0.05, -0.05},
			minDD:   -0.10,
			maxDD:   -0.09,
		},
		{
			name:    "Recovery after drawdown",
			returns: []float64{0.10, -0.10, 0.10},
			minDD:   -0.11,
			maxDD:   -0.09,
		},
		{
			name:    "Multiple drawdowns",
			returns: []float64{0.05, -0.03, -0.02, 0.04, -0.06, -0.02},
			minDD:   -0.09,
			maxDD:   -0.05,
		},
		{
			name:    "Empty returns",
			returns: []float64{},
			minDD:   -0.001,
			maxDD:   0.001,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := calculateMaxDrawdown(tt.returns)
			if result < tt.minDD || result > tt.maxDD {
				t.Errorf("calculateMaxDrawdown() = %.4f, want between %.4f and %.4f",
					result, tt.minDD, tt.maxDD)
			}
		})
	}
}

func abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}
