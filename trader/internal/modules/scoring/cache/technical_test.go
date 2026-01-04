package cache

import (
	"context"
	"database/sql"
	"testing"

	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// setupTestDB creates an in-memory SQLite database for testing
func setupTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)

	// Create calculations table
	_, err = db.Exec(`
		CREATE TABLE calculations (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			symbol TEXT NOT NULL,
			metric_type TEXT NOT NULL,
			period INTEGER NOT NULL,
			value TEXT NOT NULL,
			calculated_at TIMESTAMP NOT NULL,
			UNIQUE(symbol, metric_type, period)
		)
	`)
	require.NoError(t, err)

	return db
}

func TestGetEMA(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	cache := NewTechnicalCache(db, zerolog.Nop())
	ctx := context.Background()

	prices := []float64{100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 110, 112, 111, 113, 115}

	// First call should calculate and cache
	ema1 := cache.GetEMA(ctx, "AAPL", prices, 10)
	require.NotNil(t, ema1)
	assert.Greater(t, *ema1, 0.0)

	// Second call should retrieve from cache
	ema2 := cache.GetEMA(ctx, "AAPL", prices, 10)
	require.NotNil(t, ema2)
	assert.Equal(t, *ema1, *ema2)

	// Different period should recalculate
	ema3 := cache.GetEMA(ctx, "AAPL", prices, 5)
	require.NotNil(t, ema3)
	assert.NotEqual(t, *ema1, *ema3)
}

func TestGetRSI(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	cache := NewTechnicalCache(db, zerolog.Nop())
	ctx := context.Background()

	prices := []float64{
		44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
		45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64,
	}

	// First call should calculate and cache
	rsi1 := cache.GetRSI(ctx, "AAPL", prices, 14)
	require.NotNil(t, rsi1)
	assert.Greater(t, *rsi1, 0.0)
	assert.LessOrEqual(t, *rsi1, 100.0)

	// Second call should retrieve from cache
	rsi2 := cache.GetRSI(ctx, "AAPL", prices, 14)
	require.NotNil(t, rsi2)
	assert.Equal(t, *rsi1, *rsi2)
}

func TestGetBollingerBands(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	cache := NewTechnicalCache(db, zerolog.Nop())
	ctx := context.Background()

	prices := []float64{
		100, 102, 101, 103, 105, 104, 106, 108, 107, 109,
		110, 112, 111, 113, 115, 114, 116, 118, 117, 119, 120,
	}

	// First call should calculate and cache
	bb1 := cache.GetBollingerBands(ctx, "AAPL", prices, 20, 2.0)
	require.NotNil(t, bb1)
	assert.Greater(t, bb1.Upper, bb1.Middle)
	assert.Greater(t, bb1.Middle, bb1.Lower)
	assert.GreaterOrEqual(t, bb1.Position, 0.0)
	assert.LessOrEqual(t, bb1.Position, 1.0)

	// Second call should retrieve from cache
	bb2 := cache.GetBollingerBands(ctx, "AAPL", prices, 20, 2.0)
	require.NotNil(t, bb2)
	assert.Equal(t, bb1.Upper, bb2.Upper)
	assert.Equal(t, bb1.Middle, bb2.Middle)
	assert.Equal(t, bb1.Lower, bb2.Lower)
	assert.Equal(t, bb1.Position, bb2.Position)
}

func TestGetSharpeRatio(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	cache := NewTechnicalCache(db, zerolog.Nop())
	ctx := context.Background()

	// Prices with positive returns
	prices := []float64{
		100, 102, 104, 103, 105, 107, 106, 108, 110, 112,
		111, 113, 115, 114, 116, 118, 117, 119, 121, 120,
	}

	// First call should calculate and cache
	sharpe1 := cache.GetSharpeRatio(ctx, "AAPL", prices, 0.02)
	require.NotNil(t, sharpe1)

	// Second call should retrieve from cache
	sharpe2 := cache.GetSharpeRatio(ctx, "AAPL", prices, 0.02)
	require.NotNil(t, sharpe2)
	assert.Equal(t, *sharpe1, *sharpe2)
}

func TestGetMaxDrawdown(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	cache := NewTechnicalCache(db, zerolog.Nop())
	ctx := context.Background()

	// Prices with a drawdown
	prices := []float64{100, 110, 105, 115, 100, 120, 110, 130}

	// First call should calculate and cache
	dd1 := cache.GetMaxDrawdown(ctx, "AAPL", prices)
	require.NotNil(t, dd1)
	assert.Less(t, *dd1, 0.0) // Drawdown is negative

	// Second call should retrieve from cache
	dd2 := cache.GetMaxDrawdown(ctx, "AAPL", prices)
	require.NotNil(t, dd2)
	assert.Equal(t, *dd1, *dd2)
}

func TestGet52WeekHigh(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	cache := NewTechnicalCache(db, zerolog.Nop())
	ctx := context.Background()

	// Create 252+ trading days of prices
	prices := make([]float64, 260)
	for i := range prices {
		prices[i] = 100.0 + float64(i%20)
	}
	prices[100] = 150.0 // Peak somewhere in the middle

	// First call should calculate and cache
	high1 := cache.Get52WeekHigh(ctx, "AAPL", prices)
	require.NotNil(t, high1)
	assert.Equal(t, 150.0, *high1)

	// Second call should retrieve from cache
	high2 := cache.Get52WeekHigh(ctx, "AAPL", prices)
	require.NotNil(t, high2)
	assert.Equal(t, *high1, *high2)
}

func TestGet52WeekLow(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	cache := NewTechnicalCache(db, zerolog.Nop())
	ctx := context.Background()

	// Create 252+ trading days of prices
	prices := make([]float64, 260)
	for i := range prices {
		prices[i] = 100.0 + float64(i%20)
	}
	prices[100] = 50.0 // Trough somewhere in the middle

	// First call should calculate and cache
	low1 := cache.Get52WeekLow(ctx, "AAPL", prices)
	require.NotNil(t, low1)
	assert.Equal(t, 50.0, *low1)

	// Second call should retrieve from cache
	low2 := cache.Get52WeekLow(ctx, "AAPL", prices)
	require.NotNil(t, low2)
	assert.Equal(t, *low1, *low2)
}

func TestInvalidateCache(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	cache := NewTechnicalCache(db, zerolog.Nop())
	ctx := context.Background()

	prices := []float64{100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 110}

	// Need enough prices for RSI calculation
	rsiPrices := []float64{
		44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
		45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64,
	}

	// Cache some values
	ema1 := cache.GetEMA(ctx, "AAPL", prices, 10)
	require.NotNil(t, ema1)

	rsi1 := cache.GetRSI(ctx, "AAPL", rsiPrices, 14)
	require.NotNil(t, rsi1)

	// Invalidate cache
	err := cache.InvalidateCache(ctx, "AAPL")
	require.NoError(t, err)

	// Next call should recalculate (we can't easily verify this without mocking,
	// but we can verify it doesn't error)
	ema2 := cache.GetEMA(ctx, "AAPL", prices, 10)
	require.NotNil(t, ema2)
}

func TestInvalidateMetric(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	cache := NewTechnicalCache(db, zerolog.Nop())
	ctx := context.Background()

	prices := []float64{100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 110, 112}

	// Cache EMA for period 10
	ema1 := cache.GetEMA(ctx, "AAPL", prices, 10)
	require.NotNil(t, ema1)

	// Cache EMA for period 5
	ema2 := cache.GetEMA(ctx, "AAPL", prices, 5)
	require.NotNil(t, ema2)

	// Invalidate only period 10
	err := cache.InvalidateMetric(ctx, "AAPL", "ema", 10)
	require.NoError(t, err)

	// Period 10 should recalculate, period 5 should use cache
	ema3 := cache.GetEMA(ctx, "AAPL", prices, 10)
	require.NotNil(t, ema3)

	ema4 := cache.GetEMA(ctx, "AAPL", prices, 5)
	require.NotNil(t, ema4)
	assert.Equal(t, *ema2, *ema4) // Period 5 still cached
}

func TestCacheExpiration(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	cache := NewTechnicalCache(db, zerolog.Nop())
	ctx := context.Background()

	prices := []float64{100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 110}

	// Cache a value
	ema1 := cache.GetEMA(ctx, "AAPL", prices, 10)
	require.NotNil(t, ema1)

	// Manually set the calculated_at to 25 hours ago to simulate expiration
	_, err := db.Exec(`
		UPDATE calculations
		SET calculated_at = datetime('now', '-25 hours')
		WHERE symbol = 'AAPL' AND metric_type = 'ema' AND period = 10
	`)
	require.NoError(t, err)

	// Next call should recalculate (cache expired)
	ema2 := cache.GetEMA(ctx, "AAPL", prices, 10)
	require.NotNil(t, ema2)
	// Value should be recalculated, so timestamps differ but values same
	assert.Equal(t, *ema1, *ema2)
}

func TestMultipleSymbols(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	cache := NewTechnicalCache(db, zerolog.Nop())
	ctx := context.Background()

	prices1 := []float64{100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 110}
	prices2 := []float64{50, 51, 52, 51, 53, 54, 53, 55, 56, 55, 57}

	// Cache for AAPL
	ema1 := cache.GetEMA(ctx, "AAPL", prices1, 10)
	require.NotNil(t, ema1)

	// Cache for MSFT
	ema2 := cache.GetEMA(ctx, "MSFT", prices2, 10)
	require.NotNil(t, ema2)

	// Should be different values
	assert.NotEqual(t, *ema1, *ema2)

	// Invalidate AAPL shouldn't affect MSFT
	err := cache.InvalidateCache(ctx, "AAPL")
	require.NoError(t, err)

	// MSFT should still be cached
	ema3 := cache.GetEMA(ctx, "MSFT", prices2, 10)
	require.NotNil(t, ema3)
	assert.Equal(t, *ema2, *ema3)
}

func TestInsufficientData(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	cache := NewTechnicalCache(db, zerolog.Nop())
	ctx := context.Background()

	// Few prices for testing
	prices := []float64{100, 102, 101}

	// EMA with insufficient data falls back to SMA (mean)
	ema := cache.GetEMA(ctx, "AAPL", prices, 10)
	assert.NotNil(t, ema)               // Falls back to mean
	assert.InDelta(t, 101.0, *ema, 0.1) // Mean of 100, 102, 101

	// Not enough prices for RSI 14
	rsi := cache.GetRSI(ctx, "AAPL", prices, 14)
	assert.Nil(t, rsi)

	// Not enough prices for Bollinger Bands
	bb := cache.GetBollingerBands(ctx, "AAPL", prices, 20, 2.0)
	assert.Nil(t, bb)
}

func TestConcurrentAccess(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	cache := NewTechnicalCache(db, zerolog.Nop())
	ctx := context.Background()

	prices := []float64{100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 110, 112, 111, 113, 115}

	// Simulate concurrent access
	done := make(chan bool, 10)
	for i := 0; i < 10; i++ {
		go func() {
			ema := cache.GetEMA(ctx, "AAPL", prices, 10)
			assert.NotNil(t, ema)
			done <- true
		}()
	}

	// Wait for all goroutines
	for i := 0; i < 10; i++ {
		<-done
	}
}

func TestCacheUpsert(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	cache := NewTechnicalCache(db, zerolog.Nop())
	ctx := context.Background()

	prices1 := []float64{100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 110}
	prices2 := []float64{100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 110, 112}

	// First calculation
	ema1 := cache.GetEMA(ctx, "AAPL", prices1, 10)
	require.NotNil(t, ema1)

	// Invalidate and recalculate with more data
	err := cache.InvalidateMetric(ctx, "AAPL", "ema", 10)
	require.NoError(t, err)

	ema2 := cache.GetEMA(ctx, "AAPL", prices2, 10)
	require.NotNil(t, ema2)

	// Values should be different (more data)
	assert.NotEqual(t, *ema1, *ema2)

	// Check that only one record exists (upsert worked)
	var count int
	err = db.QueryRow(`
		SELECT COUNT(*)
		FROM calculations
		WHERE symbol = 'AAPL' AND metric_type = 'ema' AND period = 10
	`).Scan(&count)
	require.NoError(t, err)
	assert.Equal(t, 1, count)
}

func TestGetCachedValue_NonexistentSymbol(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	cache := NewTechnicalCache(db, zerolog.Nop())
	ctx := context.Background()

	// Try to get value for symbol that was never cached
	val := cache.getCachedValue(ctx, "NONEXISTENT", "ema", 10)
	assert.Nil(t, val)
}

func TestSetCachedValue_InvalidJSON(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	cache := NewTechnicalCache(db, zerolog.Nop())
	ctx := context.Background()

	// Try to cache a value that can't be marshaled (function)
	// This should log an error but not crash
	cache.setCachedValue(ctx, "AAPL", "test", 0, func() {})

	// Verify nothing was cached
	val := cache.getCachedValue(ctx, "AAPL", "test", 0)
	assert.Nil(t, val)
}
