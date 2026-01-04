package satellites

import (
	"fmt"
	"math"
	"sort"
	"time"

	"github.com/rs/zerolog"

	"github.com/aristath/arduino-trader/internal/modules/trading"
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

// ClosedTrade represents a matched buy-sell pair for P&L calculation
type ClosedTrade struct {
	Symbol     string  // Security symbol
	BuyDate    string  // Buy execution timestamp
	SellDate   string  // Sell execution timestamp
	Quantity   float64 // Number of shares/units
	BuyPrice   float64 // Purchase price per unit
	SellPrice  float64 // Sale price per unit
	ProfitLoss float64 // Realized P&L in EUR
	ReturnPct  float64 // Return percentage: (SellPrice - BuyPrice) / BuyPrice
}

// PositionLot represents an open position lot for FIFO matching
type PositionLot struct {
	BuyDate  string  // Buy execution timestamp
	Quantity float64 // Remaining quantity in lot
	Price    float64 // Purchase price per unit
	ValueEUR float64 // EUR-converted value
}

// matchTrades matches BUY and SELL trades using FIFO to calculate closed P&L.
//
// Groups trades by symbol, sorts chronologically, and matches SELLs against oldest BUYs first.
// Returns array of closed trades with realized P&L.
//
// Args:
//
//	bucketTrades: All trades for the bucket
//	log: Logger for warnings (e.g., SELL exceeds BUY)
//
// Returns:
//
//	Array of ClosedTrade with matched buy-sell pairs
func matchTrades(bucketTrades []trading.Trade, log zerolog.Logger) []ClosedTrade {
	// Group trades by symbol
	tradesBySymbol := make(map[string][]trading.Trade)
	for _, trade := range bucketTrades {
		tradesBySymbol[trade.Symbol] = append(tradesBySymbol[trade.Symbol], trade)
	}

	var closedTrades []ClosedTrade

	// Process each symbol separately
	for symbol, trades := range tradesBySymbol {
		// Sort by executed_at (chronological order)
		sort.Slice(trades, func(i, j int) bool {
			return trades[i].ExecutedAt.Before(trades[j].ExecutedAt)
		})

		// FIFO queue for open positions
		var openPositions []PositionLot

		// Process trades chronologically
		for _, trade := range trades {
			if trade.Side.IsBuy() {
				// Add to open positions queue
				openPositions = append(openPositions, PositionLot{
					BuyDate:  trade.ExecutedAt.Format("2006-01-02 15:04:05"),
					Quantity: trade.Quantity,
					Price:    trade.Price,
					ValueEUR: getValueEUR(trade),
				})
			} else if trade.Side.IsSell() {
				remainingToSell := trade.Quantity
				sellPrice := trade.Price
				sellDate := trade.ExecutedAt.Format("2006-01-02 15:04:05")

				// Match against oldest lots first (FIFO)
				for len(openPositions) > 0 && remainingToSell > 0 {
					lot := &openPositions[0]

					if lot.Quantity <= remainingToSell {
						// Close entire lot
						pnl := (sellPrice - lot.Price) * lot.Quantity
						returnPct := (sellPrice - lot.Price) / lot.Price

						closedTrades = append(closedTrades, ClosedTrade{
							Symbol:     symbol,
							BuyDate:    lot.BuyDate,
							SellDate:   sellDate,
							Quantity:   lot.Quantity,
							BuyPrice:   lot.Price,
							SellPrice:  sellPrice,
							ProfitLoss: pnl,
							ReturnPct:  returnPct,
						})

						remainingToSell -= lot.Quantity
						openPositions = openPositions[1:] // Remove closed lot
					} else {
						// Partial match - close part of lot
						pnl := (sellPrice - lot.Price) * remainingToSell
						returnPct := (sellPrice - lot.Price) / lot.Price

						closedTrades = append(closedTrades, ClosedTrade{
							Symbol:     symbol,
							BuyDate:    lot.BuyDate,
							SellDate:   sellDate,
							Quantity:   remainingToSell,
							BuyPrice:   lot.Price,
							SellPrice:  sellPrice,
							ProfitLoss: pnl,
							ReturnPct:  returnPct,
						})

						lot.Quantity -= remainingToSell
						remainingToSell = 0
					}
				}

				// Log warning if SELL exceeds BUY (data inconsistency)
				if remainingToSell > 0 {
					log.Warn().
						Str("symbol", symbol).
						Float64("excess_quantity", remainingToSell).
						Str("sell_date", sellDate).
						Msg("SELL trade exceeds BUY quantity - possible data inconsistency")
				}
			}
		}
	}

	return closedTrades
}

// getValueEUR safely extracts EUR value from trade.
// Returns ValueEUR if set, otherwise calculates from Price * Quantity.
func getValueEUR(trade trading.Trade) float64 {
	if trade.ValueEUR != nil {
		return *trade.ValueEUR
	}
	// Fallback: assume EUR if not specified
	return trade.Price * trade.Quantity
}

// buildEquityCurve creates cumulative P&L curve from closed trades.
//
// Sorts trades by sell date and builds cumulative P&L starting from zero.
// Returns array with N+1 elements (0 = starting value, 1..N = after each trade).
//
// Args:
//
//	closedTrades: Array of closed trades
//
// Returns:
//
//	Equity curve as cumulative P&L (starts at 0.0)
func buildEquityCurve(closedTrades []ClosedTrade) []float64 {
	if len(closedTrades) == 0 {
		return []float64{}
	}

	// Sort by sell date (chronological)
	sort.Slice(closedTrades, func(i, j int) bool {
		return closedTrades[i].SellDate < closedTrades[j].SellDate
	})

	// Build cumulative P&L curve
	equityCurve := make([]float64, len(closedTrades)+1)
	equityCurve[0] = 0.0 // Start at zero

	cumulativePnL := 0.0
	for i, ct := range closedTrades {
		cumulativePnL += ct.ProfitLoss
		equityCurve[i+1] = cumulativePnL
	}

	return equityCurve
}

// calculateReturns extracts trade-level returns from closed trades.
//
// Returns array of return percentages (as decimals, e.g., 0.05 for 5%).
//
// Args:
//
//	closedTrades: Array of closed trades
//
// Returns:
//
//	Array of return percentages
func calculateReturns(closedTrades []ClosedTrade) []float64 {
	returns := make([]float64, len(closedTrades))
	for i, ct := range closedTrades {
		returns[i] = ct.ReturnPct
	}
	return returns
}

// calculateInitialCapital sums the cost basis of all BUY trades in closed positions.
//
// Calculates total capital invested by summing BuyPrice * Quantity for all closed trades.
//
// Args:
//
//	closedTrades: Array of closed trades
//
// Returns:
//
//	Total initial capital invested
func calculateInitialCapital(closedTrades []ClosedTrade) float64 {
	capital := 0.0
	for _, ct := range closedTrades {
		capital += ct.BuyPrice * ct.Quantity
	}
	return capital
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
// Calculates performance metrics from closed trades using FIFO matching algorithm.
// Returns nil if insufficient data (< 5 total trades or < 3 closed trades).
//
// Args:
//
//	bucketID: Bucket ID
//	settings: Satellite settings with risk parameters (EvaluationPeriodDays, RiskFreeRate, SortinoMAR)
//	balanceService: Balance service for current values
//	tradeRepo: Trade repository for fetching trade data
//	log: Logger
//
// Returns:
//
//	PerformanceMetrics object or nil if insufficient data
func CalculateBucketPerformance(
	bucketID string,
	settings *SatelliteSettings,
	balanceService *BalanceService,
	tradeRepo *trading.TradeRepository,
	log zerolog.Logger,
) (*PerformanceMetrics, error) {
	// Step 1: Calculate date range
	periodDays := settings.EvaluationPeriodDays
	endDate := time.Now().Format(time.RFC3339)
	startDate := time.Now().AddDate(0, 0, -periodDays).Format(time.RFC3339)

	// Step 2: Fetch trades in date range
	allTrades, err := tradeRepo.GetAllInRange(startDate, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch trades: %w", err)
	}

	// Step 3: Filter trades for this bucket
	var bucketTrades []trading.Trade
	for _, trade := range allTrades {
		if trade.BucketID == bucketID {
			bucketTrades = append(bucketTrades, trade)
		}
	}

	// Step 4: Check for insufficient data
	if len(bucketTrades) < 5 {
		log.Info().
			Str("bucket_id", bucketID).
			Int("trade_count", len(bucketTrades)).
			Msg("Insufficient trades for performance calculation")
		return nil, nil // Return nil like Python version
	}

	// Step 5: Match trades (FIFO)
	closedTrades := matchTrades(bucketTrades, log)

	if len(closedTrades) < 3 {
		log.Info().
			Str("bucket_id", bucketID).
			Int("closed_trade_count", len(closedTrades)).
			Msg("Insufficient closed trades for performance calculation")
		return nil, nil
	}

	// Step 6: Build equity curve (cumulative P&L)
	equityCurve := buildEquityCurve(closedTrades)

	// Step 7: Calculate returns (trade-level returns)
	returns := calculateReturns(closedTrades)

	// Step 8: Calculate total return
	initialCapital := calculateInitialCapital(closedTrades)
	totalPnL := equityCurve[len(equityCurve)-1]
	totalReturn := 0.0
	if initialCapital > 0 {
		totalReturn = (totalPnL / initialCapital) * 100.0
	}

	// Step 9: Calculate annualized return
	daysElapsed := float64(periodDays)
	annualizedReturn := 0.0
	if daysElapsed > 0 && len(returns) > 0 {
		totalReturnDecimal := totalReturn / 100.0
		yearsElapsed := daysElapsed / 365.0
		if totalReturnDecimal > -1.0 { // Avoid negative base in power
			annualizedReturn = (math.Pow(1.0+totalReturnDecimal, 1.0/yearsElapsed) - 1.0) * 100.0
		}
	}

	// Step 10: Calculate volatility
	volatility := stdDev(returns) * 100.0

	// Step 11: Calculate downside volatility
	var downsideReturns []float64
	for _, r := range returns {
		if r < 0 {
			downsideReturns = append(downsideReturns, r)
		}
	}
	downsideVolatility := stdDev(downsideReturns) * 100.0

	// Step 12: Calculate max drawdown
	maxDD, _, _ := CalculateMaxDrawdown(equityCurve)
	maxDrawdown := maxDD * 100.0

	// Step 13: Calculate Sharpe ratio
	sharpeRatio := CalculateSharpeRatio(returns, settings.RiskFreeRate)

	// Step 14: Calculate Sortino ratio
	sortinoRatio := CalculateSortinoRatio(returns, settings.RiskFreeRate, settings.SortinoMAR)

	// Step 15: Calculate Calmar ratio
	calmarRatio := CalculateCalmarRatio(annualizedReturn, maxDrawdown)

	// Step 16: Calculate trade statistics
	profitLosses := make([]float64, len(closedTrades))
	for i, ct := range closedTrades {
		profitLosses[i] = ct.ProfitLoss
	}

	winRate, winningTrades, losingTrades := CalculateWinRate(profitLosses)
	profitFactor := CalculateProfitFactor(profitLosses)

	// Step 17: Calculate win/loss details
	var wins, losses []float64
	for _, pnl := range profitLosses {
		if pnl > 0 {
			wins = append(wins, pnl)
		} else if pnl < 0 {
			losses = append(losses, pnl)
		}
	}

	avgWin := 0.0
	if len(wins) > 0 {
		avgWin = mean(wins)
	}

	avgLoss := 0.0
	if len(losses) > 0 {
		avgLoss = mean(losses)
	}

	largestWin := 0.0
	if len(wins) > 0 {
		for _, w := range wins {
			if w > largestWin {
				largestWin = w
			}
		}
	}

	largestLoss := 0.0
	if len(losses) > 0 {
		for _, l := range losses {
			if l < largestLoss {
				largestLoss = l
			}
		}
	}

	// Step 18: Populate PerformanceMetrics struct
	metrics := &PerformanceMetrics{
		BucketID:   bucketID,
		PeriodDays: periodDays,

		TotalReturn:      totalReturn,
		AnnualizedReturn: annualizedReturn,

		Volatility:         volatility,
		DownsideVolatility: downsideVolatility,
		MaxDrawdown:        maxDrawdown,

		SharpeRatio:  sharpeRatio,
		SortinoRatio: sortinoRatio,
		CalmarRatio:  calmarRatio,

		TotalTrades:   len(closedTrades),
		WinningTrades: winningTrades,
		LosingTrades:  losingTrades,
		WinRate:       winRate,
		ProfitFactor:  profitFactor,

		AvgWin:      avgWin,
		AvgLoss:     avgLoss,
		LargestWin:  largestWin,
		LargestLoss: largestLoss,

		StartDate:    startDate,
		EndDate:      endDate,
		CalculatedAt: time.Now().Format(time.RFC3339),
	}

	// Step 19: Calculate composite score
	metrics.CompositeScore = CalculateCompositeScore(metrics)

	// Step 20: Log results
	log.Info().
		Str("bucket_id", bucketID).
		Int("closed_trades", len(closedTrades)).
		Float64("total_return", totalReturn).
		Float64("sharpe", sharpeRatio).
		Float64("sortino", sortinoRatio).
		Float64("composite_score", metrics.CompositeScore).
		Msg("Bucket performance calculated")

	return metrics, nil
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
