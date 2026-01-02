package formulas

import "math"

// DrawdownMetrics represents drawdown analysis results
type DrawdownMetrics struct {
	MaxDrawdown     float64 `json:"max_drawdown"`      // Maximum drawdown (as positive percentage, e.g., 0.25 = 25% drawdown)
	CurrentDrawdown float64 `json:"current_drawdown"`  // Current drawdown from peak
	DaysInDrawdown  int     `json:"days_in_drawdown"`  // Days since peak
	PeakValue       float64 `json:"peak_value"`        // Value at peak
	CurrentValue    float64 `json:"current_value"`     // Current value
}

// CalculateMaxDrawdown calculates the maximum drawdown from a price series
// Faithful translation from Python: app/modules/scoring/domain/calculations/drawdown.py
//
// Drawdown Formula:
//   Drawdown = (Peak Value - Current Value) / Peak Value
//   Max Drawdown = Maximum of all drawdowns
//
// Args:
//   prices: Array of prices (daily, adjusted close)
//
// Returns:
//   Maximum drawdown as positive percentage (0.25 = 25% loss from peak) or nil
func CalculateMaxDrawdown(prices []float64) *float64 {
	if len(prices) < 2 {
		return nil
	}

	maxDrawdown := 0.0
	peak := prices[0]

	for _, price := range prices {
		// Update peak
		if price > peak {
			peak = price
		}

		// Calculate drawdown from peak
		if peak > 0 {
			drawdown := (peak - price) / peak
			if drawdown > maxDrawdown {
				maxDrawdown = drawdown
			}
		}
	}

	return &maxDrawdown
}

// CalculateDrawdownMetrics calculates comprehensive drawdown metrics
// including current drawdown, days in drawdown, and peak values
func CalculateDrawdownMetrics(prices []float64) *DrawdownMetrics {
	if len(prices) < 2 {
		return nil
	}

	maxDrawdown := 0.0
	peak := prices[0]
	peakIndex := 0
	currentValue := prices[len(prices)-1]

	for i, price := range prices {
		// Update peak
		if price > peak {
			peak = price
			peakIndex = i
		}

		// Calculate drawdown from peak
		if peak > 0 {
			drawdown := (peak - price) / peak
			if drawdown > maxDrawdown {
				maxDrawdown = drawdown
			}
		}
	}

	// Calculate current drawdown
	currentDrawdown := 0.0
	if peak > 0 {
		currentDrawdown = (peak - currentValue) / peak
	}

	// Days in drawdown (from peak to current)
	daysInDrawdown := len(prices) - 1 - peakIndex

	return &DrawdownMetrics{
		MaxDrawdown:     maxDrawdown,
		CurrentDrawdown: currentDrawdown,
		DaysInDrawdown:  daysInDrawdown,
		PeakValue:       peak,
		CurrentValue:    currentValue,
	}
}

// Calculate52WeekHigh finds the 52-week high price
func Calculate52WeekHigh(prices []float64) *float64 {
	if len(prices) == 0 {
		return nil
	}

	// Take last 252 trading days (approximately 52 weeks)
	startIdx := 0
	if len(prices) > 252 {
		startIdx = len(prices) - 252
	}

	relevant := prices[startIdx:]
	high := relevant[0]

	for _, price := range relevant {
		if price > high {
			high = price
		}
	}

	return &high
}

// Calculate52WeekLow finds the 52-week low price
func Calculate52WeekLow(prices []float64) *float64 {
	if len(prices) == 0 {
		return nil
	}

	// Take last 252 trading days (approximately 52 weeks)
	startIdx := 0
	if len(prices) > 252 {
		startIdx = len(prices) - 252
	}

	relevant := prices[startIdx:]
	low := relevant[0]

	for _, price := range relevant {
		if price < low {
			low = price
		}
	}

	return &low
}

// CalculateDistanceFrom52WeekHigh calculates how far below the 52-week high the current price is
// Returns positive percentage if below high (e.g., 0.20 = 20% below high)
func CalculateDistanceFrom52WeekHigh(prices []float64) *float64 {
	if len(prices) == 0 {
		return nil
	}

	high := Calculate52WeekHigh(prices)
	if high == nil || *high == 0 {
		return nil
	}

	currentPrice := prices[len(prices)-1]
	distance := (*high - currentPrice) / *high

	return &distance
}

// CalculateMomentum calculates price momentum over a period
// Returns percentage change over the period
func CalculateMomentum(prices []float64, days int) *float64 {
	if len(prices) < days+1 {
		return nil
	}

	startPrice := prices[len(prices)-days-1]
	endPrice := prices[len(prices)-1]

	if startPrice == 0 {
		return nil
	}

	momentum := (endPrice - startPrice) / startPrice
	return &momentum
}

// CalculateVolatility calculates annualized volatility from daily prices
// Returns annualized standard deviation of returns
func CalculateVolatility(prices []float64) *float64 {
	if len(prices) < 2 {
		return nil
	}

	returns := CalculateReturns(prices)
	volatility := AnnualizedVolatility(returns)

	return &volatility
}

// CalculateVolatilityWindow calculates volatility over a specific window
func CalculateVolatilityWindow(prices []float64, days int) *float64 {
	if len(prices) < days+1 {
		return nil
	}

	// Get the last 'days' prices
	window := prices[len(prices)-days:]
	return CalculateVolatility(window)
}

// CalculateCurrentVolatility calculates short-term (60-day) volatility
func CalculateCurrentVolatility(prices []float64) *float64 {
	return CalculateVolatilityWindow(prices, 60)
}

// CalculateHistoricalVolatility calculates long-term (365-day) volatility
func CalculateHistoricalVolatility(prices []float64) *float64 {
	return CalculateVolatilityWindow(prices, 365)
}

// CalculateVolatilityRatio calculates the ratio of current to historical volatility
// Returns > 1.0 if volatility is increasing, < 1.0 if decreasing
func CalculateVolatilityRatio(prices []float64) *float64 {
	current := CalculateCurrentVolatility(prices)
	historical := CalculateHistoricalVolatility(prices)

	if current == nil || historical == nil || *historical == 0 {
		return nil
	}

	ratio := *current / *historical
	return &ratio
}

// CalcluateUlcerIndex calculates the Ulcer Index (downside risk measure)
// Measures depth and duration of drawdowns
func CalculateUlcerIndex(prices []float64, period int) *float64 {
	if len(prices) < period {
		return nil
	}

	// Get last 'period' prices
	window := prices[len(prices)-period:]

	// Calculate squared drawdowns
	peak := window[0]
	sumSquaredDrawdowns := 0.0

	for _, price := range window {
		if price > peak {
			peak = price
		}

		if peak > 0 {
			drawdown := (peak - price) / peak
			sumSquaredDrawdowns += drawdown * drawdown
		}
	}

	// Ulcer Index is the square root of the mean of squared drawdowns
	ulcer := math.Sqrt(sumSquaredDrawdowns / float64(period))
	return &ulcer
}
