package patterns

import (
	"testing"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/stretchr/testify/assert"
)

func TestGenerateSequenceHash(t *testing.T) {
	tests := []struct {
		name     string
		actions  []domain.ActionCandidate
		expected string // We'll check for a valid MD5 hash (32 hex chars)
	}{
		{
			name: "single action",
			actions: []domain.ActionCandidate{
				{Symbol: "AAPL", Side: "BUY", Quantity: 10},
			},
		},
		{
			name: "multiple actions",
			actions: []domain.ActionCandidate{
				{Symbol: "AAPL", Side: "BUY", Quantity: 10},
				{Symbol: "GOOGL", Side: "SELL", Quantity: 5},
			},
		},
		{
			name:    "empty actions",
			actions: []domain.ActionCandidate{},
			// Empty actions will hash an empty JSON array, producing a valid MD5 hash
		},
		{
			name: "same actions produce same hash",
			actions: []domain.ActionCandidate{
				{Symbol: "AAPL", Side: "BUY", Quantity: 10},
				{Symbol: "GOOGL", Side: "SELL", Quantity: 5},
			},
		},
		{
			name: "different order produces different hash",
			actions: []domain.ActionCandidate{
				{Symbol: "GOOGL", Side: "SELL", Quantity: 5},
				{Symbol: "AAPL", Side: "BUY", Quantity: 10},
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			hash1 := generateSequenceHash(tt.actions)

			// Should be a valid MD5 hash (32 hex characters), even for empty
			assert.Len(t, hash1, 32, "Hash should be 32 hex characters (MD5)")

			// Verify deterministic: same input should produce same hash
			hash2 := generateSequenceHash(tt.actions)
			assert.Equal(t, hash1, hash2, "Hash should be deterministic")

			// For the "same actions" test, verify it matches
			if tt.name == "same actions produce same hash" {
				hash3 := generateSequenceHash([]domain.ActionCandidate{
					{Symbol: "AAPL", Side: "BUY", Quantity: 10},
					{Symbol: "GOOGL", Side: "SELL", Quantity: 5},
				})
				assert.Equal(t, hash1, hash3, "Same actions should produce same hash")
			}

			// For the "different order" test, verify it's different from "same actions"
			if tt.name == "different order produces different hash" {
				hashSameOrder := generateSequenceHash([]domain.ActionCandidate{
					{Symbol: "AAPL", Side: "BUY", Quantity: 10},
					{Symbol: "GOOGL", Side: "SELL", Quantity: 5},
				})
				assert.NotEqual(t, hash1, hashSameOrder, "Different order should produce different hash")
			}
		})
	}
}

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
			params:       map[string]interface{}{"key": 100.7},
			key:          "key",
			defaultValue: 0,
			expected:     100,
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
			defaultValue: false,
			expected:     false,
		},
		{
			name:         "wrong type (string)",
			params:       map[string]interface{}{"key": "true"},
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
