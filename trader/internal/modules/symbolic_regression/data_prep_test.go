package symbolic_regression

import (
	"database/sql"
	"testing"
	"time"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	_ "modernc.org/sqlite"
)

func setupTestDB(t *testing.T) (*sql.DB, func()) {
	db, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)

	// Create schema for testing
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS daily_prices (
			isin TEXT NOT NULL,
			date TEXT NOT NULL,
			close REAL NOT NULL,
			adjusted_close REAL NOT NULL,
			PRIMARY KEY (isin, date)
		);

		CREATE TABLE IF NOT EXISTS scores (
			isin TEXT PRIMARY KEY,
			total_score REAL NOT NULL,
			quality_score REAL,
			opportunity_score REAL,
			analyst_score REAL,
			allocation_fit_score REAL,
			volatility REAL,
			cagr_score REAL,
			consistency_score REAL,
			history_years INTEGER,
			technical_score REAL,
			fundamental_score REAL,
			sharpe_score REAL,
			drawdown_score REAL,
			dividend_bonus REAL,
			financial_strength_score REAL,
			rsi REAL,
			ema_200 REAL,
			below_52w_high_pct REAL,
			last_updated TEXT NOT NULL
		);

		CREATE TABLE IF NOT EXISTS calculated_metrics (
			symbol TEXT NOT NULL,
			metric_name TEXT NOT NULL,
			metric_value REAL NOT NULL,
			calculated_at TEXT NOT NULL,
			PRIMARY KEY (symbol, metric_name)
		);

		CREATE TABLE IF NOT EXISTS market_regime_history (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			recorded_at TEXT NOT NULL,
			raw_score REAL NOT NULL,
			smoothed_score REAL NOT NULL,
			discrete_regime TEXT NOT NULL DEFAULT 'n/a'
		);

		CREATE TABLE IF NOT EXISTS securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			product_type TEXT NOT NULL,
			active INTEGER DEFAULT 1
		);
	`)
	require.NoError(t, err)

	cleanup := func() {
		db.Close()
	}

	return db, cleanup
}

func TestDataPrep_ExtractTrainingExamples_MinimumHistory(t *testing.T) {
	historyDB, cleanup := setupTestDB(t)
	defer cleanup()

	portfolioDB, cleanup2 := setupTestDB(t)
	defer cleanup2()

	configDB, cleanup3 := setupTestDB(t)
	defer cleanup3()

	universeDB, cleanup4 := setupTestDB(t)
	defer cleanup4()

	defer cleanup2()
	defer cleanup3()
	defer cleanup4()

	// Insert test data: security with 18 months of history (minimum required)
	isin := "US0378331005"
	symbol := "AAPL"

	// Insert daily prices: 18 months = ~540 days (use ISIN)
	baseDate := time.Date(2023, 1, 15, 0, 0, 0, 0, time.UTC)
	for i := 0; i < 540; i++ {
		date := baseDate.AddDate(0, 0, i)
		_, err := historyDB.Exec(
			"INSERT INTO daily_prices (isin, date, close, adjusted_close) VALUES (?, ?, ?, ?)",
			isin, date.Format("2006-01-02"), 100.0+float64(i)*0.1, 100.0+float64(i)*0.1,
		)
		require.NoError(t, err)
	}

	// Insert score at training date (2023-07-15)
	trainingDate := baseDate.AddDate(0, 6, 0)
	_, err := portfolioDB.Exec(
		"INSERT INTO scores (isin, total_score, cagr_score, fundamental_score, last_updated) VALUES (?, ?, ?, ?, ?)",
		isin, 0.75, 0.80, 0.70, trainingDate.Format("2006-01-02"),
	)
	require.NoError(t, err)

	// Insert regime score
	_, err = configDB.Exec(
		"INSERT INTO market_regime_history (recorded_at, raw_score, smoothed_score) VALUES (?, ?, ?)",
		trainingDate.Format("2006-01-02"), 0.3, 0.3,
	)
	require.NoError(t, err)

	// Insert security
	_, err = universeDB.Exec(
		"INSERT INTO securities (isin, symbol, product_type) VALUES (?, ?, ?)",
		isin, symbol, "EQUITY",
	)
	require.NoError(t, err)

	log := zerolog.Nop()
	prep := NewDataPrep(historyDB, portfolioDB, configDB, universeDB, log)

	// Extract training examples for 6-month forward returns
	examples, err := prep.ExtractTrainingExamples(
		time.Date(2023, 7, 15, 0, 0, 0, 0, time.UTC),
		6, // 6 months forward
	)
	require.NoError(t, err)

	// Should have at least one example
	assert.Greater(t, len(examples), 0, "Should extract at least one training example")

	// Verify example structure
	if len(examples) > 0 {
		ex := examples[0]
		assert.Equal(t, isin, ex.SecurityISIN)
		assert.Equal(t, symbol, ex.SecuritySymbol)
		assert.Equal(t, "EQUITY", ex.ProductType)
		assert.Equal(t, "2023-07-15", ex.Date)
		assert.Equal(t, "2024-01-15", ex.TargetDate) // 6 months later
		assert.Equal(t, 0.75, ex.Inputs.TotalScore)
		assert.Equal(t, 0.3, ex.Inputs.RegimeScore)
		// Target return should be calculated from price change
		assert.NotZero(t, ex.TargetReturn)
	}
}

func TestDataPrep_ExtractTrainingExamples_InsufficientHistory(t *testing.T) {
	historyDB, cleanup := setupTestDB(t)
	defer cleanup()

	portfolioDB, cleanup2 := setupTestDB(t)
	defer cleanup2()

	configDB, cleanup3 := setupTestDB(t)
	defer cleanup3()

	universeDB, cleanup4 := setupTestDB(t)
	defer cleanup4()

	defer cleanup2()
	defer cleanup3()
	defer cleanup4()

	// Insert test data: security with only 3 months of history (insufficient)
	isin := "US1234567890"
	symbol := "NEWCO"

	baseDate := time.Date(2023, 1, 15, 0, 0, 0, 0, time.UTC)
	// Only 90 days (3 months) - insufficient for 6-month forward return (use ISIN)
	for i := 0; i < 90; i++ {
		date := baseDate.AddDate(0, 0, i)
		_, err := historyDB.Exec(
			"INSERT INTO daily_prices (isin, date, close, adjusted_close) VALUES (?, ?, ?, ?)",
			isin, date.Format("2006-01-02"), 50.0, 50.0,
		)
		require.NoError(t, err)
	}

	_, err := universeDB.Exec(
		"INSERT INTO securities (isin, symbol, product_type) VALUES (?, ?, ?)",
		isin, symbol, "EQUITY",
	)
	require.NoError(t, err)

	log := zerolog.Nop()
	prep := NewDataPrep(historyDB, portfolioDB, configDB, universeDB, log)

	// Extract training examples
	examples, err := prep.ExtractTrainingExamples(
		time.Date(2023, 1, 15, 0, 0, 0, 0, time.UTC),
		6, // 6 months forward
	)
	require.NoError(t, err)

	// Should exclude this security (insufficient history)
	for _, ex := range examples {
		assert.NotEqual(t, isin, ex.SecurityISIN, "Should exclude security with insufficient history")
	}
}

func TestDataPrep_ExtractTrainingExamples_TimeWindowed(t *testing.T) {
	historyDB, cleanup := setupTestDB(t)
	defer cleanup()

	portfolioDB, cleanup2 := setupTestDB(t)
	defer cleanup2()

	configDB, cleanup3 := setupTestDB(t)
	defer cleanup3()

	universeDB, cleanup4 := setupTestDB(t)
	defer cleanup4()

	defer cleanup2()
	defer cleanup3()
	defer cleanup4()

	// Create two securities with different history lengths
	// AAPL: 10 years of history
	// NEWCO: 2 years of history (starting 2022)

	// AAPL - 10 years
	aaplISIN := "US0378331005"
	aaplSymbol := "AAPL"
	aaplStart := time.Date(2014, 1, 15, 0, 0, 0, 0, time.UTC)
	for i := 0; i < 3650; i++ {
		date := aaplStart.AddDate(0, 0, i)
		_, err := historyDB.Exec(
			"INSERT INTO daily_prices (isin, date, close, adjusted_close) VALUES (?, ?, ?, ?)",
			aaplISIN, date.Format("2006-01-02"), 100.0, 100.0,
		)
		require.NoError(t, err)
	}

	_, err := universeDB.Exec(
		"INSERT INTO securities (isin, symbol, product_type) VALUES (?, ?, ?)",
		aaplISIN, aaplSymbol, "EQUITY",
	)
	require.NoError(t, err)

	// Insert scores for AAPL at various dates (before both test dates)
	_, err = portfolioDB.Exec(
		"INSERT INTO scores (isin, total_score, cagr_score, fundamental_score, last_updated) VALUES (?, ?, ?, ?, ?)",
		aaplISIN, 0.75, 0.80, 0.70, "2019-12-01",
	)
	require.NoError(t, err)

	// Insert regime scores (before both test dates)
	_, err = configDB.Exec(
		"INSERT INTO market_regime_history (recorded_at, raw_score, smoothed_score) VALUES (?, ?, ?)",
		"2019-12-01", 0.3, 0.3,
	)
	require.NoError(t, err)

	// Also add regime score for 2022
	_, err = configDB.Exec(
		"INSERT INTO market_regime_history (recorded_at, raw_score, smoothed_score) VALUES (?, ?, ?)",
		"2022-01-01", 0.2, 0.2,
	)
	require.NoError(t, err)

	// NEWCO - 2 years (starting 2022)
	newcoISIN := "US1234567890"
	newcoSymbol := "NEWCO"
	newcoStart := time.Date(2022, 1, 15, 0, 0, 0, 0, time.UTC)
	for i := 0; i < 730; i++ {
		date := newcoStart.AddDate(0, 0, i)
		_, err := historyDB.Exec(
			"INSERT INTO daily_prices (isin, date, close, adjusted_close) VALUES (?, ?, ?, ?)",
			newcoISIN, date.Format("2006-01-02"), 50.0, 50.0,
		)
		require.NoError(t, err)
	}

	_, err = universeDB.Exec(
		"INSERT INTO securities (isin, symbol, product_type) VALUES (?, ?, ?)",
		newcoISIN, newcoSymbol, "EQUITY",
	)
	require.NoError(t, err)

	// Insert scores for NEWCO (before test date)
	_, err = portfolioDB.Exec(
		"INSERT INTO scores (isin, total_score, cagr_score, fundamental_score, last_updated) VALUES (?, ?, ?, ?, ?)",
		newcoISIN, 0.70, 0.75, 0.65, "2022-06-01",
	)
	require.NoError(t, err)

	log := zerolog.Nop()
	prep := NewDataPrep(historyDB, portfolioDB, configDB, universeDB, log)

	// Test 1: Training date 2020-01-15 (before NEWCO exists)
	examples2020, err := prep.ExtractTrainingExamples(
		time.Date(2020, 1, 15, 0, 0, 0, 0, time.UTC),
		6,
	)
	require.NoError(t, err)

	// Should only include AAPL (NEWCO doesn't exist yet)
	aaplCount := 0
	for _, ex := range examples2020 {
		if ex.SecurityISIN == aaplISIN {
			aaplCount++
		}
		assert.NotEqual(t, newcoISIN, ex.SecurityISIN, "NEWCO should not be included in 2020")
	}
	assert.Greater(t, aaplCount, 0, "AAPL should be included")

	// Test 2: Training date 2022-07-15 (both securities have data)
	examples2022, err := prep.ExtractTrainingExamples(
		time.Date(2022, 7, 15, 0, 0, 0, 0, time.UTC),
		6,
	)
	require.NoError(t, err)

	// Should include both
	aaplCount2022 := 0
	newcoCount2022 := 0
	for _, ex := range examples2022 {
		if ex.SecurityISIN == aaplISIN {
			aaplCount2022++
		}
		if ex.SecurityISIN == newcoISIN {
			newcoCount2022++
		}
	}
	assert.Greater(t, aaplCount2022, 0, "AAPL should be included in 2022")
	assert.Greater(t, newcoCount2022, 0, "NEWCO should be included in 2022")
}

func TestDataPrep_CalculateTargetReturn(t *testing.T) {
	historyDB, cleanup := setupTestDB(t)
	defer cleanup()

	log := zerolog.Nop()
	prep := NewDataPrep(historyDB, nil, nil, nil, log)

	isin := "US0378331005" // AAPL ISIN

	// Insert price data: $100 on 2023-01-15, $110 on 2023-07-15 (10% return)
	_, err := historyDB.Exec(
		"INSERT INTO daily_prices (isin, date, close, adjusted_close) VALUES (?, ?, ?, ?)",
		isin, "2023-01-15", 100.0, 100.0,
	)
	require.NoError(t, err)

	_, err = historyDB.Exec(
		"INSERT INTO daily_prices (isin, date, close, adjusted_close) VALUES (?, ?, ?, ?)",
		isin, "2023-07-15", 110.0, 110.0,
	)
	require.NoError(t, err)

	// Calculate 6-month return
	returnVal, err := prep.calculateTargetReturn(isin, "2023-01-15", "2023-07-15")
	require.NoError(t, err)

	// Should be 10% return
	assert.InDelta(t, 0.10, returnVal, 0.001)
}

func TestDataPrep_CalculateTargetReturn_NoData(t *testing.T) {
	historyDB, cleanup := setupTestDB(t)
	defer cleanup()

	log := zerolog.Nop()
	prep := NewDataPrep(historyDB, nil, nil, nil, log)

	// Try to calculate return for non-existent security
	_, err := prep.calculateTargetReturn("NONEXISTENT", "2023-01-15", "2023-07-15")
	assert.Error(t, err)
}
