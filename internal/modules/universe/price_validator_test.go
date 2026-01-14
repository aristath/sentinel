package universe

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestPriceValidator_ValidatePrice_OHLCConsistency(t *testing.T) {
	log := zerolog.Nop()
	validator := NewPriceValidator(log)

	tests := []struct {
		name    string
		price   DailyPrice
		context []DailyPrice
		want    bool
		reason  string
	}{
		{
			name: "valid OHLC",
			price: DailyPrice{
				Date:  "2025-01-15",
				Open:  50.0,
				High:  55.0,
				Low:   48.0,
				Close: 52.0,
			},
			context: []DailyPrice{},
			want:    true,
			reason:  "",
		},
		{
			name: "high below low",
			price: DailyPrice{
				Date:  "2025-01-15",
				Open:  50.0,
				High:  45.0, // Invalid: High < Low
				Low:   48.0,
				Close: 52.0,
			},
			context: []DailyPrice{},
			want:    false,
			reason:  "high_below_low",
		},
		{
			name: "high below open",
			price: DailyPrice{
				Date:  "2025-01-15",
				Open:  55.0,
				High:  50.0, // Invalid: High < Open
				Low:   48.0,
				Close: 52.0,
			},
			context: []DailyPrice{},
			want:    false,
			reason:  "high_below_open",
		},
		{
			name: "high below close",
			price: DailyPrice{
				Date:  "2025-01-15",
				Open:  50.0,
				High:  50.0,
				Low:   48.0,
				Close: 55.0, // Invalid: Close > High
			},
			context: []DailyPrice{},
			want:    false,
			reason:  "high_below_close",
		},
		{
			name: "low above open",
			price: DailyPrice{
				Date:  "2025-01-15",
				Open:  45.0,
				High:  55.0,
				Low:   50.0, // Invalid: Low > Open
				Close: 52.0,
			},
			context: []DailyPrice{},
			want:    false,
			reason:  "low_above_open",
		},
		{
			name: "low above close",
			price: DailyPrice{
				Date:  "2025-01-15",
				Open:  50.0,
				High:  55.0,
				Low:   52.0, // Invalid: Low > Close and Low > Open
				Close: 48.0,
			},
			context: []DailyPrice{},
			want:    false,
			reason:  "low_above_open", // First check that fails
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			valid, reason := validator.ValidatePrice(tt.price, nil, tt.context)
			assert.Equal(t, tt.want, valid, "validation result mismatch")
			if !tt.want {
				assert.Equal(t, tt.reason, reason, "reason mismatch")
			}
		})
	}
}

func TestPriceValidator_ValidatePrice_PercentageChange(t *testing.T) {
	log := zerolog.Nop()
	validator := NewPriceValidator(log)

	// Create context with normal prices around 50 EUR (newest first, as from database)
	context := []DailyPrice{
		{Date: "2025-01-14", Close: 50.0, Open: 52.0, High: 52.0, Low: 49.0}, // Most recent
		{Date: "2025-01-13", Close: 52.0, Open: 49.0, High: 53.0, Low: 48.0},
		{Date: "2025-01-12", Close: 49.0, Open: 51.0, High: 51.0, Low: 48.0},
		{Date: "2025-01-11", Close: 51.0, Open: 50.0, High: 52.0, Low: 49.0},
		{Date: "2025-01-10", Close: 50.0, Open: 49.0, High: 51.0, Low: 48.0},
	}

	tests := []struct {
		name          string
		price         DailyPrice
		previousPrice *DailyPrice
		context       []DailyPrice
		want          bool
		reason        string
	}{
		{
			name: "normal price within range",
			price: DailyPrice{
				Date:  "2025-01-15",
				Close: 51.0, // Normal: ~50 EUR
				Open:  50.0,
				High:  52.0,
				Low:   49.0,
			},
			previousPrice: &DailyPrice{Date: "2025-01-14", Close: 50.0},
			context:       context,
			want:          true,
			reason:        "",
		},
		{
			name: "price too high (10x average)",
			price: DailyPrice{
				Date:  "2025-01-15",
				Close: 550.0, // 11x average of 50 (needs to be >10x to trigger)
				Open:  550.0,
				High:  560.0,
				Low:   540.0,
			},
			context: context,
			want:    false,
			reason:  "price_too_high",
		},
		{
			name: "price too low (0.1x average)",
			price: DailyPrice{
				Date:  "2025-01-15",
				Close: 5.0, // 0.1x average of 50
				Open:  5.0,
				High:  6.0,
				Low:   4.0,
			},
			context: context,
			want:    false,
			reason:  "price_too_low",
		},
		{
			name: "spike detected (>1000% change) - uses previousPrice, not context",
			price: DailyPrice{
				Date:  "2025-01-15",
				Close: 600.0, // 1100% increase from previous day (50 -> 600)
				Open:  600.0,
				High:  610.0,
				Low:   590.0,
			},
			previousPrice: &DailyPrice{Date: "2025-01-14", Close: 50.0},
			context:       context,
			want:          false,
			reason:        "spike_detected",
		},
		{
			name: "crash detected (<-90% change) - uses previousPrice, not context",
			price: DailyPrice{
				Date:  "2025-01-15",
				Close: 4.0, // -92% decrease from previous day (50 -> 4)
				Open:  4.0,
				High:  5.0,
				Low:   3.0,
			},
			previousPrice: &DailyPrice{Date: "2025-01-14", Close: 50.0},
			context:       context,
			want:          false,
			reason:        "crash_detected",
		},
		{
			name: "LDO.EU anomaly case (44,000 vs 50) - uses previousPrice",
			price: DailyPrice{
				Date:  "2025-08-11",
				Close: 44458.62, // Abnormal: 44,458 vs normal ~50 (889x increase = spike)
				Open:  44050.53,
				High:  44497.59,
				Low:   44050.53,
			},
			previousPrice: &DailyPrice{Date: "2025-08-10", Close: 47.0},
			context:       context,
			want:          false,
			reason:        "spike_detected", // Spike detection takes priority (>1000% change)
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			valid, reason := validator.ValidatePrice(tt.price, tt.previousPrice, tt.context)
			assert.Equal(t, tt.want, valid, "validation result mismatch")
			if !tt.want {
				assert.Equal(t, tt.reason, reason, "reason mismatch")
			}
		})
	}
}

// Test that day-over-day detection uses previousPrice, not context[0]
func TestPriceValidator_ValidatePrice_DayOverDayUsesPreviousPrice(t *testing.T) {
	log := zerolog.Nop()
	validator := NewPriceValidator(log)

	// Context with future prices (simulating syncing old historical data when DB has newer data)
	context := []DailyPrice{
		{Date: "2025-12-31", Close: 100.0}, // Future price (most recent in DB)
		{Date: "2025-12-30", Close: 99.0},
	}

	// Price from 2020 being validated
	price := DailyPrice{
		Date:  "2020-01-15",
		Close: 50.0, // Normal price for 2020
		Open:  49.0,
		High:  51.0,
		Low:   48.0,
	}

	// Previous price from the array being validated (2020-01-14)
	previousPrice := &DailyPrice{
		Date:  "2020-01-14",
		Close: 49.0, // Normal day-over-day change
	}

	// Should be valid - uses previousPrice (49.0 -> 50.0 = 2% change), not context[0] (100.0)
	valid, reason := validator.ValidatePrice(price, previousPrice, context)
	assert.True(t, valid, "price should be valid when using previousPrice, not context[0]")
	assert.Empty(t, reason, "should have no reason when valid")

	// Without previousPrice, should still be valid (average-based check, not day-over-day)
	valid2, reason2 := validator.ValidatePrice(price, nil, context)
	assert.True(t, valid2, "price should be valid even without previousPrice (uses average)")
	assert.Empty(t, reason2, "should have no reason when valid")
}

func TestPriceValidator_ValidatePrice_AbsoluteBounds(t *testing.T) {
	log := zerolog.Nop()
	validator := NewPriceValidator(log)

	tests := []struct {
		name    string
		price   DailyPrice
		context []DailyPrice
		want    bool
		reason  string
	}{
		{
			name: "normal price without context",
			price: DailyPrice{
				Date:  "2025-01-15",
				Close: 50.0,
				Open:  49.0,
				High:  51.0,
				Low:   48.0,
			},
			context: []DailyPrice{}, // No context
			want:    true,
			reason:  "",
		},
		{
			name: "absolute bound exceeded (>10,000)",
			price: DailyPrice{
				Date:  "2025-01-15",
				Close: 15000.0, // > 10,000
				Open:  15000.0,
				High:  15100.0,
				Low:   14900.0,
			},
			context: []DailyPrice{}, // No context
			want:    false,
			reason:  "absolute_bound_exceeded",
		},
		{
			name: "absolute bound below minimum (<0.01)",
			price: DailyPrice{
				Date:  "2025-01-15",
				Close: 0.005, // < 0.01
				Open:  0.005,
				High:  0.006,
				Low:   0.004,
			},
			context: []DailyPrice{}, // No context
			want:    false,
			reason:  "absolute_bound_below_minimum",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			valid, reason := validator.ValidatePrice(tt.price, nil, tt.context)
			assert.Equal(t, tt.want, valid, "validation result mismatch")
			if !tt.want {
				assert.Equal(t, tt.reason, reason, "reason mismatch")
			}
		})
	}
}

func TestPriceValidator_InterpolatePrice_Linear(t *testing.T) {
	log := zerolog.Nop()
	validator := NewPriceValidator(log)

	before := []DailyPrice{
		{Date: "2025-08-09", Close: 47.0, Open: 46.0, High: 48.0, Low: 45.0},
	}
	after := []DailyPrice{
		{Date: "2025-08-12", Close: 46.7, Open: 47.2, High: 47.3, Low: 46.6},
	}

	// Price to interpolate (abnormal)
	price := DailyPrice{
		Date:   "2025-08-11",
		Close:  44458.62, // Abnormal
		Open:   44050.53,
		High:   44497.59,
		Low:    44050.53,
		Volume: intPtrForPriceValidator(1285994),
	}

	interpolated, method, err := validator.InterpolatePrice(price, before, after)
	require.NoError(t, err)
	assert.Equal(t, "linear", method)

	// Should interpolate between 47.0 and 46.7
	// Days: 2025-08-09 to 2025-08-11 = 2 days, total = 3 days
	// Expected close: 47.0 + (46.7 - 47.0) * (2/3) = 47.0 - 0.2 = 46.8
	expectedClose := 47.0 + (46.7-47.0)*(2.0/3.0)
	assert.InDelta(t, expectedClose, interpolated.Close, 0.1, "interpolated close price")

	// Open/High/Low should maintain ratios
	assert.Greater(t, interpolated.High, interpolated.Close, "high should be >= close")
	assert.Less(t, interpolated.Low, interpolated.Close, "low should be <= close")
	assert.Greater(t, interpolated.High, interpolated.Low, "high should be >= low")

	// Volume should be preserved
	assert.Equal(t, int64(1285994), *interpolated.Volume, "volume should be preserved")
}

func TestPriceValidator_InterpolatePrice_ForwardFill(t *testing.T) {
	log := zerolog.Nop()
	validator := NewPriceValidator(log)

	before := []DailyPrice{
		{Date: "2025-08-10", Close: 47.0, Open: 46.0, High: 48.0, Low: 45.0},
	}
	after := []DailyPrice{} // No after prices

	price := DailyPrice{
		Date:   "2025-08-11",
		Close:  44458.62, // Abnormal
		Open:   44050.53,
		High:   44497.59,
		Low:    44050.53,
		Volume: intPtrForPriceValidator(1285994),
	}

	interpolated, method, err := validator.InterpolatePrice(price, before, after)
	require.NoError(t, err)
	assert.Equal(t, "forward_fill", method)

	// Should use before price directly
	assert.Equal(t, 47.0, interpolated.Close, "close should match before")
	assert.Equal(t, 46.0, interpolated.Open, "open should match before")
	assert.Equal(t, 48.0, interpolated.High, "high should match before")
	assert.Equal(t, 45.0, interpolated.Low, "low should match before")
	assert.Equal(t, int64(1285994), *interpolated.Volume, "volume should be preserved")
}

func TestPriceValidator_InterpolatePrice_BackwardFill(t *testing.T) {
	log := zerolog.Nop()
	validator := NewPriceValidator(log)

	before := []DailyPrice{} // No before prices
	after := []DailyPrice{
		{Date: "2025-08-12", Close: 46.7, Open: 47.2, High: 47.3, Low: 46.6},
	}

	price := DailyPrice{
		Date:   "2025-08-11",
		Close:  44458.62, // Abnormal
		Open:   44050.53,
		High:   44497.59,
		Low:    44050.53,
		Volume: intPtrForPriceValidator(1285994),
	}

	interpolated, method, err := validator.InterpolatePrice(price, before, after)
	require.NoError(t, err)
	assert.Equal(t, "backward_fill", method)

	// Should use after price directly
	assert.Equal(t, 46.7, interpolated.Close, "close should match after")
	assert.Equal(t, 47.2, interpolated.Open, "open should match after")
	assert.Equal(t, 47.3, interpolated.High, "high should match after")
	assert.Equal(t, 46.6, interpolated.Low, "low should match after")
	assert.Equal(t, int64(1285994), *interpolated.Volume, "volume should be preserved")
}

func TestPriceValidator_InterpolatePrice_NoContext(t *testing.T) {
	log := zerolog.Nop()
	validator := NewPriceValidator(log)

	price := DailyPrice{
		Date:   "2025-08-11",
		Close:  44458.62, // Abnormal
		Open:   44050.53,
		High:   44497.59,
		Low:    44050.53,
		Volume: intPtrForPriceValidator(1285994),
	}

	// No before or after prices
	interpolated, method, err := validator.InterpolatePrice(price, []DailyPrice{}, []DailyPrice{})
	require.NoError(t, err)
	assert.Equal(t, "no_interpolation", method)
	// Should return original price when no context available
	assert.Equal(t, 44458.62, interpolated.Close, "should return original when no interpolation possible")
}

func TestPriceValidator_ValidateAndInterpolate(t *testing.T) {
	log := zerolog.Nop()
	validator := NewPriceValidator(log)

	// Context with normal prices (newest first, as from database)
	context := []DailyPrice{
		{Date: "2025-08-10", Close: 47.0, Open: 46.0, High: 48.0, Low: 45.0}, // Most recent
		{Date: "2025-08-09", Close: 47.0, Open: 46.0, High: 48.0, Low: 45.0},
	}

	// Prices to validate: one normal, one abnormal (in chronological order)
	prices := []DailyPrice{
		{
			Date:   "2025-08-10",
			Close:  47.0, // Normal - will be used as previousPrice for next price
			Open:   46.0,
			High:   48.0,
			Low:    45.0,
			Volume: intPtrForPriceValidator(1000000),
		},
		{
			Date:   "2025-08-11",
			Close:  44458.62, // Abnormal (LDO.EU case) - spike from 47.0
			Open:   44050.53,
			High:   44497.59,
			Low:    44050.53,
			Volume: intPtrForPriceValidator(1285994),
		},
		{
			Date:   "2025-08-12",
			Close:  46.7, // Normal
			Open:   47.2,
			High:   47.3,
			Low:    46.6,
			Volume: intPtrForPriceValidator(3190483),
		},
	}

	result, logs, err := validator.ValidateAndInterpolate(prices, context)
	require.NoError(t, err)
	require.Len(t, result, 3, "should return same number of prices")
	require.Len(t, logs, 1, "should log one interpolation")

	// First price should be unchanged (normal)
	assert.Equal(t, 47.0, result[0].Close, "first price should be unchanged")

	// Second price should be interpolated
	// It will use linear interpolation between prices[0] (47.0) and prices[2] (46.7)
	// Date: 2025-08-11, before: 2025-08-10 (47.0), after: 2025-08-12 (46.7)
	// Days between: 1, total: 2, so: 47.0 + (46.7-47.0)*(1/2) = 47.0 - 0.15 = 46.85
	expectedClose := 47.0 + (46.7-47.0)*(1.0/2.0)
	assert.InDelta(t, expectedClose, result[1].Close, 0.1, "second price should be interpolated")
	assert.Equal(t, "2025-08-11", logs[0].Date)
	assert.Equal(t, 44458.62, logs[0].OriginalClose)
	assert.InDelta(t, expectedClose, logs[0].InterpolatedClose, 0.1)
	assert.Equal(t, "linear", logs[0].Method)         // Will use linear since both before and after are available
	assert.Equal(t, "spike_detected", logs[0].Reason) // Spike detection takes priority (uses previousPrice from array)

	// Third price should be unchanged
	assert.Equal(t, 46.7, result[2].Close, "third price should be unchanged")
	assert.Equal(t, int64(3190483), *result[2].Volume, "volume should be preserved")
}

func TestPriceValidator_ValidateAndInterpolate_MultipleAbnormal(t *testing.T) {
	log := zerolog.Nop()
	validator := NewPriceValidator(log)

	// Context with normal prices
	context := []DailyPrice{
		{Date: "2025-08-09", Close: 47.0, Open: 46.0, High: 48.0, Low: 45.0},
	}

	// Multiple abnormal prices in sequence
	prices := []DailyPrice{
		{
			Date:  "2025-08-10",
			Close: 47.0, // Normal
			Open:  46.0,
			High:  48.0,
			Low:   45.0,
		},
		{
			Date:  "2025-08-11",
			Close: 44458.62, // Abnormal
			Open:  44050.53,
			High:  44497.59,
			Low:   44050.53,
		},
		{
			Date:  "2025-08-12",
			Close: 44458.62, // Also abnormal
			Open:  44050.53,
			High:  44497.59,
			Low:   44050.53,
		},
		{
			Date:  "2025-08-13",
			Close: 46.7, // Normal
			Open:  47.2,
			High:  47.3,
			Low:   46.6,
		},
	}

	result, logs, err := validator.ValidateAndInterpolate(prices, context)
	require.NoError(t, err)
	require.Len(t, result, 4, "should return same number of prices")
	require.Len(t, logs, 2, "should log two interpolations")

	// First price should be unchanged (normal)
	assert.Equal(t, 47.0, result[0].Close, "first price should be unchanged")

	// Second price should be interpolated (between first and fourth)
	assert.InDelta(t, 47.0, result[1].Close, 1.0, "second price should be interpolated")
	assert.Equal(t, "2025-08-11", logs[0].Date)

	// Third price should be interpolated (between second and fourth)
	assert.InDelta(t, 46.7, result[2].Close, 1.0, "third price should be interpolated")
	assert.Equal(t, "2025-08-12", logs[1].Date)

	// Fourth price should be unchanged (normal)
	assert.Equal(t, 46.7, result[3].Close, "fourth price should be unchanged")
}

func TestPriceValidator_ValidateAndInterpolate_EmptyContext(t *testing.T) {
	log := zerolog.Nop()
	validator := NewPriceValidator(log)

	// No context available
	prices := []DailyPrice{
		{
			Date:  "2025-08-11",
			Close: 44458.62, // Abnormal but no context
			Open:  44050.53,
			High:  44497.59,
			Low:   44050.53,
		},
	}

	result, logs, err := validator.ValidateAndInterpolate(prices, []DailyPrice{})
	require.NoError(t, err)
	require.Len(t, result, 1)
	require.Len(t, logs, 1)

	// Should be flagged by absolute bounds
	assert.Equal(t, "absolute_bound_exceeded", logs[0].Reason)
	// Should use no_interpolation (no before, no after)
	assert.Equal(t, "no_interpolation", logs[0].Method)
}

// Test that before/after price lookups work correctly with DESC-ordered context
func TestPriceValidator_ValidateAndInterpolate_ContextLookups(t *testing.T) {
	log := zerolog.Nop()
	validator := NewPriceValidator(log)

	// Context with prices in DESC order (most recent first, as from GetRecentPrices)
	// Simulating syncing 2020 data when DB has 2024 data
	context := []DailyPrice{
		{Date: "2024-01-15", Close: 100.0, Open: 99.0, High: 101.0, Low: 98.0}, // Most recent (future relative to prices)
		{Date: "2024-01-14", Close: 99.0, Open: 98.0, High: 100.0, Low: 97.0},
		{Date: "2020-01-20", Close: 50.0, Open: 49.0, High: 51.0, Low: 48.0}, // Past price (after prices being validated)
		{Date: "2020-01-10", Close: 48.0, Open: 47.0, High: 49.0, Low: 46.0}, // Past price (before prices being validated)
		{Date: "2020-01-05", Close: 47.0, Open: 46.0, High: 48.0, Low: 45.0}, // Older past price (before prices being validated)
	}

	// Prices to validate (2020 dates, between context dates)
	prices := []DailyPrice{
		{
			Date:  "2020-01-15",
			Close: 44458.62, // Abnormal spike
			Open:  44050.53,
			High:  44497.59,
			Low:   44050.53,
		},
	}

	result, logs, err := validator.ValidateAndInterpolate(prices, context)
	require.NoError(t, err)
	require.Len(t, result, 1)
	require.Len(t, logs, 1)

	// Should find:
	// - before: 2020-01-10 (48.0) - most recent price in context that's before 2020-01-15
	// - after: 2020-01-20 (50.0) - earliest price in context that's after 2020-01-15
	// Should use linear interpolation between 48.0 and 50.0
	assert.Equal(t, "linear", logs[0].Method, "should use linear interpolation with both before and after from context")
	assert.InDelta(t, 49.0, result[0].Close, 1.0, "should interpolate between 48.0 and 50.0")
}

func intPtrForPriceValidator(i int64) *int64 {
	return &i
}
