package formulas

import (
	"math"

	"gonum.org/v1/gonum/stat"
)

// Mean calculates the arithmetic mean of a slice of float64 values
func Mean(data []float64) float64 {
	if len(data) == 0 {
		return 0
	}
	return stat.Mean(data, nil)
}

// StdDev calculates the standard deviation of a slice of float64 values
func StdDev(data []float64) float64 {
	if len(data) == 0 {
		return 0
	}
	return stat.StdDev(data, nil)
}

// Variance calculates the variance of a slice of float64 values
func Variance(data []float64) float64 {
	if len(data) == 0 {
		return 0
	}
	return stat.Variance(data, nil)
}

// AnnualizedVolatility calculates annualized volatility from daily returns
// Formula: Std Dev of Daily Returns × sqrt(252 trading days)
func AnnualizedVolatility(dailyReturns []float64) float64 {
	if len(dailyReturns) == 0 {
		return 0
	}

	stdDev := StdDev(dailyReturns)
	return stdDev * math.Sqrt(252) // 252 trading days per year
}

// CalculateReturns converts prices to percentage returns
// Returns[i] = (Price[i] - Price[i-1]) / Price[i-1]
func CalculateReturns(prices []float64) []float64 {
	if len(prices) < 2 {
		return []float64{}
	}

	returns := make([]float64, len(prices)-1)
	for i := 1; i < len(prices); i++ {
		if prices[i-1] != 0 {
			returns[i-1] = (prices[i] - prices[i-1]) / prices[i-1]
		}
	}

	return returns
}

// Correlation calculates the Pearson correlation coefficient between two datasets
func Correlation(x, y []float64) float64 {
	if len(x) == 0 || len(y) == 0 || len(x) != len(y) {
		return 0
	}
	return stat.Correlation(x, y, nil)
}

// Covariance calculates the covariance between two datasets
func Covariance(x, y []float64) float64 {
	if len(x) == 0 || len(y) == 0 || len(x) != len(y) {
		return 0
	}
	return stat.Covariance(x, y, nil)
}

// CalculateAnnualReturn calculates annualized return from daily returns
// Faithful translation of Python empyrical.annual_return
//
// Formula: ((1+r1)*(1+r2)*...*(1+rN))^(252/N) - 1
//
// This computes the compound annual growth rate (CAGR) from a series of
// periodic returns by first calculating the cumulative return and then
// annualizing it based on the number of trading periods.
//
// Args:
//
//	returns: Daily returns as decimals (e.g., 0.01 = 1%)
//
// Returns:
//
//	Annualized return as decimal (e.g., 0.15 = 15% annual return)
func CalculateAnnualReturn(returns []float64) float64 {
	if len(returns) == 0 {
		return 0.0
	}

	// Calculate cumulative return: (1+r1)*(1+r2)*...*(1+rN)
	cumulative := 1.0
	for _, r := range returns {
		cumulative *= (1 + r)
	}

	// Annualize: cumulative^(252/N) - 1
	// 252 is the number of trading days per year
	periodsPerYear := 252.0
	numPeriods := float64(len(returns))

	// For very short periods (< 3 days), return simple cumulative return
	// to avoid extreme annualization
	if numPeriods < 3 {
		return cumulative - 1
	}

	years := numPeriods / periodsPerYear

	// Apply compound annual growth rate formula
	annualized := math.Pow(cumulative, 1.0/years) - 1
	return annualized
}
