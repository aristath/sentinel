package formulas

import "math"

// MonthlyPrice represents a monthly price data point
type MonthlyPrice struct {
	YearMonth   string  `json:"year_month"`
	AvgAdjClose float64 `json:"avg_adj_close"`
}

// CalculateCAGR calculates Compound Annual Growth Rate from monthly prices
// Faithful translation from Python: app/modules/scoring/domain/calculations/cagr.py
//
// Formula: CAGR = (Ending Value / Beginning Value)^(1/years) - 1
//
// Args:
//
//	prices: Slice of MonthlyPrice with year_month and avg_adj_close
//	months: Number of months to use (e.g., 60 for 5 years)
//
// Returns:
//
//	CAGR as decimal (e.g., 0.11 = 11%) or nil if insufficient data
func CalculateCAGR(prices []MonthlyPrice, months int) *float64 {
	const minMonthsForCAGR = 12

	if len(prices) < minMonthsForCAGR {
		return nil
	}

	// Use the requested months or all available data (whichever is less)
	useMonths := months
	if useMonths > len(prices) {
		useMonths = len(prices)
	}

	// Get the slice of prices we'll use
	priceSlice := prices[len(prices)-useMonths:]

	startPrice := priceSlice[0].AvgAdjClose
	endPrice := priceSlice[len(priceSlice)-1].AvgAdjClose

	// Validate prices
	if startPrice <= 0 || endPrice <= 0 {
		return nil
	}

	years := float64(useMonths) / 12.0

	// For very short periods (< 3 months), return simple return
	if years < 0.25 {
		result := (endPrice / startPrice) - 1
		return &result
	}

	// Calculate CAGR: (end/start)^(1/years) - 1
	cagr := math.Pow(endPrice/startPrice, 1/years) - 1
	return &cagr
}

// CalculateCAGRFromPrices is a convenience function that takes raw price values
// instead of MonthlyPrice structs
func CalculateCAGRFromPrices(prices []float64, months int) *float64 {
	if len(prices) == 0 {
		return nil
	}

	// Convert to MonthlyPrice format
	monthlyPrices := make([]MonthlyPrice, len(prices))
	for i, price := range prices {
		monthlyPrices[i] = MonthlyPrice{
			AvgAdjClose: price,
		}
	}

	return CalculateCAGR(monthlyPrices, months)
}
