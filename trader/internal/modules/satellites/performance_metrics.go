package satellites

import (
	"math"

	"github.com/rs/zerolog"
)

// PerformanceMetrics represents performance metrics for a satellite bucket
type PerformanceMetrics struct {
	BucketID   string `json:"bucket_id"`
	PeriodDays int    `json:"period_days"`

	// Returns
	TotalReturn      float64 `json:"total_return"`      // Total return over period (%)
	AnnualizedReturn float64 `json:"annualized_return"` // Annualized return (%)

	// Risk metrics
	Volatility         float64 `json:"volatility"`          // Standard deviation of returns (%)
	DownsideVolatility float64 `json:"downside_volatility"` // Std dev of negative returns only (%)
	MaxDrawdown        float64 `json:"max_drawdown"`        // Maximum drawdown (%)

	// Risk-adjusted returns
	SharpeRatio  float64 `json:"sharpe_ratio"`  // Return per unit of total risk
	SortinoRatio float64 `json:"sortino_ratio"` // Return per unit of downside risk
	CalmarRatio  float64 `json:"calmar_ratio"`  // Return per unit of max drawdown

	// Trade statistics
	TotalTrades   int     `json:"total_trades"`
	WinningTrades int     `json:"winning_trades"`
	LosingTrades  int     `json:"losing_trades"`
	WinRate       float64 `json:"win_rate"`      // % of profitable trades
	ProfitFactor  float64 `json:"profit_factor"` // Gross profit / gross loss

	// Additional metrics
	AvgWin      float64 `json:"avg_win"`      // Average winning trade (%)
	AvgLoss     float64 `json:"avg_loss"`     // Average losing trade (%)
	LargestWin  float64 `json:"largest_win"`  // Largest winning trade (%)
	LargestLoss float64 `json:"largest_loss"` // Largest losing trade (%)

	// Score for meta-allocator
	CompositeScore float64 `json:"composite_score"` // Weighted combination of metrics

	// Metadata
	StartDate    string `json:"start_date"`
	EndDate      string `json:"end_date"`
	CalculatedAt string `json:"calculated_at"`
}

// CalculateSharpeRatio calculates Sharpe ratio.
//
// Sharpe = (Mean Return - Risk Free Rate) / Std Dev of Returns
//
// Args:
//
//	returns: List of period returns (as decimals, e.g., 0.05 for 5%)
//	riskFreeRate: Annual risk-free rate (default 0)
//
// Returns:
//
//	Sharpe ratio (higher is better)
func CalculateSharpeRatio(returns []float64, riskFreeRate float64) float64 {
	if len(returns) < 2 {
		return 0.0
	}

	meanReturn := mean(returns)
	stdReturn := stdDev(returns)

	if stdReturn == 0 {
		return 0.0
	}

	// Adjust risk-free rate to period (assuming daily returns)
	periodRF := riskFreeRate / 252.0

	sharpe := (meanReturn - periodRF) / stdReturn

	return sharpe
}

// CalculateSortinoRatio calculates Sortino ratio.
//
// Sortino = (Mean Return - Target) / Downside Deviation
//
// Only penalizes downside volatility, not upside.
//
// Args:
//
//	returns: List of period returns
//	riskFreeRate: Annual risk-free rate
//	targetReturn: Minimum acceptable return (default 0)
//
// Returns:
//
//	Sortino ratio (higher is better)
func CalculateSortinoRatio(returns []float64, riskFreeRate float64, targetReturn float64) float64 {
	if len(returns) < 2 {
		return 0.0
	}

	meanReturn := mean(returns)

	// Calculate downside deviation (only negative returns)
	var downsideReturns []float64
	for _, r := range returns {
		if r < targetReturn {
			downsideReturns = append(downsideReturns, r-targetReturn)
		}
	}

	if len(downsideReturns) == 0 {
		return math.Inf(1) // No downside = infinite Sortino
	}

	downsideStd := stdDev(downsideReturns)

	if downsideStd == 0 {
		return 0.0
	}

	sortino := (meanReturn - targetReturn) / downsideStd

	return sortino
}

// CalculateMaxDrawdown calculates maximum drawdown from equity curve.
//
// Args:
//
//	equityCurve: List of portfolio values over time
//
// Returns:
//
//	Tuple of (max_drawdown_pct, peak_idx, trough_idx)
func CalculateMaxDrawdown(equityCurve []float64) (float64, int, int) {
	if len(equityCurve) < 2 {
		return 0.0, 0, 0
	}

	// Calculate running maximum
	runningMax := make([]float64, len(equityCurve))
	runningMax[0] = equityCurve[0]
	for i := 1; i < len(equityCurve); i++ {
		if equityCurve[i] > runningMax[i-1] {
			runningMax[i] = equityCurve[i]
		} else {
			runningMax[i] = runningMax[i-1]
		}
	}

	// Calculate drawdown at each point
	drawdown := make([]float64, len(equityCurve))
	for i := 0; i < len(equityCurve); i++ {
		drawdown[i] = (equityCurve[i] - runningMax[i]) / runningMax[i]
	}

	// Find maximum drawdown
	maxDDIdx := 0
	maxDD := 0.0
	for i := 0; i < len(drawdown); i++ {
		if drawdown[i] < maxDD {
			maxDD = drawdown[i]
			maxDDIdx = i
		}
	}

	maxDD = math.Abs(maxDD)

	// Find peak before this trough
	peakIdx := 0
	peakValue := equityCurve[0]
	for i := 0; i <= maxDDIdx; i++ {
		if equityCurve[i] > peakValue {
			peakValue = equityCurve[i]
			peakIdx = i
		}
	}

	return maxDD, peakIdx, maxDDIdx
}

// CalculateCalmarRatio calculates Calmar ratio.
//
// Calmar = Annualized Return / Max Drawdown
//
// Args:
//
//	annualizedReturn: Annual return (%)
//	maxDrawdown: Maximum drawdown (%)
//
// Returns:
//
//	Calmar ratio (higher is better)
func CalculateCalmarRatio(annualizedReturn float64, maxDrawdown float64) float64 {
	if maxDrawdown == 0 {
		return 0.0
	}

	return annualizedReturn / maxDrawdown
}

// CalculateWinRate calculates win rate from trade history.
//
// Args:
//
//	trades: List of trades with profit_loss field
//
// Returns:
//
//	Tuple of (win_rate, winning_count, losing_count)
func CalculateWinRate(profitLosses []float64) (float64, int, int) {
	if len(profitLosses) == 0 {
		return 0.0, 0, 0
	}

	winning := 0
	losing := 0

	for _, pnl := range profitLosses {
		if pnl > 0 {
			winning++
		} else if pnl < 0 {
			losing++
		}
	}

	total := winning + losing
	winRate := 0.0
	if total > 0 {
		winRate = float64(winning) / float64(total) * 100
	}

	return winRate, winning, losing
}

// CalculateProfitFactor calculates profit factor.
//
// Profit Factor = Gross Profit / Gross Loss
//
// Args:
//
//	trades: List of profit/loss values
//
// Returns:
//
//	Profit factor (>1 is profitable, higher is better)
func CalculateProfitFactor(profitLosses []float64) float64 {
	if len(profitLosses) == 0 {
		return 0.0
	}

	grossProfit := 0.0
	grossLoss := 0.0

	for _, pnl := range profitLosses {
		if pnl > 0 {
			grossProfit += pnl
		} else if pnl < 0 {
			grossLoss += math.Abs(pnl)
		}
	}

	if grossLoss == 0 {
		if grossProfit > 0 {
			return math.Inf(1)
		}
		return 0.0
	}

	return grossProfit / grossLoss
}

// CalculateBucketPerformance calculates comprehensive performance metrics for a bucket.
//
// NOTE: This implementation is simplified and requires integration with the
// trading module's repository to fetch actual trade data. The Python version
// uses app.repositories.TradeRepository which needs to be mapped to the Go
// trading module repository.
//
// Args:
//
//	bucketID: Bucket ID
//	periodDays: Evaluation period in days (default 90 for quarterly)
//	riskFreeRate: Annual risk-free rate (default 3%)
//	balanceService: Balance service for current values
//	log: Logger
//
// Returns:
//
//	PerformanceMetrics object or nil if insufficient data
func CalculateBucketPerformance(
	bucketID string,
	settings *SatelliteSettings,
	balanceService *BalanceService,
	log zerolog.Logger,
) (*PerformanceMetrics, error) {
	// TODO: Integrate with trading module repository to get actual trade data
	// For now, return nil to indicate insufficient data
	// This needs to be wired up to: trader/internal/modules/trading/repository.go
	//
	// Example integration:
	// allTrades, err := tradeRepo.GetAll()
	// bucketTrades := filterTradesByBucket(allTrades, bucketID, startDate, endDate)

	// Extract risk parameters from settings
	periodDays := settings.EvaluationPeriodDays
	riskFreeRate := settings.RiskFreeRate
	// sortinoMAR := settings.SortinoMAR // Will be used when calculating Sortino ratio

	log.Info().
		Str("bucket_id", bucketID).
		Int("period_days", periodDays).
		Float64("risk_free_rate", riskFreeRate).
		Msg("Performance calculation requires trade repository integration (not yet implemented)")

	// Return nil to indicate insufficient data (matches Python behavior)
	return nil, nil
}

// Helper functions for statistical calculations

func mean(values []float64) float64 {
	if len(values) == 0 {
		return 0.0
	}

	sum := 0.0
	for _, v := range values {
		sum += v
	}

	return sum / float64(len(values))
}

func stdDev(values []float64) float64 {
	if len(values) < 2 {
		return 0.0
	}

	m := mean(values)
	sumSquares := 0.0

	for _, v := range values {
		diff := v - m
		sumSquares += diff * diff
	}

	// Sample standard deviation (ddof=1 in numpy)
	variance := sumSquares / float64(len(values)-1)

	return math.Sqrt(variance)
}

// CalculateCompositeScore calculates a weighted composite score for meta-allocator.
//
// Args:
//
//	metrics: Performance metrics
//
// Returns:
//
//	Composite score (higher is better)
func CalculateCompositeScore(metrics *PerformanceMetrics) float64 {
	// Composite score (weighted average for meta-allocator)
	// Higher is better
	compositeScore := 0.3*metrics.SharpeRatio +
		0.3*metrics.SortinoRatio +
		0.2*(metrics.ProfitFactor-1) + // Normalize to 0+
		0.1*(metrics.WinRate/100) + // Normalize to 0-1
		0.1*metrics.CalmarRatio

	return compositeScore
}
