package universe

import (
	"database/sql"
	"testing"
	"time"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	_ "github.com/mattn/go-sqlite3"
)

func setupHistoryTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)

	// Create daily_prices table (consolidated schema)
	_, err = db.Exec(`
		CREATE TABLE daily_prices (
			isin TEXT NOT NULL,
			date TEXT NOT NULL,
			open REAL NOT NULL,
			high REAL NOT NULL,
			low REAL NOT NULL,
			close REAL NOT NULL,
			volume INTEGER,
			adjusted_close REAL,
			PRIMARY KEY (isin, date)
		) STRICT
	`)
	require.NoError(t, err)

	// Create monthly_prices table
	_, err = db.Exec(`
		CREATE TABLE monthly_prices (
			isin TEXT NOT NULL,
			year_month TEXT NOT NULL,
			avg_close REAL NOT NULL,
			avg_adj_close REAL NOT NULL,
			source TEXT,
			created_at TEXT,
			PRIMARY KEY (isin, year_month)
		) STRICT
	`)
	require.NoError(t, err)

	// Create indexes
	_, err = db.Exec(`
		CREATE INDEX IF NOT EXISTS idx_prices_isin ON daily_prices(isin);
		CREATE INDEX IF NOT EXISTS idx_prices_date ON daily_prices(date DESC);
		CREATE INDEX IF NOT EXISTS idx_monthly_isin ON monthly_prices(isin);
		CREATE INDEX IF NOT EXISTS idx_monthly_year_month ON monthly_prices(year_month DESC);
	`)
	require.NoError(t, err)

	return db
}

func TestNewHistoryDB(t *testing.T) {
	db := setupHistoryTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	historyDB := NewHistoryDB(db, log)

	require.NotNil(t, historyDB)
	assert.NotNil(t, historyDB.db)
}

func TestGetDailyPrices_WithISIN(t *testing.T) {
	db := setupHistoryTestDB(t)
	defer db.Close()

	// Insert test data with ISIN
	_, err := db.Exec(`
		INSERT INTO daily_prices (isin, date, open, high, low, close, volume, adjusted_close)
		VALUES
			('US0378331005', '2024-01-02', 185.0, 186.5, 184.0, 185.5, 50000000, 185.5),
			('US0378331005', '2024-01-03', 185.5, 187.0, 185.0, 186.0, 45000000, 186.0),
			('US0378331005', '2024-01-04', 186.0, 188.0, 185.5, 187.5, 55000000, 187.5),
			('NL0010273215', '2024-01-02', 800.0, 810.0, 795.0, 805.0, 1000000, 805.0)
	`)
	require.NoError(t, err)

	log := zerolog.New(nil).Level(zerolog.Disabled)
	historyDB := NewHistoryDB(db, log)

	// Test: Get daily prices for ISIN US0378331005 (AAPL)
	prices, err := historyDB.GetDailyPrices("US0378331005", 10)

	assert.NoError(t, err)
	assert.Len(t, prices, 3)
	assert.Equal(t, "2024-01-04", prices[0].Date) // Most recent first
	assert.Equal(t, 187.5, prices[0].Close)
	assert.Equal(t, 188.0, prices[0].High)
	assert.Equal(t, 185.5, prices[0].Low)
	assert.Equal(t, 186.0, prices[0].Open)
	require.NotNil(t, prices[0].Volume)
	assert.Equal(t, int64(55000000), *prices[0].Volume)
}

func TestGetDailyPrices_NoData(t *testing.T) {
	db := setupHistoryTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	historyDB := NewHistoryDB(db, log)

	// Test: Get daily prices for ISIN with no data
	prices, err := historyDB.GetDailyPrices("US0000000000", 10)

	assert.NoError(t, err)
	assert.Empty(t, prices)
}

func TestGetDailyPrices_Limit(t *testing.T) {
	db := setupHistoryTestDB(t)
	defer db.Close()

	// Insert 5 days of data
	for i := 1; i <= 5; i++ {
		date := time.Date(2024, 1, i+1, 0, 0, 0, 0, time.UTC).Format("2006-01-02")
		_, err := db.Exec(`
			INSERT INTO daily_prices (isin, date, open, high, low, close, volume, adjusted_close)
			VALUES (?, ?, 100.0, 105.0, 95.0, 102.0, 1000000, 102.0)
		`, "US0378331005", date)
		require.NoError(t, err)
	}

	log := zerolog.New(nil).Level(zerolog.Disabled)
	historyDB := NewHistoryDB(db, log)

	// Test: Limit to 3
	prices, err := historyDB.GetDailyPrices("US0378331005", 3)

	assert.NoError(t, err)
	assert.Len(t, prices, 3)
}

func TestGetMonthlyPrices_WithISIN(t *testing.T) {
	db := setupHistoryTestDB(t)
	defer db.Close()

	// Insert monthly data with ISIN
	_, err := db.Exec(`
		INSERT INTO monthly_prices (isin, year_month, avg_close, avg_adj_close, source, created_at)
		VALUES
			('US0378331005', '2024-01', 185.0, 185.0, 'calculated', datetime('now')),
			('US0378331005', '2024-02', 186.5, 186.5, 'calculated', datetime('now')),
			('US0378331005', '2024-03', 188.0, 188.0, 'calculated', datetime('now')),
			('NL0010273215', '2024-01', 800.0, 800.0, 'calculated', datetime('now'))
	`)
	require.NoError(t, err)

	log := zerolog.New(nil).Level(zerolog.Disabled)
	historyDB := NewHistoryDB(db, log)

	// Test: Get monthly prices for ISIN US0378331005
	prices, err := historyDB.GetMonthlyPrices("US0378331005", 10)

	assert.NoError(t, err)
	assert.Len(t, prices, 3)
	assert.Equal(t, "2024-03", prices[0].YearMonth) // Most recent first
	assert.Equal(t, 188.0, prices[0].AvgAdjClose)
}

func TestGetMonthlyPrices_NoData(t *testing.T) {
	db := setupHistoryTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	historyDB := NewHistoryDB(db, log)

	// Test: Get monthly prices for ISIN with no data
	prices, err := historyDB.GetMonthlyPrices("US0000000000", 10)

	assert.NoError(t, err)
	assert.Empty(t, prices)
}

func TestHasMonthlyData_WithISIN(t *testing.T) {
	db := setupHistoryTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	historyDB := NewHistoryDB(db, log)

	// Test: No monthly data initially
	hasData, err := historyDB.HasMonthlyData("US0378331005")
	assert.NoError(t, err)
	assert.False(t, hasData)

	// Insert monthly data
	_, err = db.Exec(`
		INSERT INTO monthly_prices (isin, year_month, avg_close, avg_adj_close, source, created_at)
		VALUES ('US0378331005', '2024-01', 185.0, 185.0, 'calculated', datetime('now'))
	`)
	require.NoError(t, err)

	// Test: Has monthly data now
	hasData, err = historyDB.HasMonthlyData("US0378331005")
	assert.NoError(t, err)
	assert.True(t, hasData)

	// Test: Different ISIN still has no data
	hasData, err = historyDB.HasMonthlyData("NL0010273215")
	assert.NoError(t, err)
	assert.False(t, hasData)
}

func TestSyncHistoricalPrices_WithISIN(t *testing.T) {
	db := setupHistoryTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	historyDB := NewHistoryDB(db, log)

	// Test data
	isin := "US0378331005"
	prices := []DailyPrice{
		{Date: "2024-01-02", Open: 185.0, High: 186.5, Low: 184.0, Close: 185.5, Volume: intPtr(50000000)},
		{Date: "2024-01-03", Open: 185.5, High: 187.0, Low: 185.0, Close: 186.0, Volume: intPtr(45000000)},
		{Date: "2024-01-04", Open: 186.0, High: 188.0, Low: 185.5, Close: 187.5, Volume: intPtr(55000000)},
	}

	// Test: Sync historical prices
	err := historyDB.SyncHistoricalPrices(isin, prices)
	assert.NoError(t, err)

	// Verify daily prices were inserted
	var count int
	err = db.QueryRow("SELECT COUNT(*) FROM daily_prices WHERE isin = ?", isin).Scan(&count)
	assert.NoError(t, err)
	assert.Equal(t, 3, count)

	// Verify monthly prices were aggregated
	err = db.QueryRow("SELECT COUNT(*) FROM monthly_prices WHERE isin = ?", isin).Scan(&count)
	assert.NoError(t, err)
	assert.Equal(t, 1, count) // All 3 days are in January 2024

	// Verify monthly price value
	var avgClose float64
	err = db.QueryRow("SELECT avg_close FROM monthly_prices WHERE isin = ? AND year_month = '2024-01'", isin).Scan(&avgClose)
	assert.NoError(t, err)
	expectedAvg := (185.5 + 186.0 + 187.5) / 3.0
	assert.InDelta(t, expectedAvg, avgClose, 0.01)
}

func TestSyncHistoricalPrices_MultipleISINs(t *testing.T) {
	db := setupHistoryTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	historyDB := NewHistoryDB(db, log)

	// Sync prices for first ISIN
	isin1 := "US0378331005"
	prices1 := []DailyPrice{
		{Date: "2024-01-02", Open: 185.0, High: 186.5, Low: 184.0, Close: 185.5, Volume: intPtr(50000000)},
	}
	err := historyDB.SyncHistoricalPrices(isin1, prices1)
	assert.NoError(t, err)

	// Sync prices for second ISIN
	isin2 := "NL0010273215"
	prices2 := []DailyPrice{
		{Date: "2024-01-02", Open: 800.0, High: 810.0, Low: 795.0, Close: 805.0, Volume: intPtr(1000000)},
	}
	err = historyDB.SyncHistoricalPrices(isin2, prices2)
	assert.NoError(t, err)

	// Verify ISIN isolation - each ISIN has its own data
	var count1, count2 int
	err = db.QueryRow("SELECT COUNT(*) FROM daily_prices WHERE isin = ?", isin1).Scan(&count1)
	assert.NoError(t, err)
	err = db.QueryRow("SELECT COUNT(*) FROM daily_prices WHERE isin = ?", isin2).Scan(&count2)
	assert.NoError(t, err)

	assert.Equal(t, 1, count1)
	assert.Equal(t, 1, count2)

	// Verify data is correct for each ISIN
	var close1, close2 float64
	err = db.QueryRow("SELECT close FROM daily_prices WHERE isin = ?", isin1).Scan(&close1)
	assert.NoError(t, err)
	err = db.QueryRow("SELECT close FROM daily_prices WHERE isin = ?", isin2).Scan(&close2)
	assert.NoError(t, err)

	assert.Equal(t, 185.5, close1)
	assert.Equal(t, 805.0, close2)
}

func TestSyncHistoricalPrices_ReplaceExisting(t *testing.T) {
	db := setupHistoryTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	historyDB := NewHistoryDB(db, log)

	isin := "US0378331005"

	// First sync
	prices1 := []DailyPrice{
		{Date: "2024-01-02", Open: 185.0, High: 186.5, Low: 184.0, Close: 185.5, Volume: intPtr(50000000)},
	}
	err := historyDB.SyncHistoricalPrices(isin, prices1)
	assert.NoError(t, err)

	// Second sync with updated price for same date
	prices2 := []DailyPrice{
		{Date: "2024-01-02", Open: 186.0, High: 187.0, Low: 185.0, Close: 186.5, Volume: intPtr(51000000)},
	}
	err = historyDB.SyncHistoricalPrices(isin, prices2)
	assert.NoError(t, err)

	// Verify only one row exists (replaced, not duplicated)
	var count int
	err = db.QueryRow("SELECT COUNT(*) FROM daily_prices WHERE isin = ?", isin).Scan(&count)
	assert.NoError(t, err)
	assert.Equal(t, 1, count)

	// Verify updated price
	var close float64
	err = db.QueryRow("SELECT close FROM daily_prices WHERE isin = ? AND date = '2024-01-02'", isin).Scan(&close)
	assert.NoError(t, err)
	assert.Equal(t, 186.5, close) // Updated value, not original
}

func TestSyncHistoricalPrices_MonthlyAggregation(t *testing.T) {
	db := setupHistoryTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	historyDB := NewHistoryDB(db, log)

	isin := "US0378331005"
	// Prices spanning two months
	prices := []DailyPrice{
		{Date: "2024-01-30", Open: 185.0, High: 186.0, Low: 184.0, Close: 185.5, Volume: intPtr(50000000)},
		{Date: "2024-01-31", Open: 185.5, High: 186.5, Low: 185.0, Close: 186.0, Volume: intPtr(45000000)},
		{Date: "2024-02-01", Open: 186.0, High: 187.0, Low: 185.5, Close: 186.5, Volume: intPtr(55000000)},
		{Date: "2024-02-02", Open: 186.5, High: 188.0, Low: 186.0, Close: 187.5, Volume: intPtr(60000000)},
	}

	err := historyDB.SyncHistoricalPrices(isin, prices)
	assert.NoError(t, err)

	// Verify two monthly aggregates were created
	var count int
	err = db.QueryRow("SELECT COUNT(*) FROM monthly_prices WHERE isin = ?", isin).Scan(&count)
	assert.NoError(t, err)
	assert.Equal(t, 2, count)

	// Verify January average
	var janAvg float64
	err = db.QueryRow("SELECT avg_close FROM monthly_prices WHERE isin = ? AND year_month = '2024-01'", isin).Scan(&janAvg)
	assert.NoError(t, err)
	expectedJanAvg := (185.5 + 186.0) / 2.0
	assert.InDelta(t, expectedJanAvg, janAvg, 0.01)

	// Verify February average
	var febAvg float64
	err = db.QueryRow("SELECT avg_close FROM monthly_prices WHERE isin = ? AND year_month = '2024-02'", isin).Scan(&febAvg)
	assert.NoError(t, err)
	expectedFebAvg := (186.5 + 187.5) / 2.0
	assert.InDelta(t, expectedFebAvg, febAvg, 0.01)
}

// Helper function
func intPtr(i int64) *int64 {
	return &i
}
