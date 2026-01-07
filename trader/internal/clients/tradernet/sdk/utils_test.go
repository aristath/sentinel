package sdk

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

// TestSign_MatchesPythonSDK tests that our sign function produces the same output
// as the Python SDK's sign function for the same inputs.
// Python: hmac.new(key.encode(), msg.encode(), digestmod='sha256').hexdigest()
func TestSign_MatchesPythonSDK(t *testing.T) {
	// Test cases with known Python SDK outputs
	// These were generated using Python's hmac module with SHA256

	tests := []struct {
		name    string
		key     string
		message string
		want    string
	}{
		{
			name:    "empty message",
			key:     "test_key",
			message: "",
			want:    "d056b2b640f407a9daeba0b13c3b3966e5b69e84283ec3c7fa0cac56a02208a7",
		},
		{
			name:    "simple message",
			key:     "secret",
			message: "hello",
			want:    "88aab3ede8d3adf94d26ab90d3bafd4a2083070c3bcce9c014ee04a443847c0b",
		},
		{
			name:    "JSON payload with timestamp",
			key:     "my_private_key",
			message: `{"instr_name":"AAPL.US","action_id":1}1234567890`,
			want:    "a1b37308c843d2c3d206063447cbc24d60c9eef7bff93c2f2263addb05fec2e6",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := sign(tt.key, tt.message)
			assert.Equal(t, tt.want, got, "signature should match Python SDK output")
		})
	}
}

// TestSign_ProducesValidHMAC tests that sign produces a valid HMAC-SHA256 hex string
func TestSign_ProducesValidHMAC(t *testing.T) {
	key := "test_key"
	message := "test_message"

	result := sign(key, message)

	// HMAC-SHA256 produces 64 hex characters (32 bytes)
	assert.Len(t, result, 64, "HMAC-SHA256 should produce 64 hex characters")

	// Should be lowercase hex
	for _, c := range result {
		assert.True(t, (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'),
			"result should be lowercase hex: %c", c)
	}
}

// TestSign_Deterministic tests that sign produces the same output for the same inputs
func TestSign_Deterministic(t *testing.T) {
	key := "test_key"
	message := "test_message"

	result1 := sign(key, message)
	result2 := sign(key, message)

	assert.Equal(t, result1, result2, "sign should be deterministic")
}

// TestStringify_CompactJSON tests that stringify produces compact JSON (no spaces)
func TestStringify_CompactJSON(t *testing.T) {
	tests := []struct {
		name     string
		input    interface{}
		expected string
	}{
		{
			name:     "empty object",
			input:    map[string]interface{}{},
			expected: "{}",
		},
		{
			name:     "simple object",
			input:    map[string]interface{}{"a": 1, "b": 2},
			expected: `{"a":1,"b":2}`,
		},
		{
			name:     "nested object",
			input:    map[string]interface{}{"params": map[string]interface{}{"ticker": "AAPL.US"}},
			expected: `{"params":{"ticker":"AAPL.US"}}`,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := stringify(tt.input)
			assert.NoError(t, err)
			assert.Equal(t, tt.expected, result)
			// Verify no spaces
			assert.NotContains(t, result, " ", "JSON should not contain spaces")
		})
	}
}

// TestStringify_FieldOrderPreserved tests that struct field order is preserved
func TestStringify_FieldOrderPreserved(t *testing.T) {
	// This test verifies that struct field order (not map key order) is used
	// Go structs preserve field order, which is what we need to match Python's dict insertion order

	type TestParams struct {
		InstrName    string  `json:"instr_name"`
		ActionID     int     `json:"action_id"`
		OrderTypeID  int     `json:"order_type_id"`
		Qty          int     `json:"qty"`
		LimitPrice   float64 `json:"limit_price"`
		ExpirationID int     `json:"expiration_id"`
	}

	params := TestParams{
		InstrName:    "AAPL.US",
		ActionID:     1,
		OrderTypeID:  2,
		Qty:          10,
		LimitPrice:   150.0,
		ExpirationID: 1,
	}

	result, err := stringify(params)
	assert.NoError(t, err)

	// Field order should match struct definition order
	// This is critical for signature matching!
	expected := `{"instr_name":"AAPL.US","action_id":1,"order_type_id":2,"qty":10,"limit_price":150,"expiration_id":1}`
	assert.Equal(t, expected, result, "field order must match struct definition order")
}

// TestStringify_MatchesPythonOutput tests that stringify matches Python's json.dumps with separators
func TestStringify_MatchesPythonOutput(t *testing.T) {
	// Python: json.dumps({'a': 1, 'b': 2}, separators=(',', ':'))
	// Result: '{"a":1,"b":2}'

	input := map[string]interface{}{"a": 1, "b": 2}
	result, err := stringify(input)
	assert.NoError(t, err)

	// Should match Python output (no spaces, no key sorting)
	// Note: Go maps may have different key order, but structs preserve field order
	assert.Contains(t, result, `"a":1`)
	assert.Contains(t, result, `"b":2`)
	assert.NotContains(t, result, " ")
}

func TestAbsInt(t *testing.T) {
	tests := []struct {
		name     string
		input    int
		expected int
	}{
		{"positive number", 5, 5},
		{"negative number", -5, 5},
		{"zero", 0, 0},
		{"large positive", 1000, 1000},
		{"large negative", -1000, 1000},
		{"minimum int32", -2147483648, 2147483648},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := absInt(tt.input)
			assert.Equal(t, tt.expected, result)
		})
	}
}
