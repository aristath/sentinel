package cash_utils

import (
	"fmt"
	"strings"
)

// MakeCashSymbol creates synthetic symbol for cash position
// Format: "CASH:{CURRENCY}:{bucket_id}"
// Examples: "CASH:EUR:core", "CASH:USD:satellite1"
func MakeCashSymbol(currency string, bucketID string) string {
	return fmt.Sprintf("CASH:%s:%s", strings.ToUpper(currency), bucketID)
}

// IsCashSymbol checks if a symbol represents a cash position
func IsCashSymbol(symbol string) bool {
	return strings.HasPrefix(symbol, "CASH:")
}

// ParseCashSymbol extracts currency and bucketID from cash symbol
// Returns (currency, bucketID, error)
// Returns error if symbol is not a valid cash symbol
func ParseCashSymbol(symbol string) (string, string, error) {
	if !IsCashSymbol(symbol) {
		return "", "", fmt.Errorf("not a cash symbol: %s", symbol)
	}

	parts := strings.Split(symbol, ":")
	if len(parts) != 3 {
		return "", "", fmt.Errorf("invalid cash symbol format: %s (expected CASH:CURRENCY:BUCKET)", symbol)
	}

	currency := parts[1]
	bucketID := parts[2]

	if currency == "" {
		return "", "", fmt.Errorf("empty currency in cash symbol: %s", symbol)
	}
	if bucketID == "" {
		return "", "", fmt.Errorf("empty bucket ID in cash symbol: %s", symbol)
	}

	return currency, bucketID, nil
}

// GetCashSecurityName generates human-readable name for cash security
// Examples: "Cash (EUR - core)", "Cash (USD - Satellite 1)"
func GetCashSecurityName(currency string, bucketName string) string {
	return fmt.Sprintf("Cash (%s - %s)", strings.ToUpper(currency), bucketName)
}
