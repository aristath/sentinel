package yahoo

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestNewNativeClient(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	client := NewNativeClient(log)

	assert.NotNil(t, client)
	assert.NotNil(t, client.log)
}

func TestNativeClient_ImplementsFullClientInterface(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	client := NewNativeClient(log)

	// Ensure NativeClient implements FullClientInterface
	var _ FullClientInterface = client
}

func TestIsISIN(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected bool
	}{
		{
			name:     "valid ISIN",
			input:    "US0378331005",
			expected: true,
		},
		{
			name:     "valid ISIN with lowercase",
			input:    "us0378331005",
			expected: true,
		},
		{
			name:     "valid ISIN with spaces",
			input:    " US0378331005 ",
			expected: true,
		},
		{
			name:     "invalid - too short",
			input:    "US037833100",
			expected: false,
		},
		{
			name:     "invalid - too long",
			input:    "US03783310055",
			expected: false,
		},
		{
			name:     "invalid - wrong first two chars",
			input:    "123456789012",
			expected: false,
		},
		{
			name:     "invalid - wrong last char",
			input:    "US037833100A",
			expected: false,
		},
		{
			name:     "empty string",
			input:    "",
			expected: false,
		},
		{
			name:     "another valid ISIN",
			input:    "GB0002875804",
			expected: true,
		},
		{
			name:     "invalid - special characters",
			input:    "US037833-005",
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := isISIN(tt.input)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestTradernetToYahoo(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{
			name:     "US security - strips .US",
			input:    "AAPL.US",
			expected: "AAPL",
		},
		{
			name:     "US security lowercase",
			input:    "aapl.us",
			expected: "AAPL",
		},
		{
			name:     "Japanese security - converts .JP to .T",
			input:    "7203.JP",
			expected: "7203.T",
		},
		{
			name:     "Japanese security lowercase",
			input:    "7203.jp",
			expected: "7203.T",
		},
		{
			name:     "Greek security - converts .GR to .AT",
			input:    "TITK.GR",
			expected: "TITK.AT",
		},
		{
			name:     "Greek security lowercase",
			input:    "titk.gr",
			expected: "TITK.AT",
		},
		{
			name:     "other suffix - passes through",
			input:    "SAP.DE",
			expected: "SAP.DE",
		},
		{
			name:     "no suffix - passes through",
			input:    "AAPL",
			expected: "AAPL",
		},
		{
			name:     "lowercase no suffix - uppercased",
			input:    "aapl",
			expected: "AAPL",
		},
		{
			name:     "mixed case",
			input:    "ApPl.Us",
			expected: "APPL",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := tradernetToYahoo(tt.input)
			assert.Equal(t, tt.expected, result)
		})
	}
}
