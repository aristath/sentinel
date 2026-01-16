package market_regime

import (
	"database/sql"
	"os"
	"testing"
	"time"

	"github.com/aristath/sentinel/internal/modules/universe"
	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func setupMarketIndexTestDB(t *testing.T) (*sql.DB, *sql.DB, *universe.HistoryDB) {
	// Create temporary databases
	universeFile, err := os.CreateTemp("", "test_universe_*.db")
	require.NoError(t, err)
	universeFile.Close()

	historyFile, err := os.CreateTemp("", "test_history_*.db")
	require.NoError(t, err)
	historyFile.Close()

	universeDB, err := sql.Open("sqlite3", universeFile.Name())
	require.NoError(t, err)

	historyDB, err := sql.Open("sqlite3", historyFile.Name())
	require.NoError(t, err)

	// Create universe schema with JSON storage (migration 038)
	_, err = universeDB.Exec(`
		CREATE TABLE IF NOT EXISTS securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			data TEXT NOT NULL,
			last_synced INTEGER
		) STRICT;
		CREATE INDEX IF NOT EXISTS idx_securities_symbol ON securities(symbol);
	`)
	require.NoError(t, err)

	// Create history schema
	_, err = historyDB.Exec(`
		CREATE TABLE IF NOT EXISTS daily_prices (
			isin TEXT NOT NULL,
			date INTEGER NOT NULL,
			open REAL NOT NULL,
			high REAL NOT NULL,
			low REAL NOT NULL,
			close REAL NOT NULL,
			volume INTEGER,
			adjusted_close REAL,
			PRIMARY KEY (isin, date)
		);
		CREATE INDEX IF NOT EXISTS idx_prices_isin_date ON daily_prices(isin, date DESC);
	`)
	require.NoError(t, err)

	t.Cleanup(func() {
		universeDB.Close()
		historyDB.Close()
		os.Remove(universeFile.Name())
		os.Remove(historyFile.Name())
	})

	// Create HistoryDB wrapper (nil filter for tests - no filtering)
	log := zerolog.New(nil).Level(zerolog.Disabled)
	historyDBClient := universe.NewHistoryDB(historyDB, nil, log)

	return universeDB, historyDB, historyDBClient
}

// setupTestIndices creates valid Tradernet indices in the test database
func setupTestIndices(t *testing.T, universeDB *sql.DB) {
	// Create indices matching the known indices from index_discovery.go
	indices := []struct {
		symbol string
		name   string
	}{
		{"SP500.IDX", "S&P 500"},
		{"NASDAQ.IDX", "NASDAQ Composite"},
		{"DAX.IDX", "DAX (Germany)"},
		{"FTSE.IDX", "FTSE 100 (UK)"},
		{"HSI.IDX", "Hang Seng Index"},
	}

	for _, idx := range indices {
		isin := "INDEX-" + idx.symbol
		_, err := universeDB.Exec(`
			INSERT OR REPLACE INTO securities (isin, symbol, data, last_synced)
			VALUES (?, ?, json_object('name', ?, 'product_type', 'INDEX'), NULL)
		`, isin, idx.symbol, idx.name)
		require.NoError(t, err)
	}
}

// setupTestPrices creates test price data for indices
func setupTestPrices(t *testing.T, historyDB *sql.DB, symbols []string, days int, dailyReturn float64) {
	now := time.Now()

	for i := 0; i < days; i++ {
		dateTime := now.AddDate(0, 0, -days+i)
		dateUnix := time.Date(dateTime.Year(), dateTime.Month(), dateTime.Day(), 0, 0, 0, 0, time.UTC).Unix()

		for _, symbol := range symbols {
			isin := "INDEX-" + symbol
			// Price grows by dailyReturn each day
			price := 1000.0 * (1.0 + float64(i)*dailyReturn)
			_, err := historyDB.Exec(`
				INSERT OR REPLACE INTO daily_prices (isin, date, open, high, low, close, volume)
				VALUES (?, ?, ?, ?, ?, ?, ?)
			`, isin, dateUnix, price, price*1.01, price*0.99, price, 1000000)
			require.NoError(t, err)
		}
	}
}

func TestGetMarketReturns(t *testing.T) {
	universeDB, historyDB, historyDBClient := setupMarketIndexTestDB(t)
	log := zerolog.Nop()
	securityRepo := universe.NewSecurityRepository(universeDB, log)
	service := NewMarketIndexService(securityRepo, historyDBClient, nil, log)

	// Setup indices with valid Tradernet symbols
	setupTestIndices(t, universeDB)

	// Setup price data for indices across all regions
	allSymbols := []string{
		"SP500.IDX", "NASDAQ.IDX", // US
		"DAX.IDX", "FTSE.IDX", // EU
		"HSI.IDX", // ASIA
	}
	setupTestPrices(t, historyDB, allSymbols, 30, 0.001) // 0.1% daily return

	t.Run("Returns composite market returns for regime detection", func(t *testing.T) {
		returns, err := service.GetMarketReturns(20)
		require.NoError(t, err)
		require.NotEmpty(t, returns, "Should return market returns")

		// Should have returns for the requested days (minus 1 for return calculation)
		assert.LessOrEqual(t, len(returns), 20, "Should not exceed requested days")
		assert.Greater(t, len(returns), 0, "Should have some returns")

		// Returns should be reasonable (small daily returns)
		for _, ret := range returns {
			assert.Greater(t, ret, -0.1, "Daily return should not be extreme negative")
			assert.Less(t, ret, 0.1, "Daily return should not be extreme positive")
		}
	})

	t.Run("Combines returns from all regions", func(t *testing.T) {
		returns, err := service.GetMarketReturns(10)
		require.NoError(t, err)
		require.NotEmpty(t, returns)

		// All returns should be positive (since all indices have positive daily returns)
		for _, ret := range returns {
			assert.GreaterOrEqual(t, ret, 0.0, "Should have positive composite returns when all indices rise")
		}
	})

	t.Run("Handles insufficient data gracefully", func(t *testing.T) {
		// Request more days than available
		returns, err := service.GetMarketReturns(100)
		if err != nil {
			assert.Contains(t, err.Error(), "insufficient", "Should indicate insufficient data")
		} else {
			assert.LessOrEqual(t, len(returns), 30, "Should return available data only")
		}
	})
}

func TestGetMarketReturns_PartialRegionData(t *testing.T) {
	universeDB, historyDB, historyDBClient := setupMarketIndexTestDB(t)
	log := zerolog.Nop()
	securityRepo := universe.NewSecurityRepository(universeDB, log)
	service := NewMarketIndexService(securityRepo, historyDBClient, nil, log)

	// Setup indices
	setupTestIndices(t, universeDB)

	// Only setup data for US indices (not EU or ASIA)
	usSymbols := []string{"SP500.IDX", "NASDAQ.IDX"}
	setupTestPrices(t, historyDB, usSymbols, 30, 0.001)

	t.Run("Works with partial region data", func(t *testing.T) {
		returns, err := service.GetMarketReturns(20)
		// Should either succeed with available data or return an error
		if err == nil {
			assert.NotEmpty(t, returns, "Should return data from available regions")
		}
		// If it errors, that's also acceptable - no regions with data means no returns
	})
}

func TestGetReturnsForRegion(t *testing.T) {
	universeDB, historyDB, historyDBClient := setupMarketIndexTestDB(t)
	log := zerolog.Nop()
	securityRepo := universe.NewSecurityRepository(universeDB, log)
	service := NewMarketIndexService(securityRepo, historyDBClient, nil, log)

	// Setup indices
	setupTestIndices(t, universeDB)

	// Setup different returns for different regions
	// US: +0.2% per day (bullish)
	setupTestPrices(t, historyDB, []string{"SP500.IDX", "NASDAQ.IDX"}, 30, 0.002)

	// EU: -0.1% per day (bearish) - need to recreate with different rate
	now := time.Now()
	for i := 0; i < 30; i++ {
		dateTime := now.AddDate(0, 0, -30+i)
		dateUnix := time.Date(dateTime.Year(), dateTime.Month(), dateTime.Day(), 0, 0, 0, 0, time.UTC).Unix()

		for _, symbol := range []string{"DAX.IDX", "FTSE.IDX"} {
			isin := "INDEX-" + symbol
			price := 1000.0 * (1.0 - float64(i)*0.001) // Declining
			_, err := historyDB.Exec(`
				INSERT OR REPLACE INTO daily_prices (isin, date, open, high, low, close, volume)
				VALUES (?, ?, ?, ?, ?, ?, ?)
			`, isin, dateUnix, price, price*1.01, price*0.99, price, 1000000)
			require.NoError(t, err)
		}
	}

	t.Run("Returns region-specific returns", func(t *testing.T) {
		usReturns, err := service.GetReturnsForRegion(RegionUS, 20)
		require.NoError(t, err)
		require.NotEmpty(t, usReturns)

		euReturns, err := service.GetReturnsForRegion(RegionEU, 20)
		require.NoError(t, err)
		require.NotEmpty(t, euReturns)

		// US should be mostly positive, EU should be mostly negative
		usPositive := 0
		for _, ret := range usReturns {
			if ret > 0 {
				usPositive++
			}
		}
		assert.Greater(t, usPositive, len(usReturns)/2, "US should have mostly positive returns")

		euNegative := 0
		for _, ret := range euReturns {
			if ret < 0 {
				euNegative++
			}
		}
		assert.Greater(t, euNegative, len(euReturns)/2, "EU should have mostly negative returns")
	})
}

func TestGetReturnsForAllRegions(t *testing.T) {
	universeDB, historyDB, historyDBClient := setupMarketIndexTestDB(t)
	log := zerolog.Nop()
	securityRepo := universe.NewSecurityRepository(universeDB, log)
	service := NewMarketIndexService(securityRepo, historyDBClient, nil, log)

	// Setup indices
	setupTestIndices(t, universeDB)

	// Setup price data for all regions
	allSymbols := []string{"SP500.IDX", "NASDAQ.IDX", "DAX.IDX", "FTSE.IDX", "HSI.IDX"}
	setupTestPrices(t, historyDB, allSymbols, 30, 0.001)

	t.Run("Returns returns for all regions with data", func(t *testing.T) {
		regionReturns, err := service.GetReturnsForAllRegions(20)
		require.NoError(t, err)
		require.NotEmpty(t, regionReturns)

		// Should have returns for US, EU, and ASIA
		assert.Contains(t, regionReturns, RegionUS, "Should have US returns")
		assert.Contains(t, regionReturns, RegionEU, "Should have EU returns")
		assert.Contains(t, regionReturns, RegionAsia, "Should have ASIA returns")

		// Each region should have returns
		for region, returns := range regionReturns {
			assert.NotEmpty(t, returns, "Region %s should have returns", region)
		}
	})
}

func TestGetPriceIndicesForRegion(t *testing.T) {
	universeDB, _, historyDBClient := setupMarketIndexTestDB(t)
	log := zerolog.Nop()
	securityRepo := universe.NewSecurityRepository(universeDB, log)
	service := NewMarketIndexService(securityRepo, historyDBClient, nil, log)

	t.Run("Returns correct indices for each region", func(t *testing.T) {
		usIndices := service.GetPriceIndicesForRegion(RegionUS)
		assert.NotEmpty(t, usIndices, "US should have indices")
		for _, idx := range usIndices {
			assert.Equal(t, RegionUS, idx.Region)
			assert.Equal(t, IndexTypePrice, idx.IndexType, "Should only return PRICE indices")
		}

		euIndices := service.GetPriceIndicesForRegion(RegionEU)
		assert.NotEmpty(t, euIndices, "EU should have indices")
		for _, idx := range euIndices {
			assert.Equal(t, RegionEU, idx.Region)
			assert.Equal(t, IndexTypePrice, idx.IndexType)
		}

		asiaIndices := service.GetPriceIndicesForRegion(RegionAsia)
		assert.NotEmpty(t, asiaIndices, "ASIA should have indices")
		for _, idx := range asiaIndices {
			assert.Equal(t, RegionAsia, idx.Region)
			assert.Equal(t, IndexTypePrice, idx.IndexType)
		}
	})

	t.Run("VIX is excluded from price indices", func(t *testing.T) {
		usIndices := service.GetPriceIndicesForRegion(RegionUS)
		for _, idx := range usIndices {
			assert.NotEqual(t, "VIX.IDX", idx.Symbol, "VIX should not be in price indices")
		}
	})
}
