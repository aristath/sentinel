package cash_utils

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestMakeCashSymbol(t *testing.T) {
	tests := []struct {
		name        string
		currency    string
		bucketID    string
		want        string
		description string
	}{
		{
			name:        "EUR core bucket",
			currency:    "EUR",
			bucketID:    "core",
			want:        "CASH:EUR:core",
			description: "Standard EUR cash symbol for core bucket",
		},
		{
			name:        "USD satellite bucket",
			currency:    "USD",
			bucketID:    "satellite1",
			want:        "CASH:USD:satellite1",
			description: "USD cash symbol for satellite bucket",
		},
		{
			name:        "currency is uppercased",
			currency:    "eur",
			bucketID:    "core",
			want:        "CASH:EUR:core",
			description: "Currency should be converted to uppercase",
		},
		{
			name:        "mixed case currency",
			currency:    "UsD",
			bucketID:    "satellite",
			want:        "CASH:USD:satellite",
			description: "Mixed case currency should be uppercased",
		},
		{
			name:        "bucket ID preserved as-is",
			currency:    "EUR",
			bucketID:    "SatelliteBucket",
			want:        "CASH:EUR:SatelliteBucket",
			description: "Bucket ID should be preserved exactly as provided",
		},
		{
			name:        "GBP currency",
			currency:    "GBP",
			bucketID:    "core",
			want:        "CASH:GBP:core",
			description: "GBP currency support",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := MakeCashSymbol(tt.currency, tt.bucketID)
			assert.Equal(t, tt.want, got, tt.description)
		})
	}
}

func TestIsCashSymbol(t *testing.T) {
	tests := []struct {
		name        string
		symbol      string
		want        bool
		description string
	}{
		{
			name:        "valid EUR cash symbol",
			symbol:      "CASH:EUR:core",
			want:        true,
			description: "Valid cash symbol should return true",
		},
		{
			name:        "valid USD cash symbol",
			symbol:      "CASH:USD:satellite1",
			want:        true,
			description: "Valid USD cash symbol should return true",
		},
		{
			name:        "regular stock symbol",
			symbol:      "AAPL",
			want:        false,
			description: "Regular stock symbol should return false",
		},
		{
			name:        "symbol starting with CASH but not cash",
			symbol:      "CASHIER",
			want:        false,
			description: "Symbol starting with CASH but not prefix should return false",
		},
		{
			name:        "empty string",
			symbol:      "",
			want:        false,
			description: "Empty string should return false",
		},
		{
			name:        "cash lowercase prefix",
			symbol:      "cash:EUR:core",
			want:        false,
			description: "Lowercase prefix should return false (must be uppercase CASH:)",
		},
		{
			name:        "symbol containing CASH: but not at start",
			symbol:      "SYMBOL:CASH:EUR",
			want:        false,
			description: "CASH: must be at the start of the symbol",
		},
		{
			name:        "just CASH: prefix",
			symbol:      "CASH:",
			want:        true,
			description: "CASH: prefix alone should return true (format validation happens in ParseCashSymbol)",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := IsCashSymbol(tt.symbol)
			assert.Equal(t, tt.want, got, tt.description)
		})
	}
}

func TestParseCashSymbol(t *testing.T) {
	tests := []struct {
		name         string
		symbol       string
		wantCurrency string
		wantBucketID string
		wantErr      bool
		errContains  string
		description  string
	}{
		{
			name:         "valid EUR core symbol",
			symbol:       "CASH:EUR:core",
			wantCurrency: "EUR",
			wantBucketID: "core",
			wantErr:      false,
			description:  "Valid cash symbol should parse correctly",
		},
		{
			name:         "valid USD satellite symbol",
			symbol:       "CASH:USD:satellite1",
			wantCurrency: "USD",
			wantBucketID: "satellite1",
			wantErr:      false,
			description:  "Valid USD satellite symbol should parse correctly",
		},
		{
			name:         "symbol with complex bucket ID",
			symbol:       "CASH:GBP:satellite-2-bucket",
			wantCurrency: "GBP",
			wantBucketID: "satellite-2-bucket",
			wantErr:      false,
			description:  "Bucket ID with hyphens should be preserved",
		},
		{
			name:         "not a cash symbol",
			symbol:       "AAPL",
			wantCurrency: "",
			wantBucketID: "",
			wantErr:      true,
			errContains:  "not a cash symbol",
			description:  "Non-cash symbol should return error",
		},
		{
			name:         "invalid format - too few parts",
			symbol:       "CASH:EUR",
			wantCurrency: "",
			wantBucketID: "",
			wantErr:      true,
			errContains:  "invalid cash symbol format",
			description:  "Symbol with only 2 parts should return format error",
		},
		{
			name:         "invalid format - too many parts",
			symbol:       "CASH:EUR:core:extra",
			wantCurrency: "",
			wantBucketID: "",
			wantErr:      true,
			errContains:  "invalid cash symbol format",
			description:  "Symbol with 4 parts should return format error",
		},
		{
			name:         "empty currency",
			symbol:       "CASH::core",
			wantCurrency: "",
			wantBucketID: "",
			wantErr:      true,
			errContains:  "empty currency",
			description:  "Empty currency should return error",
		},
		{
			name:         "empty bucket ID",
			symbol:       "CASH:EUR:",
			wantCurrency: "",
			wantBucketID: "",
			wantErr:      true,
			errContains:  "empty bucket ID",
			description:  "Empty bucket ID should return error",
		},
		{
			name:         "empty string",
			symbol:       "",
			wantCurrency: "",
			wantBucketID: "",
			wantErr:      true,
			errContains:  "not a cash symbol",
			description:  "Empty string should return error",
		},
		{
			name:         "currency with spaces",
			symbol:       "CASH:EUR :core",
			wantCurrency: "EUR ",
			wantBucketID: "core",
			wantErr:      false,
			description:  "Currency with trailing space should be parsed (may want to trim in future)",
		},
		{
			name:         "bucket ID with spaces",
			symbol:       "CASH:EUR: core",
			wantCurrency: "EUR",
			wantBucketID: " core",
			wantErr:      false,
			description:  "Bucket ID with leading space should be parsed",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gotCurrency, gotBucketID, err := ParseCashSymbol(tt.symbol)

			if tt.wantErr {
				assert.Error(t, err, tt.description)
				if tt.errContains != "" {
					assert.Contains(t, err.Error(), tt.errContains, "Error message should contain expected text")
				}
				assert.Empty(t, gotCurrency, "Currency should be empty on error")
				assert.Empty(t, gotBucketID, "Bucket ID should be empty on error")
			} else {
				assert.NoError(t, err, tt.description)
				assert.Equal(t, tt.wantCurrency, gotCurrency, "Currency mismatch: %s", tt.description)
				assert.Equal(t, tt.wantBucketID, gotBucketID, "Bucket ID mismatch: %s", tt.description)
			}
		})
	}
}

func TestParseCashSymbol_RoundTrip(t *testing.T) {
	// Test that MakeCashSymbol and ParseCashSymbol are inverse operations
	tests := []struct {
		name     string
		currency string
		bucketID string
	}{
		{"EUR core", "EUR", "core"},
		{"USD satellite1", "USD", "satellite1"},
		{"GBP satellite-2", "GBP", "satellite-2"},
		{"EUR complex-bucket-id", "EUR", "complex-bucket-id"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			symbol := MakeCashSymbol(tt.currency, tt.bucketID)
			parsedCurrency, parsedBucketID, err := ParseCashSymbol(symbol)

			assert.NoError(t, err, "Round-trip parsing should not error")
			assert.Equal(t, tt.currency, parsedCurrency, "Currency should match after round-trip")
			assert.Equal(t, tt.bucketID, parsedBucketID, "Bucket ID should match after round-trip")
		})
	}
}

func TestGetCashSecurityName(t *testing.T) {
	tests := []struct {
		name        string
		currency    string
		bucketName  string
		want        string
		description string
	}{
		{
			name:        "EUR core bucket",
			currency:    "EUR",
			bucketName:  "core",
			want:        "Cash (EUR - core)",
			description: "Standard format for EUR core",
		},
		{
			name:        "USD satellite bucket",
			currency:    "USD",
			bucketName:  "Satellite 1",
			want:        "Cash (USD - Satellite 1)",
			description: "USD with formatted bucket name",
		},
		{
			name:        "currency is uppercased",
			currency:    "eur",
			bucketName:  "core",
			want:        "Cash (EUR - core)",
			description: "Currency should be converted to uppercase",
		},
		{
			name:        "mixed case currency",
			currency:    "UsD",
			bucketName:  "satellite",
			want:        "Cash (USD - satellite)",
			description: "Mixed case currency should be uppercased",
		},
		{
			name:        "bucket name preserved as-is",
			currency:    "GBP",
			bucketName:  "My Satellite Bucket",
			want:        "Cash (GBP - My Satellite Bucket)",
			description: "Bucket name should be preserved exactly",
		},
		{
			name:        "GBP currency",
			currency:    "GBP",
			bucketName:  "core",
			want:        "Cash (GBP - core)",
			description: "GBP currency support",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := GetCashSecurityName(tt.currency, tt.bucketName)
			assert.Equal(t, tt.want, got, tt.description)
		})
	}
}
