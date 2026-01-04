package portfolio

import (
	"time"

	"github.com/rs/zerolog"
)

// MarketRegime represents the current market condition
type MarketRegime string

const (
	MarketRegimeBull     MarketRegime = "bull"
	MarketRegimeBear     MarketRegime = "bear"
	MarketRegimeSideways MarketRegime = "sideways"
)

// MarketRegimeDetector analyzes market conditions to determine regime
type MarketRegimeDetector struct {
	log zerolog.Logger
}

// NewMarketRegimeDetector creates a new market regime detector
func NewMarketRegimeDetector(log zerolog.Logger) *MarketRegimeDetector {
	return &MarketRegimeDetector{
		log: log.With().Str("component", "market_regime_detector").Logger(),
	}
}

// DetectRegime analyzes portfolio performance to determine market regime
// Uses a simple heuristic based on:
// - Recent portfolio return trend (average daily return)
// - Volatility (standard deviation of daily returns)
// - Drawdown (max peak-to-trough decline)
//
// Parameters assume DAILY returns (not annualized):
// - portfolioReturn: average daily return over the window
// - volatility: standard deviation of daily returns
// - maxDrawdown: maximum drawdown as a negative fraction
func (d *MarketRegimeDetector) DetectRegime(portfolioReturn, volatility, maxDrawdown float64) MarketRegime {
	// Bull market criteria (based on daily returns):
	// - Average daily return > 0.05% (roughly 18% annualized if compounded)
	// - Maximum drawdown less than 10%
	// - Not experiencing extreme volatility
	if portfolioReturn > 0.0005 && maxDrawdown > -0.10 && volatility < 0.04 {
		d.log.Debug().
			Float64("daily_return", portfolioReturn).
			Float64("volatility", volatility).
			Float64("drawdown", maxDrawdown).
			Msg("Detected bull market regime")
		return MarketRegimeBull
	}

	// Bear market criteria (based on daily returns):
	// - Average daily return < -0.05% (roughly -18% annualized)
	// - OR experiencing large drawdown (> 12%)
	// - OR very high volatility (> 3% daily std dev)
	if portfolioReturn < -0.0005 || maxDrawdown < -0.12 || volatility > 0.03 {
		d.log.Debug().
			Float64("daily_return", portfolioReturn).
			Float64("volatility", volatility).
			Float64("drawdown", maxDrawdown).
			Msg("Detected bear market regime")
		return MarketRegimeBear
	}

	// Sideways market: everything else (choppy, range-bound)
	// - Near-zero average returns
	// - Moderate volatility
	// - Moderate drawdowns
	d.log.Debug().
		Float64("daily_return", portfolioReturn).
		Float64("volatility", volatility).
		Float64("drawdown", maxDrawdown).
		Msg("Detected sideways market regime")
	return MarketRegimeSideways
}

// DetectRegimeFromHistory analyzes historical returns to determine regime
// This method looks at the last N days of returns to determine the current regime
func (d *MarketRegimeDetector) DetectRegimeFromHistory(returns []float64, window int) MarketRegime {
	if len(returns) < window {
		d.log.Warn().
			Int("returns_len", len(returns)).
			Int("window", window).
			Msg("Insufficient data for regime detection, defaulting to sideways")
		return MarketRegimeSideways
	}

	// Calculate metrics over the window
	recentReturns := returns[len(returns)-window:]

	avgReturn := calculateMean(recentReturns)
	volatility := calculateStdDev(recentReturns)
	drawdown := calculateMaxDrawdown(recentReturns)

	return d.DetectRegime(avgReturn, volatility, drawdown)
}

// DetectRegimeFromTimeSeries analyzes time series data with timestamps
func (d *MarketRegimeDetector) DetectRegimeFromTimeSeries(
	timestamps []time.Time,
	values []float64,
	windowDays int,
) MarketRegime {
	if len(timestamps) != len(values) {
		d.log.Error().
			Int("timestamps_len", len(timestamps)).
			Int("values_len", len(values)).
			Msg("Mismatched timestamps and values length")
		return MarketRegimeSideways
	}

	if len(values) == 0 {
		d.log.Warn().Msg("No data provided for regime detection")
		return MarketRegimeSideways
	}

	// Calculate daily returns
	returns := make([]float64, 0, len(values)-1)
	for i := 1; i < len(values); i++ {
		if values[i-1] != 0 {
			dailyReturn := (values[i] - values[i-1]) / values[i-1]
			returns = append(returns, dailyReturn)
		}
	}

	// Use the window for detection
	window := windowDays
	if window > len(returns) {
		window = len(returns)
	}

	return d.DetectRegimeFromHistory(returns, window)
}

// Helper functions

func calculateMean(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}

	sum := 0.0
	for _, v := range values {
		sum += v
	}
	return sum / float64(len(values))
}

func calculateStdDev(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}

	mean := calculateMean(values)
	sumSquaredDiff := 0.0
	for _, v := range values {
		diff := v - mean
		sumSquaredDiff += diff * diff
	}
	variance := sumSquaredDiff / float64(len(values))
	return sqrt(variance)
}

func sqrt(x float64) float64 {
	// Simple Newton's method for square root
	if x == 0 {
		return 0
	}
	z := x
	for i := 0; i < 10; i++ {
		z = (z + x/z) / 2
	}
	return z
}

func calculateMaxDrawdown(returns []float64) float64 {
	if len(returns) == 0 {
		return 0
	}

	// Calculate cumulative returns
	cumulative := 1.0
	peak := 1.0
	maxDrawdown := 0.0

	for _, r := range returns {
		cumulative *= (1 + r)
		if cumulative > peak {
			peak = cumulative
		}
		drawdown := (cumulative - peak) / peak
		if drawdown < maxDrawdown {
			maxDrawdown = drawdown
		}
	}

	return maxDrawdown
}
