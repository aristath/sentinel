package tradernet

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestValidateAndInterpolateCandles_OHLCConsistency(t *testing.T) {
	candles := []OHLCV{
		{Timestamp: 1000, Open: 50.0, High: 55.0, Low: 48.0, Close: 52.0, Volume: 1000},
		{Timestamp: 2000, Open: 50.0, High: 45.0, Low: 48.0, Close: 52.0, Volume: 2000}, // Invalid: High < Low
		{Timestamp: 3000, Open: 50.0, High: 55.0, Low: 48.0, Close: 52.0, Volume: 3000},
	}

	result := validateAndInterpolateCandles(candles)

	assert.Len(t, result, 3, "should return same number of candles")
	// Middle candle should be interpolated
	assert.GreaterOrEqual(t, result[1].High, result[1].Low, "interpolated candle should have valid OHLC")
	assert.GreaterOrEqual(t, result[1].High, result[1].Open, "interpolated candle should have valid OHLC")
	assert.GreaterOrEqual(t, result[1].High, result[1].Close, "interpolated candle should have valid OHLC")
	assert.Equal(t, int64(2000), result[1].Volume, "volume should be preserved")
}

func TestValidateAndInterpolateCandles_AbsoluteBounds(t *testing.T) {
	candles := []OHLCV{
		{Timestamp: 1000, Open: 50.0, High: 55.0, Low: 48.0, Close: 50.0, Volume: 1000},
		{Timestamp: 2000, Open: 15000.0, High: 15100.0, Low: 14900.0, Close: 15000.0, Volume: 2000}, // Invalid: >10000
		{Timestamp: 3000, Open: 50.0, High: 55.0, Low: 48.0, Close: 52.0, Volume: 3000},
	}

	result := validateAndInterpolateCandles(candles)

	assert.Len(t, result, 3, "should return same number of candles")
	// Middle candle should be interpolated
	assert.LessOrEqual(t, result[1].Close, 10000.0, "interpolated close should be within bounds")
	assert.GreaterOrEqual(t, result[1].Close, 0.01, "interpolated close should be within bounds")
}

func TestValidateAndInterpolateCandles_SpikeDetection(t *testing.T) {
	candles := []OHLCV{
		{Timestamp: 1000, Open: 50.0, High: 55.0, Low: 48.0, Close: 50.0, Volume: 1000},
		{Timestamp: 2000, Open: 600.0, High: 610.0, Low: 590.0, Close: 600.0, Volume: 2000}, // 1100% spike
		{Timestamp: 3000, Open: 52.0, High: 55.0, Low: 48.0, Close: 52.0, Volume: 3000},     // Normal
	}

	result := validateAndInterpolateCandles(candles)

	assert.Len(t, result, 3, "should return same number of candles")
	// Middle candle should be interpolated (spike detected, next is normal)
	assert.InDelta(t, 51.0, result[1].Close, 1.0, "interpolated close should be between 50 and 52")
}

func TestValidateAndInterpolateCandles_ValidPricesPassThrough(t *testing.T) {
	candles := []OHLCV{
		{Timestamp: 1000, Open: 50.0, High: 55.0, Low: 48.0, Close: 52.0, Volume: 1000},
		{Timestamp: 2000, Open: 51.0, High: 56.0, Low: 49.0, Close: 53.0, Volume: 2000},
		{Timestamp: 3000, Open: 52.0, High: 57.0, Low: 50.0, Close: 54.0, Volume: 3000},
	}

	result := validateAndInterpolateCandles(candles)

	assert.Equal(t, candles, result, "valid prices should pass through unchanged")
}

func TestInterpolateOHLCV_Linear(t *testing.T) {
	allCandles := []OHLCV{
		{Timestamp: 1000, Open: 47.0, High: 48.0, Low: 46.0, Close: 47.0, Volume: 1000},
		{Timestamp: 2000, Open: 0, High: 0, Low: 0, Close: 0, Volume: 2000}, // To be interpolated
		{Timestamp: 3000, Open: 46.7, High: 47.3, Low: 46.6, Close: 46.7, Volume: 3000},
	}

	candle := allCandles[1]
	result := interpolateOHLCV(candle, 1, allCandles)

	// Should interpolate between 47.0 and 46.7
	assert.InDelta(t, 46.85, result.Close, 0.1, "should interpolate close price")
	assert.GreaterOrEqual(t, result.High, result.Close, "high should be >= close")
	assert.LessOrEqual(t, result.Low, result.Close, "low should be <= close")
	assert.Equal(t, int64(2000), result.Volume, "volume should be preserved")
}

func TestInterpolateOHLCV_ForwardFill(t *testing.T) {
	allCandles := []OHLCV{
		{Timestamp: 1000, Open: 47.0, High: 48.0, Low: 46.0, Close: 47.0, Volume: 1000},
		{Timestamp: 2000, Open: 0, High: 0, Low: 0, Close: 0, Volume: 2000}, // To be interpolated
	}

	candle := allCandles[1]
	result := interpolateOHLCV(candle, 1, allCandles)

	// Should use before price (forward fill)
	assert.Equal(t, 47.0, result.Close, "should forward fill from before")
	assert.Equal(t, 47.0, result.Open, "should forward fill from before")
	assert.Equal(t, int64(2000), result.Volume, "volume should be preserved")
}

func TestInterpolateOHLCV_BackwardFill(t *testing.T) {
	allCandles := []OHLCV{
		{Timestamp: 1000, Open: 0, High: 0, Low: 0, Close: 0, Volume: 1000}, // To be interpolated
		{Timestamp: 2000, Open: 46.7, High: 47.3, Low: 46.6, Close: 46.7, Volume: 2000},
	}

	candle := allCandles[0]
	result := interpolateOHLCV(candle, 0, allCandles)

	// Should use after price (backward fill)
	assert.Equal(t, 46.7, result.Close, "should backward fill from after")
	assert.Equal(t, 46.7, result.Open, "should backward fill from after")
	assert.Equal(t, int64(1000), result.Volume, "volume should be preserved")
}
