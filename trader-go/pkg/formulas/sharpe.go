package formulas

import (
	"math"
)

// CalculateSharpeRatio calculates the Sharpe Ratio
// Faithful translation from Python: app/modules/scoring/domain/calculations/sharpe.py
//
// Sharpe Ratio Formula:
//   Sharpe = (Portfolio Return - Risk-free Rate) / Standard Deviation of Returns
//   Annualized: Sharpe × sqrt(252) for daily returns
//
// Args:
//   returns: Array of periodic returns (daily, monthly, etc.)
//   riskFreeRate: Risk-free rate (annual, as decimal, e.g., 0.02 for 2%)
//   periodsPerYear: Number of periods per year (252 for daily, 12 for monthly)
//
// Returns:
//   Sharpe ratio or nil if insufficient data
func CalculateSharpeRatio(returns []float64, riskFreeRate float64, periodsPerYear int) *float64 {
	if len(returns) < 2 {
		return nil
	}

	// Calculate mean return
	meanReturn := Mean(returns)

	// Calculate standard deviation
	stdDev := StdDev(returns)
	if stdDev == 0 {
		return nil
	}

	// Calculate periodic risk-free rate
	periodicRiskFree := riskFreeRate / float64(periodsPerYear)

	// Calculate Sharpe ratio
	sharpe := (meanReturn - periodicRiskFree) / stdDev

	// Annualize
	annualizedSharpe := sharpe * math.Sqrt(float64(periodsPerYear))

	return &annualizedSharpe
}

// CalculateSharpeFromPrices is a convenience function that calculates Sharpe ratio
// directly from price data
func CalculateSharpeFromPrices(prices []float64, riskFreeRate float64) *float64 {
	if len(prices) < 2 {
		return nil
	}

	// Convert prices to returns
	returns := CalculateReturns(prices)

	// Calculate Sharpe ratio assuming daily data (252 trading days)
	return CalculateSharpeRatio(returns, riskFreeRate, 252)
}

// CalculateSortinoRatio calculates the Sortino Ratio (downside deviation version of Sharpe)
// Only considers downside volatility (negative returns)
//
// Sortino Formula:
//   Sortino = (Portfolio Return - Risk-free Rate) / Downside Deviation
//
// Args:
//   returns: Array of periodic returns
//   riskFreeRate: Risk-free rate (annual, as decimal)
//   periodsPerYear: Number of periods per year
//
// Returns:
//   Sortino ratio or nil if insufficient data
func CalculateSortinoRatio(returns []float64, riskFreeRate float64, periodsPerYear int) *float64 {
	if len(returns) < 2 {
		return nil
	}

	// Calculate mean return
	meanReturn := Mean(returns)

	// Calculate downside deviation (only negative returns)
	var downsideSquaredSum float64
	downsideCount := 0

	for _, ret := range returns {
		if ret < 0 {
			downsideSquaredSum += ret * ret
			downsideCount++
		}
	}

	if downsideCount == 0 {
		// No downside, return nil (or could return infinity)
		return nil
	}

	downsideDeviation := math.Sqrt(downsideSquaredSum / float64(downsideCount))
	if downsideDeviation == 0 {
		return nil
	}

	// Calculate periodic risk-free rate
	periodicRiskFree := riskFreeRate / float64(periodsPerYear)

	// Calculate Sortino ratio
	sortino := (meanReturn - periodicRiskFree) / downsideDeviation

	// Annualize
	annualizedSortino := sortino * math.Sqrt(float64(periodsPerYear))

	return &annualizedSortino
}
