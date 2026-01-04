package formulas

import (
	"github.com/markcheno/go-talib"
)

// CalculateEMA calculates the Exponential Moving Average
// Faithful translation from Python: app/modules/scoring/domain/calculations/ema.py
//
// EMA Formula:
//
//	EMA_today = (Price_today × multiplier) + (EMA_yesterday × (1 - multiplier))
//	where multiplier = 2 / (period + 1)
//
// Args:
//
//	closes: Array of closing prices
//	length: EMA period (typically 200)
//
// Returns:
//
//	Current EMA value or nil if insufficient data
func CalculateEMA(closes []float64, length int) *float64 {
	if len(closes) == 0 {
		return nil
	}

	// If not enough data for proper EMA, fallback to SMA
	if len(closes) < length {
		sma := Mean(closes)
		return &sma
	}

	// Use go-talib for EMA calculation
	ema := talib.Ema(closes, length)

	// Return the last value
	if len(ema) > 0 && !isNaN(ema[len(ema)-1]) {
		result := ema[len(ema)-1]
		return &result
	}

	// Fallback to SMA of last 'length' prices
	sma := Mean(closes[len(closes)-length:])
	return &sma
}

// CalculateSMA calculates the Simple Moving Average
// This is a helper function that can be used independently
func CalculateSMA(closes []float64, length int) *float64 {
	if len(closes) < length {
		return nil
	}

	sma := talib.Sma(closes, length)
	if len(sma) > 0 && !isNaN(sma[len(sma)-1]) {
		result := sma[len(sma)-1]
		return &result
	}

	return nil
}

// CalculateDistanceFromEMA calculates the percentage distance from EMA
// Returns positive if price is above EMA, negative if below
//
// Formula: (Current Price - EMA) / EMA
func CalculateDistanceFromEMA(closes []float64, length int) *float64 {
	if len(closes) == 0 {
		return nil
	}

	ema := CalculateEMA(closes, length)
	if ema == nil {
		return nil
	}

	currentPrice := closes[len(closes)-1]
	if *ema == 0 {
		return nil
	}

	distance := (currentPrice - *ema) / *ema
	return &distance
}
