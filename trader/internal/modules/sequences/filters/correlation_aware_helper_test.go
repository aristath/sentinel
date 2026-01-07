package filters

import (
	"testing"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/stretchr/testify/assert"
)

func TestExtractAllBuySymbols(t *testing.T) {
	tests := []struct {
		name      string
		sequences []domain.ActionSequence
		expected  []string
	}{
		{
			name: "single sequence with buy",
			sequences: []domain.ActionSequence{
				{
					Actions: []domain.ActionCandidate{
						{Symbol: "AAPL", Side: "BUY", Quantity: 10},
						{Symbol: "GOOGL", Side: "SELL", Quantity: 5},
					},
				},
			},
			expected: []string{"AAPL"},
		},
		{
			name: "multiple sequences with overlapping symbols",
			sequences: []domain.ActionSequence{
				{
					Actions: []domain.ActionCandidate{
						{Symbol: "AAPL", Side: "BUY", Quantity: 10},
						{Symbol: "GOOGL", Side: "BUY", Quantity: 5},
					},
				},
				{
					Actions: []domain.ActionCandidate{
						{Symbol: "AAPL", Side: "BUY", Quantity: 15},
						{Symbol: "MSFT", Side: "BUY", Quantity: 8},
					},
				},
			},
			expected: []string{"AAPL", "GOOGL", "MSFT"}, // Should be unique
		},
		{
			name: "no buy actions",
			sequences: []domain.ActionSequence{
				{
					Actions: []domain.ActionCandidate{
						{Symbol: "AAPL", Side: "SELL", Quantity: 10},
					},
				},
			},
			expected: []string{},
		},
		{
			name:      "empty sequences",
			sequences: []domain.ActionSequence{},
			expected:  []string{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := extractAllBuySymbols(tt.sequences)

			// Convert to map for easier comparison (order may vary)
			resultMap := make(map[string]bool)
			for _, sym := range result {
				resultMap[sym] = true
			}

			expectedMap := make(map[string]bool)
			for _, sym := range tt.expected {
				expectedMap[sym] = true
			}

			assert.Equal(t, len(tt.expected), len(result), "Should have same number of unique symbols")
			for sym := range expectedMap {
				assert.True(t, resultMap[sym], "Should contain symbol %s", sym)
			}
		})
	}
}

func TestExtractBuySymbols(t *testing.T) {
	tests := []struct {
		name     string
		sequence domain.ActionSequence
		expected []string
	}{
		{
			name: "sequence with buy and sell",
			sequence: domain.ActionSequence{
				Actions: []domain.ActionCandidate{
					{Symbol: "AAPL", Side: "BUY", Quantity: 10},
					{Symbol: "GOOGL", Side: "SELL", Quantity: 5},
					{Symbol: "MSFT", Side: "BUY", Quantity: 8},
				},
			},
			expected: []string{"AAPL", "MSFT"},
		},
		{
			name: "only buy actions",
			sequence: domain.ActionSequence{
				Actions: []domain.ActionCandidate{
					{Symbol: "AAPL", Side: "BUY", Quantity: 10},
					{Symbol: "GOOGL", Side: "BUY", Quantity: 5},
				},
			},
			expected: []string{"AAPL", "GOOGL"},
		},
		{
			name: "no buy actions",
			sequence: domain.ActionSequence{
				Actions: []domain.ActionCandidate{
					{Symbol: "AAPL", Side: "SELL", Quantity: 10},
				},
			},
			expected: []string{},
		},
		{
			name:     "empty sequence",
			sequence: domain.ActionSequence{},
			expected: []string{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := extractBuySymbols(tt.sequence)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestHasHighCorrelation(t *testing.T) {
	tests := []struct {
		name           string
		symbols        []string
		correlationMap map[string]float64
		threshold      float64
		expected       bool
	}{
		{
			name:    "high positive correlation",
			symbols: []string{"AAPL", "GOOGL"},
			correlationMap: map[string]float64{
				"AAPL:GOOGL": 0.9,
			},
			threshold: 0.8,
			expected:  true,
		},
		{
			name:    "high negative correlation",
			symbols: []string{"AAPL", "GOOGL"},
			correlationMap: map[string]float64{
				"AAPL:GOOGL": -0.9,
			},
			threshold: 0.8,
			expected:  true,
		},
		{
			name:    "low correlation",
			symbols: []string{"AAPL", "GOOGL"},
			correlationMap: map[string]float64{
				"AAPL:GOOGL": 0.5,
			},
			threshold: 0.8,
			expected:  false,
		},
		{
			name:    "reversed key order",
			symbols: []string{"AAPL", "GOOGL"},
			correlationMap: map[string]float64{
				"GOOGL:AAPL": 0.9,
			},
			threshold: 0.8,
			expected:  true,
		},
		{
			name:    "multiple symbols with high correlation",
			symbols: []string{"AAPL", "GOOGL", "MSFT"},
			correlationMap: map[string]float64{
				"GOOGL:MSFT": 0.9,
			},
			threshold: 0.8,
			expected:  true,
		},
		{
			name:    "no correlation data",
			symbols: []string{"AAPL", "GOOGL"},
			correlationMap: map[string]float64{
				"OTHER:PAIR": 0.9,
			},
			threshold: 0.8,
			expected:  false,
		},
		{
			name:           "empty symbols",
			symbols:        []string{},
			correlationMap: map[string]float64{},
			threshold:      0.8,
			expected:       false,
		},
		{
			name:    "single symbol",
			symbols: []string{"AAPL"},
			correlationMap: map[string]float64{
				"AAPL:GOOGL": 0.9,
			},
			threshold: 0.8,
			expected:  false,
		},
		{
			name:    "correlation at threshold",
			symbols: []string{"AAPL", "GOOGL"},
			correlationMap: map[string]float64{
				"AAPL:GOOGL": 0.8,
			},
			threshold: 0.8,
			expected:  false, // Should be > threshold, not >=
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := hasHighCorrelation(tt.symbols, tt.correlationMap, tt.threshold)
			assert.Equal(t, tt.expected, result)

			// Verify it uses absolute value (test separately)
			if tt.name == "high positive correlation" || tt.name == "high negative correlation" {
				// Both should return true due to absolute value check
				assert.True(t, result, "Should treat high negative correlation as high correlation")
			}
		})
	}

	// Additional test to verify absolute value behavior
	t.Run("absolute value check", func(t *testing.T) {
		symbols := []string{"AAPL", "GOOGL"}
		correlationMap := map[string]float64{
			"AAPL:GOOGL": -0.9,
		}

		// Should return true because abs(-0.9) = 0.9 > 0.8
		result := hasHighCorrelation(symbols, correlationMap, 0.8)
		assert.True(t, result, "Should use absolute value for correlation check")

		// Test with positive correlation
		correlationMap2 := map[string]float64{
			"AAPL:GOOGL": 0.9,
		}
		result2 := hasHighCorrelation(symbols, correlationMap2, 0.8)
		assert.True(t, result2, "Should also detect high positive correlation")
	})
}
