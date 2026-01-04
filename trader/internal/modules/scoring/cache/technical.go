package cache

import (
	"context"
	"database/sql"
	"encoding/json"
	"time"

	"github.com/aristath/arduino-trader/pkg/formulas"
	"github.com/rs/zerolog"
)

// TechnicalCache provides caching for technical calculations
// Faithful translation from Python: app/modules/scoring/domain/caching/technical.py
type TechnicalCache struct {
	db  *sql.DB
	log zerolog.Logger
}

// NewTechnicalCache creates a new technical cache instance
func NewTechnicalCache(db *sql.DB, log zerolog.Logger) *TechnicalCache {
	return &TechnicalCache{
		db:  db,
		log: log.With().Str("component", "technical_cache").Logger(),
	}
}

// CachedMetric represents a cached calculation result
type CachedMetric struct {
	Symbol       string
	MetricType   string
	Period       int
	Value        interface{}
	CalculatedAt time.Time
}

// GetEMA retrieves EMA from cache or calculates and stores it
// Args:
//
//	symbol: Security symbol
//	prices: Daily closing prices
//	period: EMA period (e.g., 50, 200)
//
// Returns:
//
//	EMA value or nil if insufficient data
func (tc *TechnicalCache) GetEMA(ctx context.Context, symbol string, prices []float64, period int) *float64 {
	// Try to get from cache
	cached := tc.getCachedValue(ctx, symbol, "ema", period)
	if cached != nil {
		if val, ok := cached.(float64); ok {
			return &val
		}
	}

	// Calculate
	ema := formulas.CalculateEMA(prices, period)
	if ema == nil {
		return nil
	}

	// Store in cache
	tc.setCachedValue(ctx, symbol, "ema", period, *ema)

	return ema
}

// GetRSI retrieves RSI from cache or calculates and stores it
// Args:
//
//	symbol: Security symbol
//	prices: Daily closing prices
//	period: RSI period (typically 14)
//
// Returns:
//
//	RSI value or nil if insufficient data
func (tc *TechnicalCache) GetRSI(ctx context.Context, symbol string, prices []float64, period int) *float64 {
	// Try to get from cache
	cached := tc.getCachedValue(ctx, symbol, "rsi", period)
	if cached != nil {
		if val, ok := cached.(float64); ok {
			return &val
		}
	}

	// Calculate
	rsi := formulas.CalculateRSI(prices, period)
	if rsi == nil {
		return nil
	}

	// Store in cache
	tc.setCachedValue(ctx, symbol, "rsi", period, *rsi)

	return rsi
}

// BollingerBandsResult holds Bollinger Bands values
type BollingerBandsResult struct {
	Upper    float64 `json:"upper"`
	Middle   float64 `json:"middle"`
	Lower    float64 `json:"lower"`
	Position float64 `json:"position"`
}

// GetBollingerBands retrieves Bollinger Bands from cache or calculates and stores them
// Args:
//
//	symbol: Security symbol
//	prices: Daily closing prices
//	period: Moving average period (typically 20)
//	stdDev: Number of standard deviations (typically 2.0)
//
// Returns:
//
//	BollingerBandsResult or nil if insufficient data
func (tc *TechnicalCache) GetBollingerBands(ctx context.Context, symbol string, prices []float64, period int, stdDev float64) *BollingerBandsResult {
	// Try to get from cache
	cached := tc.getCachedValue(ctx, symbol, "bollinger", period)
	if cached != nil {
		// Cached value should be JSON
		if jsonData, ok := cached.(string); ok {
			var result BollingerBandsResult
			if err := json.Unmarshal([]byte(jsonData), &result); err == nil {
				return &result
			}
		}
	}

	// Calculate
	if len(prices) < period {
		return nil
	}

	// Calculate Bollinger Bands and position
	bollingerPos := formulas.CalculateBollingerPosition(prices, period, stdDev)
	if bollingerPos == nil {
		return nil
	}

	result := &BollingerBandsResult{
		Upper:    bollingerPos.Bands.Upper,
		Middle:   bollingerPos.Bands.Middle,
		Lower:    bollingerPos.Bands.Lower,
		Position: bollingerPos.Position,
	}

	// Store in cache as JSON
	jsonData, err := json.Marshal(result)
	if err == nil {
		tc.setCachedValue(ctx, symbol, "bollinger", period, string(jsonData))
	}

	return result
}

// GetSharpeRatio retrieves Sharpe ratio from cache or calculates and stores it
// Args:
//
//	symbol: Security symbol
//	prices: Daily closing prices
//	riskFreeRate: Annual risk-free rate (e.g., 0.02 for 2%)
//
// Returns:
//
//	Sharpe ratio or nil if insufficient data
func (tc *TechnicalCache) GetSharpeRatio(ctx context.Context, symbol string, prices []float64, riskFreeRate float64) *float64 {
	// Try to get from cache (use period=0 for non-period metrics)
	cached := tc.getCachedValue(ctx, symbol, "sharpe", 0)
	if cached != nil {
		if val, ok := cached.(float64); ok {
			return &val
		}
	}

	// Calculate
	sharpe := formulas.CalculateSharpeFromPrices(prices, riskFreeRate)
	if sharpe == nil {
		return nil
	}

	// Store in cache
	tc.setCachedValue(ctx, symbol, "sharpe", 0, *sharpe)

	return sharpe
}

// GetMaxDrawdown retrieves max drawdown from cache or calculates and stores it
// Args:
//
//	symbol: Security symbol
//	prices: Daily closing prices
//
// Returns:
//
//	Max drawdown (negative value) or nil if insufficient data
func (tc *TechnicalCache) GetMaxDrawdown(ctx context.Context, symbol string, prices []float64) *float64 {
	// Try to get from cache
	cached := tc.getCachedValue(ctx, symbol, "max_drawdown", 0)
	if cached != nil {
		if val, ok := cached.(float64); ok {
			return &val
		}
	}

	// Calculate
	drawdown := formulas.CalculateMaxDrawdown(prices)
	if drawdown == nil {
		return nil
	}

	// Store in cache
	tc.setCachedValue(ctx, symbol, "max_drawdown", 0, *drawdown)

	return drawdown
}

// Get52WeekHigh retrieves 52-week high from cache or calculates and stores it
// Args:
//
//	symbol: Security symbol
//	prices: Daily closing prices (at least 252 trading days for full year)
//
// Returns:
//
//	52-week high price or nil if insufficient data
func (tc *TechnicalCache) Get52WeekHigh(ctx context.Context, symbol string, prices []float64) *float64 {
	// Try to get from cache
	cached := tc.getCachedValue(ctx, symbol, "52w_high", 0)
	if cached != nil {
		if val, ok := cached.(float64); ok {
			return &val
		}
	}

	// Calculate
	high := formulas.Calculate52WeekHigh(prices)
	if high == nil {
		return nil
	}

	// Store in cache
	tc.setCachedValue(ctx, symbol, "52w_high", 0, *high)

	return high
}

// Get52WeekLow retrieves 52-week low from cache or calculates and stores it
// Args:
//
//	symbol: Security symbol
//	prices: Daily closing prices (at least 252 trading days for full year)
//
// Returns:
//
//	52-week low price or nil if insufficient data
func (tc *TechnicalCache) Get52WeekLow(ctx context.Context, symbol string, prices []float64) *float64 {
	// Try to get from cache
	cached := tc.getCachedValue(ctx, symbol, "52w_low", 0)
	if cached != nil {
		if val, ok := cached.(float64); ok {
			return &val
		}
	}

	// Calculate
	low := formulas.Calculate52WeekLow(prices)
	if low == nil {
		return nil
	}

	// Store in cache
	tc.setCachedValue(ctx, symbol, "52w_low", 0, *low)

	return low
}

// InvalidateCache removes cached values for a symbol
// Useful when price data is updated
func (tc *TechnicalCache) InvalidateCache(ctx context.Context, symbol string) error {
	query := `DELETE FROM calculations WHERE symbol = ?`
	_, err := tc.db.ExecContext(ctx, query, symbol)
	if err != nil {
		tc.log.Error().Err(err).Str("symbol", symbol).Msg("Failed to invalidate cache")
		return err
	}
	return nil
}

// InvalidateMetric removes a specific cached metric for a symbol
func (tc *TechnicalCache) InvalidateMetric(ctx context.Context, symbol, metricType string, period int) error {
	query := `DELETE FROM calculations WHERE symbol = ? AND metric_type = ? AND period = ?`
	_, err := tc.db.ExecContext(ctx, query, symbol, metricType, period)
	if err != nil {
		tc.log.Error().
			Err(err).
			Str("symbol", symbol).
			Str("metric_type", metricType).
			Int("period", period).
			Msg("Failed to invalidate metric")
		return err
	}
	return nil
}

// getCachedValue retrieves a cached value from the database
// Returns nil if not found or expired
func (tc *TechnicalCache) getCachedValue(ctx context.Context, symbol, metricType string, period int) interface{} {
	query := `
		SELECT value, calculated_at
		FROM calculations
		WHERE symbol = ? AND metric_type = ? AND period = ?
		ORDER BY calculated_at DESC
		LIMIT 1
	`

	var value string
	var calculatedAt time.Time
	err := tc.db.QueryRowContext(ctx, query, symbol, metricType, period).Scan(&value, &calculatedAt)
	if err != nil {
		if err != sql.ErrNoRows {
			tc.log.Error().
				Err(err).
				Str("symbol", symbol).
				Str("metric_type", metricType).
				Int("period", period).
				Msg("Failed to get cached value")
		}
		return nil
	}

	// Check if cache is still valid (24 hours)
	if time.Since(calculatedAt) > 24*time.Hour {
		return nil
	}

	// Try to parse as float64 first (most common case)
	var floatVal float64
	if err := json.Unmarshal([]byte(value), &floatVal); err == nil {
		return floatVal
	}

	// Return as string (for complex types like Bollinger Bands)
	return value
}

// setCachedValue stores a calculated value in the database
func (tc *TechnicalCache) setCachedValue(ctx context.Context, symbol, metricType string, period int, value interface{}) {
	// Convert value to JSON
	jsonData, err := json.Marshal(value)
	if err != nil {
		tc.log.Error().
			Err(err).
			Str("symbol", symbol).
			Str("metric_type", metricType).
			Msg("Failed to marshal value")
		return
	}

	query := `
		INSERT INTO calculations (symbol, metric_type, period, value, calculated_at)
		VALUES (?, ?, ?, ?, ?)
		ON CONFLICT(symbol, metric_type, period)
		DO UPDATE SET value = excluded.value, calculated_at = excluded.calculated_at
	`

	_, err = tc.db.ExecContext(ctx, query, symbol, metricType, period, string(jsonData), time.Now())
	if err != nil {
		tc.log.Error().
			Err(err).
			Str("symbol", symbol).
			Str("metric_type", metricType).
			Int("period", period).
			Msg("Failed to cache value")
	}
}
