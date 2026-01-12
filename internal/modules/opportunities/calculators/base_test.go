package calculators

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestGetFloatParam(t *testing.T) {
	tests := []struct {
		name         string
		params       map[string]interface{}
		key          string
		defaultValue float64
		expected     float64
	}{
		{
			name:         "float64 value exists",
			params:       map[string]interface{}{"key": 123.45},
			key:          "key",
			defaultValue: 0.0,
			expected:     123.45,
		},
		{
			name:         "int value exists (converted to float64)",
			params:       map[string]interface{}{"key": 100},
			key:          "key",
			defaultValue: 0.0,
			expected:     100.0,
		},
		{
			name:         "key does not exist",
			params:       map[string]interface{}{"other": 123.45},
			key:          "key",
			defaultValue: 99.99,
			expected:     99.99,
		},
		{
			name:         "nil params",
			params:       nil,
			key:          "key",
			defaultValue: 99.99,
			expected:     99.99,
		},
		{
			name:         "wrong type (string)",
			params:       map[string]interface{}{"key": "not a number"},
			key:          "key",
			defaultValue: 99.99,
			expected:     99.99,
		},
		{
			name:         "wrong type (bool)",
			params:       map[string]interface{}{"key": true},
			key:          "key",
			defaultValue: 99.99,
			expected:     99.99,
		},
		{
			name:         "zero float64 value",
			params:       map[string]interface{}{"key": 0.0},
			key:          "key",
			defaultValue: 99.99,
			expected:     0.0,
		},
		{
			name:         "negative float64 value",
			params:       map[string]interface{}{"key": -123.45},
			key:          "key",
			defaultValue: 0.0,
			expected:     -123.45,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := GetFloatParam(tt.params, tt.key, tt.defaultValue)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestGetIntParam(t *testing.T) {
	tests := []struct {
		name         string
		params       map[string]interface{}
		key          string
		defaultValue int
		expected     int
	}{
		{
			name:         "int value exists",
			params:       map[string]interface{}{"key": 100},
			key:          "key",
			defaultValue: 0,
			expected:     100,
		},
		{
			name:         "float64 value exists (converted to int)",
			params:       map[string]interface{}{"key": 123.45},
			key:          "key",
			defaultValue: 0,
			expected:     123,
		},
		{
			name:         "float64 value with decimal (truncated)",
			params:       map[string]interface{}{"key": 123.99},
			key:          "key",
			defaultValue: 0,
			expected:     123,
		},
		{
			name:         "key does not exist",
			params:       map[string]interface{}{"other": 100},
			key:          "key",
			defaultValue: 99,
			expected:     99,
		},
		{
			name:         "nil params",
			params:       nil,
			key:          "key",
			defaultValue: 99,
			expected:     99,
		},
		{
			name:         "wrong type (string)",
			params:       map[string]interface{}{"key": "not a number"},
			key:          "key",
			defaultValue: 99,
			expected:     99,
		},
		{
			name:         "wrong type (bool)",
			params:       map[string]interface{}{"key": true},
			key:          "key",
			defaultValue: 99,
			expected:     99,
		},
		{
			name:         "zero int value",
			params:       map[string]interface{}{"key": 0},
			key:          "key",
			defaultValue: 99,
			expected:     0,
		},
		{
			name:         "negative int value",
			params:       map[string]interface{}{"key": -100},
			key:          "key",
			defaultValue: 0,
			expected:     -100,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := GetIntParam(tt.params, tt.key, tt.defaultValue)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestGetBoolParam(t *testing.T) {
	tests := []struct {
		name         string
		params       map[string]interface{}
		key          string
		defaultValue bool
		expected     bool
	}{
		{
			name:         "bool true exists",
			params:       map[string]interface{}{"key": true},
			key:          "key",
			defaultValue: false,
			expected:     true,
		},
		{
			name:         "bool false exists",
			params:       map[string]interface{}{"key": false},
			key:          "key",
			defaultValue: true,
			expected:     false,
		},
		{
			name:         "key does not exist",
			params:       map[string]interface{}{"other": true},
			key:          "key",
			defaultValue: true,
			expected:     true,
		},
		{
			name:         "nil params",
			params:       nil,
			key:          "key",
			defaultValue: true,
			expected:     true,
		},
		{
			name:         "wrong type (string)",
			params:       map[string]interface{}{"key": "true"},
			key:          "key",
			defaultValue: false,
			expected:     false,
		},
		{
			name:         "wrong type (int)",
			params:       map[string]interface{}{"key": 1},
			key:          "key",
			defaultValue: false,
			expected:     false,
		},
		{
			name:         "wrong type (float64)",
			params:       map[string]interface{}{"key": 1.0},
			key:          "key",
			defaultValue: false,
			expected:     false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := GetBoolParam(tt.params, tt.key, tt.defaultValue)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestNewBaseCalculator(t *testing.T) {
	log := zerolog.Nop()
	calc := NewBaseCalculator(log, "test_calculator")

	assert.NotNil(t, calc)
	assert.NotNil(t, calc.log)
}

func TestExclusionCollector(t *testing.T) {
	t.Run("collects exclusions", func(t *testing.T) {
		collector := NewExclusionCollector("opportunity_buys", nil)

		collector.Add("US0378331005", "AAPL", "Apple Inc.", "score below minimum")
		collector.Add("US5949181045", "MSFT", "Microsoft Corp.", "value trap detected")

		result := collector.Result()
		assert.Len(t, result, 2)
	})

	t.Run("accumulates reasons for same ISIN", func(t *testing.T) {
		collector := NewExclusionCollector("opportunity_buys", nil)

		collector.Add("US0378331005", "AAPL", "Apple Inc.", "score below minimum")
		collector.Add("US0378331005", "AAPL", "Apple Inc.", "quality gate failed")

		result := collector.Result()
		assert.Len(t, result, 1)
		assert.Len(t, result[0].Reasons, 2)

		// Check reasons are present (now PreFilteredReason type)
		reasons := make([]string, len(result[0].Reasons))
		for i, r := range result[0].Reasons {
			reasons[i] = r.Reason
		}
		assert.Contains(t, reasons, "score below minimum")
		assert.Contains(t, reasons, "quality gate failed")
	})

	t.Run("deduplicates same reason", func(t *testing.T) {
		collector := NewExclusionCollector("opportunity_buys", nil)

		collector.Add("US0378331005", "AAPL", "Apple Inc.", "score below minimum")
		collector.Add("US0378331005", "AAPL", "Apple Inc.", "score below minimum")

		result := collector.Result()
		assert.Len(t, result, 1)
		assert.Len(t, result[0].Reasons, 1)
	})

	t.Run("ignores empty ISIN", func(t *testing.T) {
		collector := NewExclusionCollector("opportunity_buys", nil)

		collector.Add("", "AAPL", "Apple Inc.", "no ISIN")

		result := collector.Result()
		assert.Empty(t, result)
	})

	t.Run("sets calculator name", func(t *testing.T) {
		collector := NewExclusionCollector("averaging_down", nil)
		collector.Add("US0378331005", "AAPL", "Apple Inc.", "reason")

		result := collector.Result()
		assert.Equal(t, "averaging_down", result[0].Calculator)
	})

	t.Run("marks dismissed reasons", func(t *testing.T) {
		dismissedFilters := map[string]map[string][]string{
			"US0378331005": {
				"opportunity_buys": {"score below minimum"},
			},
		}
		collector := NewExclusionCollector("opportunity_buys", dismissedFilters)

		collector.Add("US0378331005", "AAPL", "Apple Inc.", "score below minimum")
		collector.Add("US0378331005", "AAPL", "Apple Inc.", "quality gate failed")

		result := collector.Result()
		assert.Len(t, result, 1)
		assert.Len(t, result[0].Reasons, 2)

		// Find and check each reason
		for _, r := range result[0].Reasons {
			if r.Reason == "score below minimum" {
				assert.True(t, r.Dismissed, "score below minimum should be dismissed")
			} else if r.Reason == "quality gate failed" {
				assert.False(t, r.Dismissed, "quality gate failed should NOT be dismissed")
			}
		}
	})

	t.Run("dismissal is calculator-specific", func(t *testing.T) {
		// Only "averaging_down" has this reason dismissed
		dismissedFilters := map[string]map[string][]string{
			"US0378331005": {
				"averaging_down": {"score below minimum"},
			},
		}

		// Use different calculator - should not be dismissed
		collector := NewExclusionCollector("opportunity_buys", dismissedFilters)
		collector.Add("US0378331005", "AAPL", "Apple Inc.", "score below minimum")

		result := collector.Result()
		assert.Len(t, result, 1)
		assert.False(t, result[0].Reasons[0].Dismissed, "should not be dismissed for different calculator")
	})

	t.Run("reasons without dismissal are not dismissed", func(t *testing.T) {
		collector := NewExclusionCollector("opportunity_buys", nil)
		collector.Add("US0378331005", "AAPL", "Apple Inc.", "score below minimum")

		result := collector.Result()
		assert.Len(t, result, 1)
		assert.False(t, result[0].Reasons[0].Dismissed, "should default to not dismissed")
	})
}
