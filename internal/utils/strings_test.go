package utils

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestParseCSV(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected []string
	}{
		{
			name:     "empty string",
			input:    "",
			expected: nil,
		},
		{
			name:     "single value",
			input:    "Technology",
			expected: []string{"Technology"},
		},
		{
			name:     "two values",
			input:    "Energy, Technology",
			expected: []string{"Energy", "Technology"},
		},
		{
			name:     "three values with varied spacing",
			input:    "US,  Europe , Asia",
			expected: []string{"US", "Europe", "Asia"},
		},
		{
			name:     "no spaces after comma",
			input:    "Finance,Healthcare",
			expected: []string{"Finance", "Healthcare"},
		},
		{
			name:     "trailing comma",
			input:    "Finance,",
			expected: []string{"Finance"},
		},
		{
			name:     "leading comma",
			input:    ",Healthcare",
			expected: []string{"Healthcare"},
		},
		{
			name:     "only spaces",
			input:    "   ",
			expected: nil,
		},
		{
			name:     "comma only",
			input:    ",",
			expected: nil,
		},
		{
			name:     "multiple commas",
			input:    ",,Technology,,Finance,,",
			expected: []string{"Technology", "Finance"},
		},
		{
			name:     "value with internal spaces preserved",
			input:    "Consumer Goods, Real Estate",
			expected: []string{"Consumer Goods", "Real Estate"},
		},
		{
			name:     "mixed spacing around values",
			input:    "  Energy  ,  Technology  ",
			expected: []string{"Energy", "Technology"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := ParseCSV(tt.input)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestParseCSV_Idempotent(t *testing.T) {
	// Parsing an already-parsed single value should return same result
	input := "Technology"
	firstParse := ParseCSV(input)
	assert.Equal(t, []string{"Technology"}, firstParse)

	// Parsing the single result element should give same result
	if len(firstParse) > 0 {
		secondParse := ParseCSV(firstParse[0])
		assert.Equal(t, []string{"Technology"}, secondParse)
	}
}

func TestParseCSV_PreservesInput(t *testing.T) {
	// Verify that the function doesn't modify the input string
	input := "Energy, Technology"
	originalInput := input

	_ = ParseCSV(input)

	assert.Equal(t, originalInput, input, "input should not be modified")
}

func TestParseCSV_RealWorldExamples(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected []string
	}{
		{
			name:     "typical industry",
			input:    "Information Technology",
			expected: []string{"Information Technology"},
		},
		{
			name:     "multi-industry security",
			input:    "Energy, Technology, Infrastructure",
			expected: []string{"Energy", "Technology", "Infrastructure"},
		},
		{
			name:     "typical geography",
			input:    "United States",
			expected: []string{"United States"},
		},
		{
			name:     "multi-geography security",
			input:    "US, Europe, Asia Pacific",
			expected: []string{"US", "Europe", "Asia Pacific"},
		},
		{
			name:     "conglomerate industries",
			input:    "Consumer Discretionary, Consumer Staples, Technology",
			expected: []string{"Consumer Discretionary", "Consumer Staples", "Technology"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := ParseCSV(tt.input)
			assert.Equal(t, tt.expected, result)
		})
	}
}
