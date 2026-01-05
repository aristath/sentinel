package scorers

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestOpportunityScorer_StoresRawBelow52wHigh(t *testing.T) {
	scorer := NewOpportunityScorer()

	// Create daily prices with a 52-week high
	dailyPrices := make([]float64, 260) // More than 52 weeks
	basePrice := 100.0
	high52w := 150.0
	currentPrice := 120.0 // 20% below high

	// Set prices with high at some point and current lower
	for i := range dailyPrices {
		if i < 100 {
			// Rising to high
			dailyPrices[i] = basePrice + float64(i)*0.5
		} else if i < 150 {
			// At high
			dailyPrices[i] = high52w
		} else {
			// Dropping to current
			dailyPrices[i] = high52w - float64(i-150)*0.2
		}
	}
	// Set last price to current
	dailyPrices[len(dailyPrices)-1] = currentPrice

	peRatio := 15.0
	marketAvgPE := 22.0

	result := scorer.Calculate(dailyPrices, &peRatio, nil, marketAvgPE)

	// Verify raw below_52w_high percentage is stored
	assert.Contains(t, result.Components, "below_52w_high_raw", "Components should contain below_52w_high_raw")

	// Verify scored value is still present
	assert.Contains(t, result.Components, "below_52w_high", "Components should contain scored below_52w_high")

	// Verify raw value is the actual percentage (0.20 for 20% below)
	rawBelow52w := result.Components["below_52w_high_raw"]
	expectedPct := (high52w - currentPrice) / high52w
	assert.InDelta(t, expectedPct, rawBelow52w, 0.01, "Raw below_52w_high should match calculated percentage")

	// Verify scored value is between 0 and 1
	scoredBelow52w := result.Components["below_52w_high"]
	assert.GreaterOrEqual(t, scoredBelow52w, 0.0, "Scored below_52w_high should be >= 0")
	assert.LessOrEqual(t, scoredBelow52w, 1.0, "Scored below_52w_high should be <= 1")
}

func TestOpportunityScorer_StoresRawBelow52wHigh_WithNilHigh(t *testing.T) {
	scorer := NewOpportunityScorer()

	// Create insufficient daily prices
	dailyPrices := make([]float64, 10)
	for i := range dailyPrices {
		dailyPrices[i] = 100.0 + float64(i)*0.1
	}

	peRatio := 15.0
	marketAvgPE := 22.0

	result := scorer.Calculate(dailyPrices, &peRatio, nil, marketAvgPE)

	// When 52w high is nil, below_52w_high_raw should be 0.0
	if rawBelow52w, exists := result.Components["below_52w_high_raw"]; exists {
		assert.Equal(t, 0.0, rawBelow52w, "Raw below_52w_high should be 0.0 when calculation fails")
	}
}
