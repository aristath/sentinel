package symbolic_regression

import (
	"database/sql"
	"testing"
	"time"

	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	_ "modernc.org/sqlite"
)

// testSecurityProvider wraps universe.SecurityRepository for testing
type testSecurityProvider struct {
	repo *universe.SecurityRepository
}

func newTestSecurityProvider(repo *universe.SecurityRepository) SecurityProvider {
	return &testSecurityProvider{repo: repo}
}

func (p *testSecurityProvider) GetISINBySymbol(symbol string) (string, error) {
	return p.repo.GetISINBySymbol(symbol)
}

func (p *testSecurityProvider) GetSymbolByISIN(isin string) (string, error) {
	return p.repo.GetSymbolByISIN(isin)
}

func (p *testSecurityProvider) GetAll() ([]SecurityInfo, error) {
	securities, err := p.repo.GetAll()
	if err != nil {
		return nil, err
	}

	result := make([]SecurityInfo, len(securities))
	for i, sec := range securities {
		result[i] = SecurityInfo{
			ISIN:        sec.ISIN,
			Symbol:      sec.Symbol,
			ProductType: sec.ProductType,
		}
	}
	return result, nil
}

// mockHistoryDB is a test mock implementing universe.HistoryDBInterface
type mockHistoryDB struct {
	prices map[string][]universe.DailyPrice // keyed by ISIN
}

func newMockHistoryDB() *mockHistoryDB {
	return &mockHistoryDB{
		prices: make(map[string][]universe.DailyPrice),
	}
}

// AddPrice adds a test price to the mock
func (m *mockHistoryDB) AddPrice(isin string, date string, close, adjustedClose float64) {
	adj := adjustedClose
	m.prices[isin] = append(m.prices[isin], universe.DailyPrice{
		Date:          date,
		Close:         close,
		AdjustedClose: &adj,
		Open:          close,
		High:          close,
		Low:           close,
	})
}

func (m *mockHistoryDB) GetDailyPrices(isin string, limit int) ([]universe.DailyPrice, error) {
	prices := m.prices[isin]
	if limit > 0 && len(prices) > limit {
		return prices[:limit], nil
	}
	return prices, nil
}

func (m *mockHistoryDB) GetRecentPrices(isin string, days int) ([]universe.DailyPrice, error) {
	return m.GetDailyPrices(isin, days)
}

func (m *mockHistoryDB) GetMonthlyPrices(isin string, limit int) ([]universe.MonthlyPrice, error) {
	return nil, nil
}

func (m *mockHistoryDB) HasMonthlyData(isin string) (bool, error) {
	return false, nil
}

func (m *mockHistoryDB) SyncHistoricalPrices(isin string, prices []universe.DailyPrice) error {
	return nil
}

func (m *mockHistoryDB) DeletePricesForSecurity(isin string) error {
	delete(m.prices, isin)
	return nil
}

func (m *mockHistoryDB) UpsertExchangeRate(fromCurrency, toCurrency string, rate float64) error {
	return nil
}

func (m *mockHistoryDB) GetLatestExchangeRate(fromCurrency, toCurrency string) (*universe.ExchangeRate, error) {
	return nil, nil
}

func (m *mockHistoryDB) InvalidateCache(isin string) {}
func (m *mockHistoryDB) InvalidateAllCaches()        {}

// Compile-time check that mockHistoryDB implements the interface
var _ universe.HistoryDBInterface = (*mockHistoryDB)(nil)

func setupTestDB(t *testing.T) (*sql.DB, func()) {
	db, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)

	// Create schema for testing
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS daily_prices (
			isin TEXT NOT NULL,
			date INTEGER NOT NULL,
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
			stability_score REAL,
			sharpe_score REAL,
			drawdown_score REAL,
			dividend_bonus REAL,
			financial_strength_score REAL,
			rsi REAL,
			ema_200 REAL,
			below_52w_high_pct REAL,
			last_updated INTEGER NOT NULL
		);

		CREATE TABLE IF NOT EXISTS calculated_metrics (
			symbol TEXT NOT NULL,
			metric_name TEXT NOT NULL,
			metric_value REAL NOT NULL,
			calculated_at INTEGER NOT NULL,
			PRIMARY KEY (symbol, metric_name)
		);

		CREATE TABLE IF NOT EXISTS market_regime_history (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			recorded_at INTEGER NOT NULL,
			raw_score REAL NOT NULL,
			smoothed_score REAL NOT NULL,
			discrete_regime TEXT NOT NULL DEFAULT 'n/a'
		);

		CREATE TABLE IF NOT EXISTS securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			data TEXT NOT NULL,
			last_synced INTEGER
		) STRICT;
	`)
	require.NoError(t, err)

	cleanup := func() {
		db.Close()
	}

	return db, cleanup
}

func TestDataPrep_ExtractTrainingExamples_MinimumHistory(t *testing.T) {
	// Create mock for history DB with filtered prices
	mockHistory := newMockHistoryDB()

	portfolioDB, cleanup2 := setupTestDB(t)
	defer cleanup2()

	configDB, cleanup3 := setupTestDB(t)
	defer cleanup3()

	universeDB, cleanup4 := setupTestDB(t)
	defer cleanup4()

	// Insert test data: security with 18 months of history (minimum required)
	isin := "US0378331005"
	symbol := "AAPL"

	// Add daily prices to mock: 18 months = ~540 days
	baseDate := time.Date(2023, 1, 15, 0, 0, 0, 0, time.UTC)
	for i := 0; i < 540; i++ {
		date := baseDate.AddDate(0, 0, i)
		dateStr := date.Format("2006-01-02")
		price := 100.0 + float64(i)*0.1
		mockHistory.AddPrice(isin, dateStr, price, price)
	}

	// Insert score at training date (2023-07-15)
	trainingDate := baseDate.AddDate(0, 6, 0)
	trainingDateUnix := time.Date(trainingDate.Year(), trainingDate.Month(), trainingDate.Day(), 0, 0, 0, 0, time.UTC).Unix()
	_, err := portfolioDB.Exec(
		"INSERT INTO scores (isin, total_score, cagr_score, stability_score, last_updated) VALUES (?, ?, ?, ?, ?)",
		isin, 0.75, 0.80, 0.70, trainingDateUnix,
	)
	require.NoError(t, err)

	// Insert regime score
	_, err = configDB.Exec(
		"INSERT INTO market_regime_history (recorded_at, raw_score, smoothed_score) VALUES (?, ?, ?)",
		trainingDate.Format("2006-01-02"), 0.3, 0.3,
	)
	require.NoError(t, err)

	// Insert security (JSON storage - migration 038)
	_, err = universeDB.Exec(
		"INSERT INTO securities (isin, symbol, data, last_synced) VALUES (?, ?, json_object('name', ?, 'product_type', 'EQUITY'), NULL)",
		isin, symbol, symbol+" Inc",
	)
	require.NoError(t, err)

	log := zerolog.Nop()
	securityRepo := universe.NewSecurityRepository(universeDB, log)
	securityProvider := newTestSecurityProvider(securityRepo)
	prep := NewDataPrep(mockHistory, portfolioDB, configDB, securityProvider, log)

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
	// Create mock for history DB with filtered prices
	mockHistory := newMockHistoryDB()

	portfolioDB, cleanup2 := setupTestDB(t)
	defer cleanup2()

	configDB, cleanup3 := setupTestDB(t)
	defer cleanup3()

	universeDB, cleanup4 := setupTestDB(t)
	defer cleanup4()

	// Insert test data: security with only 3 months of history (insufficient)
	isin := "US1234567890"
	symbol := "NEWCO"

	baseDate := time.Date(2023, 1, 15, 0, 0, 0, 0, time.UTC)
	// Only 90 days (3 months) - insufficient for 6-month forward return
	for i := 0; i < 90; i++ {
		date := baseDate.AddDate(0, 0, i)
		dateStr := date.Format("2006-01-02")
		mockHistory.AddPrice(isin, dateStr, 50.0, 50.0)
	}

	_, err := universeDB.Exec(
		"INSERT INTO securities (isin, symbol, data, last_synced) VALUES (?, ?, json_object('name', ?, 'product_type', 'EQUITY'), NULL)",
		isin, symbol, symbol+" Inc",
	)
	require.NoError(t, err)

	log := zerolog.Nop()
	securityRepo := universe.NewSecurityRepository(universeDB, log)
	securityProvider := newTestSecurityProvider(securityRepo)
	prep := NewDataPrep(mockHistory, portfolioDB, configDB, securityProvider, log)

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
	// Create mock for history DB with filtered prices
	mockHistory := newMockHistoryDB()

	portfolioDB, cleanup2 := setupTestDB(t)
	defer cleanup2()

	configDB, cleanup3 := setupTestDB(t)
	defer cleanup3()

	universeDB, cleanup4 := setupTestDB(t)
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
		dateStr := date.Format("2006-01-02")
		mockHistory.AddPrice(aaplISIN, dateStr, 100.0, 100.0)
	}

	_, err := universeDB.Exec(
		"INSERT INTO securities (isin, symbol, data, last_synced) VALUES (?, ?, json_object('name', 'Apple Inc.', 'product_type', ?), NULL)",
		aaplISIN, aaplSymbol, "EQUITY",
	)
	require.NoError(t, err)

	// Insert scores for AAPL at various dates (before both test dates)
	aaplScoreDate, _ := time.Parse("2006-01-02", "2019-12-01")
	aaplScoreDateUnix := time.Date(aaplScoreDate.Year(), aaplScoreDate.Month(), aaplScoreDate.Day(), 0, 0, 0, 0, time.UTC).Unix()
	_, err = portfolioDB.Exec(
		"INSERT INTO scores (isin, total_score, cagr_score, stability_score, last_updated) VALUES (?, ?, ?, ?, ?)",
		aaplISIN, 0.75, 0.80, 0.70, aaplScoreDateUnix,
	)
	require.NoError(t, err)

	// Insert regime scores (before both test dates)
	regimeDate1, _ := time.Parse("2006-01-02", "2019-12-01")
	regimeDate1Unix := time.Date(regimeDate1.Year(), regimeDate1.Month(), regimeDate1.Day(), 0, 0, 0, 0, time.UTC).Unix()
	_, err = configDB.Exec(
		"INSERT INTO market_regime_history (recorded_at, raw_score, smoothed_score) VALUES (?, ?, ?)",
		regimeDate1Unix, 0.3, 0.3,
	)
	require.NoError(t, err)

	// Also add regime score for 2022
	regimeDate2, _ := time.Parse("2006-01-02", "2022-01-01")
	regimeDate2Unix := time.Date(regimeDate2.Year(), regimeDate2.Month(), regimeDate2.Day(), 0, 0, 0, 0, time.UTC).Unix()
	_, err = configDB.Exec(
		"INSERT INTO market_regime_history (recorded_at, raw_score, smoothed_score) VALUES (?, ?, ?)",
		regimeDate2Unix, 0.2, 0.2,
	)
	require.NoError(t, err)

	// NEWCO - 2 years (starting 2022)
	newcoISIN := "US1234567890"
	newcoSymbol := "NEWCO"
	newcoStart := time.Date(2022, 1, 15, 0, 0, 0, 0, time.UTC)
	for i := 0; i < 730; i++ {
		date := newcoStart.AddDate(0, 0, i)
		dateStr := date.Format("2006-01-02")
		mockHistory.AddPrice(newcoISIN, dateStr, 50.0, 50.0)
	}

	_, err = universeDB.Exec(
		"INSERT INTO securities (isin, symbol, data, last_synced) VALUES (?, ?, json_object('name', 'NEWCO Inc.', 'product_type', ?), NULL)",
		newcoISIN, newcoSymbol, "EQUITY",
	)
	require.NoError(t, err)

	// Insert scores for NEWCO (before test date)
	newcoScoreDate, _ := time.Parse("2006-01-02", "2022-06-01")
	newcoScoreDateUnix := time.Date(newcoScoreDate.Year(), newcoScoreDate.Month(), newcoScoreDate.Day(), 0, 0, 0, 0, time.UTC).Unix()
	_, err = portfolioDB.Exec(
		"INSERT INTO scores (isin, total_score, cagr_score, stability_score, last_updated) VALUES (?, ?, ?, ?, ?)",
		newcoISIN, 0.70, 0.75, 0.65, newcoScoreDateUnix,
	)
	require.NoError(t, err)

	log := zerolog.Nop()
	securityRepo := universe.NewSecurityRepository(universeDB, log)
	securityProvider := newTestSecurityProvider(securityRepo)
	prep := NewDataPrep(mockHistory, portfolioDB, configDB, securityProvider, log)

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
	// Create mock for history DB with filtered prices
	mockHistory := newMockHistoryDB()

	isin := "US0378331005" // AAPL ISIN

	// Add price data: $100 on 2023-01-15, $110 on 2023-07-15 (10% return)
	mockHistory.AddPrice(isin, "2023-01-15", 100.0, 100.0)
	mockHistory.AddPrice(isin, "2023-07-15", 110.0, 110.0)

	log := zerolog.Nop()
	prep := NewDataPrep(mockHistory, nil, nil, nil, log)

	// Calculate 6-month return
	returnVal, err := prep.calculateTargetReturn(isin, "2023-01-15", "2023-07-15")
	require.NoError(t, err)

	// Should be 10% return
	assert.InDelta(t, 0.10, returnVal, 0.001)
}

func TestDataPrep_CalculateTargetReturn_NoData(t *testing.T) {
	// Create empty mock
	mockHistory := newMockHistoryDB()

	log := zerolog.Nop()
	prep := NewDataPrep(mockHistory, nil, nil, nil, log)

	// Try to calculate return for non-existent security
	_, err := prep.calculateTargetReturn("NONEXISTENT", "2023-01-15", "2023-07-15")
	assert.Error(t, err)
}
