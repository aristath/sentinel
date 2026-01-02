package formulas

import (
	"github.com/markcheno/go-talib"
)

// CalculateRSI calculates the Relative Strength Index
// Faithful translation from Python: app/modules/scoring/domain/calculations/rsi.py
//
// RSI Formula:
//   RSI = 100 - (100 / (1 + RS))
//   where RS = Average Gain / Average Loss over N periods
//
// Args:
//   closes: Array of closing prices
//   length: RSI period (typically 14)
//
// Returns:
//   Current RSI value (0-100) or nil if insufficient data
func CalculateRSI(closes []float64, length int) *float64 {
	if len(closes) < length+1 {
		return nil
	}

	// Use go-talib for RSI calculation
	rsi := talib.Rsi(closes, length)

	// Return the last value
	if len(rsi) > 0 && !isNaN(rsi[len(rsi)-1]) {
		result := rsi[len(rsi)-1]
		return &result
	}

	return nil
}

// isNaN checks if a float64 is NaN
func isNaN(f float64) bool {
	return f != f
}
