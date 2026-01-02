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
