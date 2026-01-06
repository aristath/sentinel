package portfolio

import (
	"database/sql"
	"os"
	"testing"
	"time"

	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func setupMarketIndexTestDB(t *testing.T) (*sql.DB, *sql.DB) {
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

	// Create universe schema
	_, err = universeDB.Exec(`
		CREATE TABLE IF NOT EXISTS securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			name TEXT NOT NULL,
			product_type TEXT,
			active INTEGER DEFAULT 1,
			allow_buy INTEGER DEFAULT 1,
			allow_sell INTEGER DEFAULT 1,
			created_at TEXT NOT NULL,
			updated_at TEXT NOT NULL
		);
	`)
	require.NoError(t, err)

	// Create history schema
	_, err = historyDB.Exec(`
		CREATE TABLE IF NOT EXISTS daily_prices (
			symbol TEXT NOT NULL,
			date TEXT NOT NULL,
			open REAL NOT NULL,
			high REAL NOT NULL,
			low REAL NOT NULL,
			close REAL NOT NULL,
			volume INTEGER,
			adjusted_close REAL,
			PRIMARY KEY (symbol, date)
		);
		CREATE INDEX IF NOT EXISTS idx_prices_symbol_date ON daily_prices(symbol, date DESC);
	`)
	require.NoError(t, err)

	t.Cleanup(func() {
		universeDB.Close()
		historyDB.Close()
		os.Remove(universeFile.Name())
		os.Remove(historyFile.Name())
	})

	return universeDB, historyDB
}

func TestEnsureIndicesExist(t *testing.T) {
	universeDB, historyDB := setupMarketIndexTestDB(t)
	service := NewMarketIndexService(universeDB, historyDB, nil, zerolog.Nop())

	t.Run("Creates indices if they don't exist", func(t *testing.T) {
		err := service.EnsureIndicesExist()
		require.NoError(t, err)

		// Verify indices were created
		var count int
		err = universeDB.QueryRow(`
			SELECT COUNT(*) FROM securities
			WHERE product_type = 'INDEX'
		`).Scan(&count)
		require.NoError(t, err)
		assert.GreaterOrEqual(t, count, 3, "Should have at least 3 indices")
	})

	t.Run("Indices are non-tradeable", func(t *testing.T) {
		err := service.EnsureIndicesExist()
		require.NoError(t, err)

		var allowBuy, allowSell int
		err = universeDB.QueryRow(`
			SELECT allow_buy, allow_sell FROM securities
			WHERE symbol = 'SPX.US' AND product_type = 'INDEX'
		`).Scan(&allowBuy, &allowSell)
		require.NoError(t, err)
		assert.Equal(t, 0, allowBuy, "Indices should not be buyable")
		assert.Equal(t, 0, allowSell, "Indices should not be sellable")
	})

	t.Run("Idempotent - can call multiple times", func(t *testing.T) {
		err := service.EnsureIndicesExist()
		require.NoError(t, err)

		var count1 int
		universeDB.QueryRow(`SELECT COUNT(*) FROM securities WHERE product_type = 'INDEX'`).Scan(&count1)

		err = service.EnsureIndicesExist()
		require.NoError(t, err)

		var count2 int
		universeDB.QueryRow(`SELECT COUNT(*) FROM securities WHERE product_type = 'INDEX'`).Scan(&count2)

		assert.Equal(t, count1, count2, "Should not create duplicates")
	})
}

func TestGetCompositeReturns(t *testing.T) {
	universeDB, historyDB := setupMarketIndexTestDB(t)
	service := NewMarketIndexService(universeDB, historyDB, nil, zerolog.Nop())

	// Setup: Create indices and add price data
	err := service.EnsureIndicesExist()
	require.NoError(t, err)

	// Insert test price data
	now := time.Now()
	for i := 0; i < 10; i++ {
		date := now.AddDate(0, 0, -10+i).Format("2006-01-02")

		// S&P 500: +1% per day
		spxPrice := 4000.0 * (1.0 + float64(i)*0.01)
		_, err = historyDB.Exec(`
			INSERT OR REPLACE INTO daily_prices (symbol, date, open, high, low, close, volume)
			VALUES (?, ?, ?, ?, ?, ?, ?)
		`, "SPX.US", date, spxPrice, spxPrice*1.01, spxPrice*0.99, spxPrice, 1000000)
		require.NoError(t, err)

		// MSCI Europe: +0.5% per day
		euPrice := 2000.0 * (1.0 + float64(i)*0.005)
		_, err = historyDB.Exec(`
			INSERT OR REPLACE INTO daily_prices (symbol, date, open, high, low, close, volume)
			VALUES (?, ?, ?, ?, ?, ?, ?)
		`, "STOXX600.EU", date, euPrice, euPrice*1.01, euPrice*0.99, euPrice, 1000000)
		require.NoError(t, err)

		// MSCI Asia: +0.3% per day
		asiaPrice := 1500.0 * (1.0 + float64(i)*0.003)
		_, err = historyDB.Exec(`
			INSERT OR REPLACE INTO daily_prices (symbol, date, open, high, low, close, volume)
			VALUES (?, ?, ?, ?, ?, ?, ?)
		`, "MSCIASIA.ASIA", date, asiaPrice, asiaPrice*1.01, asiaPrice*0.99, asiaPrice, 1000000)
		require.NoError(t, err)
	}

	t.Run("Calculates weighted composite returns", func(t *testing.T) {
		returns, err := service.GetCompositeReturns(10) // Last 10 days
		require.NoError(t, err)
		require.NotEmpty(t, returns)

		// With weights: US 20%, EU 50%, Asia 30%
		// Expected: weighted average of individual returns
		// Should be positive (all indices are rising)
		assert.Greater(t, len(returns), 0, "Should have returns")

		// Check that returns are reasonable (daily returns should be small)
		for _, ret := range returns {
			assert.Greater(t, ret, -0.1, "Daily return should not be extreme")
			assert.Less(t, ret, 0.1, "Daily return should not be extreme")
		}
	})

	t.Run("Handles missing index data gracefully", func(t *testing.T) {
		// Remove one index's data
		_, err = historyDB.Exec(`DELETE FROM daily_prices WHERE symbol = 'MSCIASIA.ASIA'`)
		require.NoError(t, err)

		// Should still work with available indices
		returns, err := service.GetCompositeReturns(10)
		// Should either return partial data or error gracefully
		if err != nil {
			assert.Contains(t, err.Error(), "insufficient", "Should indicate insufficient data")
		} else {
			assert.NotEmpty(t, returns, "Should return partial data if available")
		}
	})
}

func TestGetMarketReturns(t *testing.T) {
	universeDB, historyDB := setupMarketIndexTestDB(t)
	service := NewMarketIndexService(universeDB, historyDB, nil, zerolog.Nop())

	// Setup indices
	err := service.EnsureIndicesExist()
	require.NoError(t, err)

	// Insert price data
	now := time.Now()
	for i := 0; i < 30; i++ {
		date := now.AddDate(0, 0, -30+i).Format("2006-01-02")
		price := 1000.0 * (1.0 + float64(i)*0.001) // Small daily gains

		for _, symbol := range []string{"SPX.US", "STOXX600.EU", "MSCIASIA.ASIA"} {
			_, err = historyDB.Exec(`
				INSERT OR REPLACE INTO daily_prices (symbol, date, open, high, low, close, volume)
				VALUES (?, ?, ?, ?, ?, ?, ?)
			`, symbol, date, price, price*1.01, price*0.99, price, 1000000)
			require.NoError(t, err)
		}
	}

	t.Run("Returns market returns for regime detection", func(t *testing.T) {
		returns, err := service.GetMarketReturns(20) // Last 20 days
		require.NoError(t, err)
		require.Len(t, returns, 20, "Should return 20 daily returns")

		// Returns should be reasonable (small daily returns)
		for _, ret := range returns {
			assert.Greater(t, ret, -0.1, "Daily return should not be extreme negative")
			assert.Less(t, ret, 0.1, "Daily return should not be extreme positive")
		}
	})

	t.Run("Handles insufficient data", func(t *testing.T) {
		// Request more days than available
		returns, err := service.GetMarketReturns(100)
		if err != nil {
			assert.Contains(t, err.Error(), "insufficient", "Should indicate insufficient data")
		} else {
			assert.LessOrEqual(t, len(returns), 30, "Should return available data only")
		}
	})
}

func TestMarketIndexWeights(t *testing.T) {
	universeDB, historyDB := setupMarketIndexTestDB(t)
	service := NewMarketIndexService(universeDB, historyDB, nil, zerolog.Nop())

	t.Run("Default weights match portfolio allocation", func(t *testing.T) {
		indices := service.GetDefaultIndices()

		// Verify weights sum to 1.0
		totalWeight := 0.0
		for _, idx := range indices {
			totalWeight += idx.Weight
		}
		assert.InDelta(t, 1.0, totalWeight, 0.01, "Weights should sum to 1.0")

		// Verify specific weights (50/30/20 allocation)
		usWeight := 0.0
		euWeight := 0.0
		asiaWeight := 0.0

		for _, idx := range indices {
			switch idx.Region {
			case "US":
				usWeight += idx.Weight
			case "EU":
				euWeight += idx.Weight
			case "ASIA":
				asiaWeight += idx.Weight
			}
		}

		assert.InDelta(t, 0.20, usWeight, 0.01, "US should be 20%")
		assert.InDelta(t, 0.50, euWeight, 0.01, "EU should be 50%")
		assert.InDelta(t, 0.30, asiaWeight, 0.01, "Asia should be 30%")
	})
}
