package charts

import (
	"testing"
	"time"
)

func TestParseDateRange(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		wantDays int // Expected days before now (approximate)
	}{
		{
			name:     "1 month",
			input:    "1M",
			wantDays: 30,
		},
		{
			name:     "3 months",
			input:    "3M",
			wantDays: 90,
		},
		{
			name:     "6 months",
			input:    "6M",
			wantDays: 180,
		},
		{
			name:     "1 year",
			input:    "1Y",
			wantDays: 365,
		},
		{
			name:     "5 years",
			input:    "5Y",
			wantDays: 365 * 5,
		},
		{
			name:     "10 years",
			input:    "10Y",
			wantDays: 365 * 10,
		},
		{
			name:     "all time - empty string",
			input:    "all",
			wantDays: -1, // Empty result
		},
		{
			name:     "empty string",
			input:    "",
			wantDays: -1, // Empty result
		},
		{
			name:     "invalid range",
			input:    "invalid",
			wantDays: -1, // Empty result
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := parseDateRange(tt.input)

			if tt.wantDays == -1 {
				// Expect empty string
				if result != "" {
					t.Errorf("parseDateRange(%q) = %q, want empty string", tt.input, result)
				}
				return
			}

			// Parse result date
			if result == "" {
				t.Errorf("parseDateRange(%q) returned empty string, expected date", tt.input)
				return
			}

			resultDate, err := time.Parse("2006-01-02", result)
			if err != nil {
				t.Errorf("parseDateRange(%q) returned invalid date format: %q", tt.input, result)
				return
			}

			// Check that date is approximately correct
			// Use wider tolerance for month-based ranges (due to varying month lengths)
			tolerance := 5.0 // 5 day tolerance for month-based calculations
			expectedDate := time.Now().AddDate(0, 0, -tt.wantDays)
			daysDiff := resultDate.Sub(expectedDate).Hours() / 24

			if daysDiff < -tolerance || daysDiff > tolerance {
				t.Errorf("parseDateRange(%q) = %q, expected ~%d days ago, got %.0f days difference",
					tt.input, result, tt.wantDays, daysDiff)
			}
		})
	}
}

func TestIsValidISIN(t *testing.T) {
	tests := []struct {
		name  string
		isin  string
		valid bool
	}{
		{
			name:  "valid US ISIN",
			isin:  "US0378331005",
			valid: true,
		},
		{
			name:  "valid IE ISIN",
			isin:  "IE00B4BNMY34",
			valid: true,
		},
		{
			name:  "valid GR ISIN",
			isin:  "GRS323003012",
			valid: true,
		},
		{
			name:  "too short",
			isin:  "US037833100",
			valid: false,
		},
		{
			name:  "too long",
			isin:  "US03783310055",
			valid: false,
		},
		{
			name:  "no country code",
			isin:  "120378331005",
			valid: false,
		},
		{
			name:  "no check digit",
			isin:  "US037833100A",
			valid: false,
		},
		{
			name:  "empty string",
			isin:  "",
			valid: false,
		},
		{
			name:  "special characters",
			isin:  "US0378331@05",
			valid: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := isValidISIN(tt.isin)
			if result != tt.valid {
				t.Errorf("isValidISIN(%q) = %v, want %v", tt.isin, result, tt.valid)
			}
		})
	}
}

func TestIsLetter(t *testing.T) {
	tests := []struct {
		name     string
		char     byte
		expected bool
	}{
		{"uppercase A", 'A', true},
		{"uppercase Z", 'Z', true},
		{"uppercase M", 'M', true},
		{"lowercase a", 'a', true},
		{"lowercase z", 'z', true},
		{"lowercase m", 'm', true},
		{"digit 0", '0', false},
		{"digit 9", '9', false},
		{"digit 5", '5', false},
		{"special @", '@', false},
		{"special #", '#', false},
		{"space", ' ', false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := isLetter(tt.char)
			if result != tt.expected {
				t.Errorf("isLetter(%q) = %v, want %v", tt.char, result, tt.expected)
			}
		})
	}
}

func TestIsDigit(t *testing.T) {
	tests := []struct {
		name     string
		char     byte
		expected bool
	}{
		{"digit 0", '0', true},
		{"digit 9", '9', true},
		{"digit 5", '5', true},
		{"uppercase A", 'A', false},
		{"uppercase Z", 'Z', false},
		{"lowercase a", 'a', false},
		{"lowercase z", 'z', false},
		{"special @", '@', false},
		{"special #", '#', false},
		{"space", ' ', false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := isDigit(tt.char)
			if result != tt.expected {
				t.Errorf("isDigit(%q) = %v, want %v", tt.char, result, tt.expected)
			}
		})
	}
}

func TestIsAlphanumeric(t *testing.T) {
	tests := []struct {
		name     string
		char     byte
		expected bool
	}{
		{"uppercase A", 'A', true},
		{"uppercase Z", 'Z', true},
		{"lowercase a", 'a', true},
		{"lowercase z", 'z', true},
		{"digit 0", '0', true},
		{"digit 9", '9', true},
		{"digit 5", '5', true},
		{"special @", '@', false},
		{"special #", '#', false},
		{"space", ' ', false},
		{"underscore", '_', false},
		{"hyphen", '-', false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := isAlphanumeric(tt.char)
			if result != tt.expected {
				t.Errorf("isAlphanumeric(%q) = %v, want %v", tt.char, result, tt.expected)
			}
		})
	}
}
