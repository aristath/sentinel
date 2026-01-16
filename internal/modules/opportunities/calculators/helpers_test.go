package calculators

import (
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/stretchr/testify/assert"
)

// createEnrichedPosition is a test helper that creates an EnrichedPosition from a Position and Security.
// This simplifies test data setup by combining the old fragmented data into the new unified format.
func createEnrichedPosition(pos domain.Position, sec universe.Security, currentPrice float64) planningdomain.EnrichedPosition {
	return planningdomain.EnrichedPosition{
		ISIN:         pos.ISIN,
		Symbol:       pos.Symbol,
		Quantity:     float64(pos.Quantity),
		AverageCost:  pos.AverageCost,
		Currency:     sec.Currency,
		SecurityName: sec.Name,
		Geography:    sec.Geography,
		Exchange:     sec.FullExchangeName,
		AllowBuy:     sec.AllowBuy,
		AllowSell:    sec.AllowSell,
		MinLot:       sec.MinLot,
		CurrentPrice: currentPrice,
	}
}

// createEnrichedPositionWithWeight creates an EnrichedPosition with WeightInPortfolio set.
func createEnrichedPositionWithWeight(pos domain.Position, sec universe.Security, currentPrice, weight float64) planningdomain.EnrichedPosition {
	enriched := createEnrichedPosition(pos, sec, currentPrice)
	enriched.WeightInPortfolio = weight
	return enriched
}

func TestAbs(t *testing.T) {
	tests := []struct {
		name     string
		input    float64
		expected float64
	}{
		{
			name:     "positive number",
			input:    5.0,
			expected: 5.0,
		},
		{
			name:     "negative number",
			input:    -5.0,
			expected: 5.0,
		},
		{
			name:     "zero",
			input:    0.0,
			expected: 0.0,
		},
		{
			name:     "positive decimal",
			input:    3.14,
			expected: 3.14,
		},
		{
			name:     "negative decimal",
			input:    -3.14,
			expected: 3.14,
		},
		{
			name:     "large positive",
			input:    1000.0,
			expected: 1000.0,
		},
		{
			name:     "large negative",
			input:    -1000.0,
			expected: 1000.0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := abs(tt.input)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestContains(t *testing.T) {
	tests := []struct {
		name     string
		slice    []string
		value    string
		expected bool
	}{
		{
			name:     "empty slice",
			slice:    []string{},
			value:    "test",
			expected: false,
		},
		{
			name:     "contains value",
			slice:    []string{"apple", "banana", "cherry"},
			value:    "banana",
			expected: true,
		},
		{
			name:     "does not contain value",
			slice:    []string{"apple", "banana", "cherry"},
			value:    "orange",
			expected: false,
		},
		{
			name:     "contains at beginning",
			slice:    []string{"apple", "banana", "cherry"},
			value:    "apple",
			expected: true,
		},
		{
			name:     "contains at end",
			slice:    []string{"apple", "banana", "cherry"},
			value:    "cherry",
			expected: true,
		},
		{
			name:     "case sensitive",
			slice:    []string{"apple", "banana", "cherry"},
			value:    "APPLE",
			expected: false,
		},
		{
			name:     "empty string in slice",
			slice:    []string{"apple", "", "cherry"},
			value:    "",
			expected: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := contains(tt.slice, tt.value)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestMin(t *testing.T) {
	tests := []struct {
		name     string
		a        int
		b        int
		expected int
	}{
		{
			name:     "a less than b",
			a:        5,
			b:        10,
			expected: 5,
		},
		{
			name:     "b less than a",
			a:        10,
			b:        5,
			expected: 5,
		},
		{
			name:     "equal values",
			a:        5,
			b:        5,
			expected: 5,
		},
		{
			name:     "negative values",
			a:        -5,
			b:        -10,
			expected: -10,
		},
		{
			name:     "one negative",
			a:        -5,
			b:        10,
			expected: -5,
		},
		{
			name:     "zero values",
			a:        0,
			b:        0,
			expected: 0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := min(tt.a, tt.b)
			assert.Equal(t, tt.expected, result)
		})
	}
}
