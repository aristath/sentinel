package universe

import (
	"fmt"
	"math"
	"time"

	"github.com/rs/zerolog"
)

const (
	// Validation thresholds
	maxPriceMultiplier    = 10.0    // Price > 10x average is abnormal
	minPriceMultiplier    = 0.1     // Price < 0.1x average is abnormal
	maxPriceChangePercent = 1000.0  // >1000% change is a spike
	minPriceChangePercent = -90.0   // <-90% change is a crash
	absolutePriceMax      = 10000.0 // Absolute maximum price (EUR/USD)
	absolutePriceMin      = 0.01    // Absolute minimum price
	contextWindowDays     = 30      // Use last 30 days for context
)

// InterpolationLog records when a price was interpolated
type InterpolationLog struct {
	Date              string
	OriginalClose     float64
	InterpolatedClose float64
	Method            string // "linear", "forward_fill", "backward_fill"
	Reason            string
}

// PriceValidator validates and interpolates abnormal prices
type PriceValidator struct {
	log zerolog.Logger
}

// NewPriceValidator creates a new price validator
func NewPriceValidator(log zerolog.Logger) *PriceValidator {
	return &PriceValidator{
		log: log.With().Str("component", "price_validator").Logger(),
	}
}

// ValidatePrice checks if a price is valid
// Returns (isValid, reason)
func (v *PriceValidator) ValidatePrice(price DailyPrice, context []DailyPrice) (bool, string) {
	// 1. OHLC consistency checks (always applied, no context needed)
	if price.High < price.Low {
		return false, "high_below_low"
	}
	if price.High < price.Open {
		return false, "high_below_open"
	}
	if price.High < price.Close {
		return false, "high_below_close"
	}
	if price.Low > price.Open {
		return false, "low_above_open"
	}
	if price.Low > price.Close {
		return false, "low_above_close"
	}

	// 2. Percentage change checks (requires context)
	if len(context) > 0 {
		// Check day-over-day change FIRST (takes priority over average checks)
		prevClose := context[0].Close
		if prevClose > 0 {
			changePercent := ((price.Close - prevClose) / prevClose) * 100.0
			if changePercent > maxPriceChangePercent {
				return false, "spike_detected"
			}
			if changePercent < minPriceChangePercent {
				return false, "crash_detected"
			}
		}

		// Calculate average of recent prices (last 30 or all if <30)
		contextSize := len(context)
		if contextSize > contextWindowDays {
			contextSize = contextWindowDays
		}
		recentContext := context[:contextSize]

		var sum float64
		for _, p := range recentContext {
			sum += p.Close
		}
		avgPrice := sum / float64(len(recentContext))

		// Check if price is too high or too low relative to average
		if price.Close > avgPrice*maxPriceMultiplier {
			return false, "price_too_high"
		}
		if price.Close < avgPrice*minPriceMultiplier {
			return false, "price_too_low"
		}
	}

	// 3. Absolute bounds (fallback when no context)
	if len(context) == 0 {
		if price.Close > absolutePriceMax {
			return false, "absolute_bound_exceeded"
		}
		if price.Close < absolutePriceMin {
			return false, "absolute_bound_below_minimum"
		}
	}

	return true, ""
}

// InterpolatePrice interpolates an abnormal price using surrounding valid prices
// Returns (interpolatedPrice, method, error)
func (v *PriceValidator) InterpolatePrice(price DailyPrice, before []DailyPrice, after []DailyPrice) (DailyPrice, string, error) {
	interpolated := price // Start with original (preserves date, volume)

	// Parse dates for calculation
	priceDate, err := time.Parse("2006-01-02", price.Date)
	if err != nil {
		return interpolated, "", fmt.Errorf("failed to parse price date: %w", err)
	}

	// Linear interpolation (both before and after available)
	if len(before) > 0 && len(after) > 0 {
		beforePrice := before[0]
		afterPrice := after[0]

		beforeDate, err := time.Parse("2006-01-02", beforePrice.Date)
		if err != nil {
			return interpolated, "", fmt.Errorf("failed to parse before date: %w", err)
		}
		afterDate, err := time.Parse("2006-01-02", afterPrice.Date)
		if err != nil {
			return interpolated, "", fmt.Errorf("failed to parse after date: %w", err)
		}

		daysBetween := priceDate.Sub(beforeDate).Hours() / 24.0
		totalDays := afterDate.Sub(beforeDate).Hours() / 24.0

		if totalDays <= 0 {
			return interpolated, "", fmt.Errorf("invalid date range: totalDays <= 0")
		}

		// Interpolate Close
		interpolated.Close = beforePrice.Close + (afterPrice.Close-beforePrice.Close)*(daysBetween/totalDays)

		// Calculate ratios for Open/High/Low
		beforeOpenRatio := beforePrice.Open / beforePrice.Close
		afterOpenRatio := afterPrice.Open / afterPrice.Close
		openRatio := (beforeOpenRatio + afterOpenRatio) / 2.0

		beforeHighRatio := beforePrice.High / beforePrice.Close
		afterHighRatio := afterPrice.High / afterPrice.Close
		highRatio := (beforeHighRatio + afterHighRatio) / 2.0

		beforeLowRatio := beforePrice.Low / beforePrice.Close
		afterLowRatio := afterPrice.Low / afterPrice.Close
		lowRatio := (beforeLowRatio + afterLowRatio) / 2.0

		// Apply ratios to interpolated Close
		interpolated.Open = interpolated.Close * openRatio
		interpolated.High = interpolated.Close * highRatio
		interpolated.Low = interpolated.Close * lowRatio

		// Ensure OHLC consistency
		if interpolated.High < interpolated.Close {
			interpolated.High = interpolated.Close
		}
		if interpolated.Low > interpolated.Close {
			interpolated.Low = interpolated.Close
		}
		if interpolated.High < interpolated.Open {
			interpolated.High = interpolated.Open
		}
		if interpolated.Low > interpolated.Open {
			interpolated.Low = interpolated.Open
		}

		return interpolated, "linear", nil
	}

	// Forward fill (only before available)
	if len(before) > 0 {
		beforePrice := before[0]
		interpolated.Close = beforePrice.Close
		interpolated.Open = beforePrice.Open
		interpolated.High = beforePrice.High
		interpolated.Low = beforePrice.Low
		return interpolated, "forward_fill", nil
	}

	// Backward fill (only after available)
	if len(after) > 0 {
		afterPrice := after[0]
		interpolated.Close = afterPrice.Close
		interpolated.Open = afterPrice.Open
		interpolated.High = afterPrice.High
		interpolated.Low = afterPrice.Low
		return interpolated, "backward_fill", nil
	}

	// No context available - ensure OHLC consistency at minimum
	ensureOHLCConsistency(&interpolated)
	return interpolated, "no_interpolation", nil
}

// ValidateAndInterpolate validates all prices and interpolates abnormal ones
// Returns (validatedPrices, interpolationLogs, error)
func (v *PriceValidator) ValidateAndInterpolate(prices []DailyPrice, context []DailyPrice) ([]DailyPrice, []InterpolationLog, error) {
	if len(prices) == 0 {
		return prices, []InterpolationLog{}, nil
	}

	result := make([]DailyPrice, 0, len(prices))
	logs := []InterpolationLog{}

	for i, price := range prices {
		valid, reason := v.ValidatePrice(price, context)
		if valid {
			// Price is valid, keep as-is
			result = append(result, price)
			continue
		}

		// Price is abnormal, need to interpolate
		// Find before and after prices
		var before []DailyPrice
		var after []DailyPrice

		// Look for before price (previous valid price in prices array or result)
		// First check already processed valid prices in result
		for j := len(result) - 1; j >= 0; j-- {
			// Check if this result price is before the current price (by date)
			resultDate, err1 := time.Parse("2006-01-02", result[j].Date)
			currentDate, err2 := time.Parse("2006-01-02", price.Date)
			if err1 == nil && err2 == nil && resultDate.Before(currentDate) {
				before = []DailyPrice{result[j]}
				break
			}
		}
		// If not found in result, check previous prices in the prices array
		if len(before) == 0 {
			for j := i - 1; j >= 0; j-- {
				prevValid, _ := v.ValidatePrice(prices[j], context)
				if prevValid {
					before = []DailyPrice{prices[j]}
					break
				}
			}
		}
		// If still not found, find the most recent context price that's before current price
		if len(before) == 0 && len(context) > 0 {
			priceDate, err := time.Parse("2006-01-02", price.Date)
			if err == nil {
				for _, ctxPrice := range context {
					ctxDate, err := time.Parse("2006-01-02", ctxPrice.Date)
					if err == nil && ctxDate.Before(priceDate) {
						before = []DailyPrice{ctxPrice}
						break
					}
				}
			}
		}

		// Look for after price (next valid price in prices array)
		for j := i + 1; j < len(prices); j++ {
			// Check if next price is valid
			nextValid, _ := v.ValidatePrice(prices[j], context)
			if nextValid {
				after = []DailyPrice{prices[j]}
				break
			}
		}
		// If not found in prices, try to find a future date in context
		if len(after) == 0 && len(context) > 0 {
			priceDate, err := time.Parse("2006-01-02", price.Date)
			if err == nil {
				for _, ctxPrice := range context {
					ctxDate, err := time.Parse("2006-01-02", ctxPrice.Date)
					if err == nil && ctxDate.After(priceDate) {
						after = []DailyPrice{ctxPrice}
						break
					}
				}
			}
		}

		// Interpolate
		interpolated, method, err := v.InterpolatePrice(price, before, after)
		if err != nil {
			v.log.Error().
				Err(err).
				Str("date", price.Date).
				Msg("Failed to interpolate price, using original")
			// Use original price if interpolation fails
			result = append(result, price)
			continue
		}

		// Log interpolation
		logs = append(logs, InterpolationLog{
			Date:              price.Date,
			OriginalClose:     price.Close,
			InterpolatedClose: interpolated.Close,
			Method:            method,
			Reason:            reason,
		})

		v.log.Warn().
			Str("date", price.Date).
			Float64("original_close", price.Close).
			Float64("interpolated_close", interpolated.Close).
			Str("method", method).
			Str("reason", reason).
			Msg("Interpolated abnormal price")

		result = append(result, interpolated)
	}

	return result, logs, nil
}

// Helper function to ensure OHLC consistency
func ensureOHLCConsistency(price *DailyPrice) {
	// Ensure High >= all
	price.High = math.Max(price.High, price.Open)
	price.High = math.Max(price.High, price.Close)

	// Ensure Low <= all
	price.Low = math.Min(price.Low, price.Open)
	price.Low = math.Min(price.Low, price.Close)

	// Ensure High >= Low
	if price.High < price.Low {
		price.High = price.Low
	}
}
