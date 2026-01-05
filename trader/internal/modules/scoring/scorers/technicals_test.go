package scorers

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestTechnicalsScorer_StoresRawRSIAndEMA(t *testing.T) {
	scorer := NewTechnicalsScorer()

	// Create daily prices that will produce RSI and EMA values
	dailyPrices := make([]float64, 250) // Enough for 200-day EMA
	basePrice := 100.0
	for i := range dailyPrices {
		// Simulate price movement with some volatility
		if i%10 < 5 {
			// Upward movement
			dailyPrices[i] = basePrice + float64(i)*0.2 + float64(i%5)*0.3
		} else {
			// Downward movement
			dailyPrices[i] = basePrice + float64(i)*0.2 - float64(i%5)*0.2
		}
	}

	result := scorer.Calculate(dailyPrices)

	// Verify raw RSI is stored
	assert.Contains(t, result.Components, "rsi_raw", "Components should contain rsi_raw")

	// Verify raw EMA is stored
	assert.Contains(t, result.Components, "ema_raw", "Components should contain ema_raw")

	// Verify scored values are still present
	assert.Contains(t, result.Components, "rsi", "Components should contain scored rsi")
	assert.Contains(t, result.Components, "ema", "Components should contain scored ema")

	// Verify raw RSI is between 0 and 100
	rawRSI := result.Components["rsi_raw"]
	assert.GreaterOrEqual(t, rawRSI, 0.0, "Raw RSI should be >= 0")
	assert.LessOrEqual(t, rawRSI, 100.0, "Raw RSI should be <= 100")

	// Verify raw EMA is a positive price value
	rawEMA := result.Components["ema_raw"]
	assert.Greater(t, rawEMA, 0.0, "Raw EMA should be a positive price value")

	// Verify scored values are between 0 and 1
	scoredRSI := result.Components["rsi"]
	assert.GreaterOrEqual(t, scoredRSI, 0.0, "Scored RSI should be >= 0")
	assert.LessOrEqual(t, scoredRSI, 1.0, "Scored RSI should be <= 1")

	scoredEMA := result.Components["ema"]
	assert.GreaterOrEqual(t, scoredEMA, 0.0, "Scored EMA should be >= 0")
	assert.LessOrEqual(t, scoredEMA, 1.0, "Scored EMA should be <= 1")
}

func TestTechnicalsScorer_StoresRawRSIAndEMA_WithInsufficientData(t *testing.T) {
	scorer := NewTechnicalsScorer()

	// Create insufficient daily prices (less than 20)
	dailyPrices := make([]float64, 10)
	for i := range dailyPrices {
		dailyPrices[i] = 100.0 + float64(i)*0.1
	}

	result := scorer.Calculate(dailyPrices)

	// When data is insufficient, raw values should be 0.0
	if rawRSI, exists := result.Components["rsi_raw"]; exists {
		assert.Equal(t, 0.0, rawRSI, "Raw RSI should be 0.0 when calculation fails")
	}
	if rawEMA, exists := result.Components["ema_raw"]; exists {
		assert.Equal(t, 0.0, rawEMA, "Raw EMA should be 0.0 when calculation fails")
	}
}
