package ticker

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestFormatCurrency_EUR(t *testing.T) {
	tests := []struct {
		name     string
		amount   float64
		currency string
		expected string
	}{
		{
			name:     "positive EUR with thousands",
			amount:   1234.56,
			currency: "EUR",
			expected: "€1,234",
		},
		{
			name:     "positive EUR without thousands",
			amount:   567.89,
			currency: "EUR",
			expected: "€567",
		},
		{
			name:     "zero EUR",
			amount:   0,
			currency: "EUR",
			expected: "€0",
		},
		{
			name:     "negative EUR",
			amount:   -500.0,
			currency: "EUR",
			expected: "-€500",
		},
		{
			name:     "large EUR with millions",
			amount:   1234567.89,
			currency: "EUR",
			expected: "€1,234,567",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := formatCurrency(tt.amount, tt.currency)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestFormatCurrency_USD(t *testing.T) {
	tests := []struct {
		name     string
		amount   float64
		currency string
		expected string
	}{
		{
			name:     "positive USD with thousands",
			amount:   1234.56,
			currency: "USD",
			expected: "$1,234",
		},
		{
			name:     "negative USD",
			amount:   -1000.0,
			currency: "USD",
			expected: "-$1,000",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := formatCurrency(tt.amount, tt.currency)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestFormatCurrency_RUB(t *testing.T) {
	tests := []struct {
		name     string
		amount   float64
		currency string
		expected string
	}{
		{
			name:     "positive RUB with thousands",
			amount:   12345.67,
			currency: "RUB",
			expected: "₽12,345",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := formatCurrency(tt.amount, tt.currency)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestFormatCurrency_Truncation(t *testing.T) {
	tests := []struct {
		name     string
		amount   float64
		currency string
		expected string
	}{
		{
			name:     "truncates at 0.5",
			amount:   123.5,
			currency: "EUR",
			expected: "€123",
		},
		{
			name:     "truncates below 0.5",
			amount:   123.4,
			currency: "EUR",
			expected: "€123",
		},
		{
			name:     "truncates above 0.5",
			amount:   123.6,
			currency: "EUR",
			expected: "€123",
		},
		{
			name:     "negative truncates correctly",
			amount:   -123.5,
			currency: "EUR",
			expected: "-€123",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := formatCurrency(tt.amount, tt.currency)
			assert.Equal(t, tt.expected, result)
		})
	}
}
