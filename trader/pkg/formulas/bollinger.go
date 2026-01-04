package formulas

import (
	"github.com/markcheno/go-talib"
)

// BollingerBands represents Bollinger Bands values
type BollingerBands struct {
	Upper  float64 `json:"upper"`
	Middle float64 `json:"middle"`
	Lower  float64 `json:"lower"`
}

// BollingerPosition represents where price is relative to Bollinger Bands
// Range: 0.0 (at lower band) to 1.0 (at upper band)
type BollingerPosition struct {
	Position float64        `json:"position"` // 0.0 to 1.0
	Bands    BollingerBands `json:"bands"`
}

// CalculateBollingerBands calculates Bollinger Bands
// Faithful translation from Python: app/modules/scoring/domain/calculations/bollinger.py
//
// Bollinger Bands Formula:
//
//	Middle Band = 20-day SMA
//	Upper Band = Middle + (2 × std deviation)
//	Lower Band = Middle - (2 × std deviation)
//
// Args:
//
//	closes: Array of closing prices
//	length: Period for moving average (typically 20)
//	stdDevMultiplier: Standard deviation multiplier (typically 2)
//
// Returns:
//
//	BollingerBands struct or nil if insufficient data
func CalculateBollingerBands(closes []float64, length int, stdDevMultiplier float64) *BollingerBands {
	if len(closes) < length {
		return nil
	}

	// Use go-talib for Bollinger Bands calculation
	// Parameters: inReal, inTimePeriod, inNbDevUp, inNbDevDn, inMAType
	// MAType 0 = SMA (Simple Moving Average)
	upper, middle, lower := talib.BBands(closes, length, stdDevMultiplier, stdDevMultiplier, 0)

	// Return the last values
	if len(upper) > 0 && !isNaN(upper[len(upper)-1]) {
		return &BollingerBands{
			Upper:  upper[len(upper)-1],
			Middle: middle[len(middle)-1],
			Lower:  lower[len(lower)-1],
		}
	}

	return nil
}

// CalculateBollingerPosition calculates where current price is within the Bollinger Bands
// Returns 0.0 if at lower band, 0.5 if at middle, 1.0 if at upper band
//
// Formula: (Price - Lower) / (Upper - Lower)
func CalculateBollingerPosition(closes []float64, length int, stdDevMultiplier float64) *BollingerPosition {
	if len(closes) == 0 {
		return nil
	}

	bands := CalculateBollingerBands(closes, length, stdDevMultiplier)
	if bands == nil {
		return nil
	}

	currentPrice := closes[len(closes)-1]
	bandWidth := bands.Upper - bands.Lower

	if bandWidth == 0 {
		// Bands are collapsed, price is at middle
		return &BollingerPosition{
			Position: 0.5,
			Bands:    *bands,
		}
	}

	// Calculate position within bands (0.0 = lower, 1.0 = upper)
	position := (currentPrice - bands.Lower) / bandWidth

	// Clamp to 0.0 - 1.0 range (price can be outside bands)
	if position < 0.0 {
		position = 0.0
	}
	if position > 1.0 {
		position = 1.0
	}

	return &BollingerPosition{
		Position: position,
		Bands:    *bands,
	}
}
