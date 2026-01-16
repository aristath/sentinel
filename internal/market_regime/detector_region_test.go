package market_regime

import (
	"database/sql"
	"testing"
	"time"

	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	_ "github.com/mattn/go-sqlite3"
)

// mockSecurityProvider implements SecurityProvider for testing
type mockSecurityProvider struct {
	db *sql.DB
}

func (m *mockSecurityProvider) GetISINBySymbol(symbol string) (string, error) {
	var isin string
	err := m.db.QueryRow("SELECT isin FROM securities WHERE symbol = ?", symbol).Scan(&isin)
	if err == sql.ErrNoRows {
		return "", nil
	}
	return isin, err
}

// mockSecurityRepo implements SecurityRepositoryInterface for testing
type mockSecurityRepo struct {
	db *sql.DB
}

func (m *mockSecurityRepo) Exists(isin string) (bool, error) {
	var count int
	err := m.db.QueryRow("SELECT COUNT(*) FROM securities WHERE isin = ?", isin).Scan(&count)
	return count > 0, err
}

func (m *mockSecurityRepo) Create(sec universe.Security) error {
	_, err := m.db.Exec(`INSERT INTO securities (isin, symbol, name, product_type, market_code, active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)`,
		sec.ISIN, sec.Symbol, sec.Name, sec.ProductType, sec.MarketCode, 0, 0)
	return err
}

func (m *mockSecurityRepo) Update(isin string, updates map[string]any) error {
	return nil // Not needed for these tests
}

// Implement remaining interface methods as no-ops (not used in these tests)
func (m *mockSecurityRepo) GetBySymbol(symbol string) (*universe.Security, error) { return nil, nil }
func (m *mockSecurityRepo) GetByISIN(isin string) (*universe.Security, error)     { return nil, nil }
func (m *mockSecurityRepo) GetByIdentifier(identifier string) (*universe.Security, error) {
	return nil, nil
}
func (m *mockSecurityRepo) GetAll() ([]universe.Security, error)       { return nil, nil }
func (m *mockSecurityRepo) GetAllActive() ([]universe.Security, error) { return nil, nil }
func (m *mockSecurityRepo) GetAllActiveTradable() ([]universe.Security, error) {
	return nil, nil
}
func (m *mockSecurityRepo) GetByISINs(isins []string) ([]universe.Security, error) { return nil, nil }
func (m *mockSecurityRepo) GetBySymbols(symbols []string) ([]universe.Security, error) {
	return nil, nil
}
func (m *mockSecurityRepo) GetTradable() ([]universe.Security, error) { return nil, nil }
func (m *mockSecurityRepo) GetByMarketCode(marketCode string) ([]universe.Security, error) {
	return nil, nil
}
func (m *mockSecurityRepo) GetByGeography(geography string) ([]universe.Security, error) {
	return nil, nil
}
func (m *mockSecurityRepo) GetByIndustry(industry string) ([]universe.Security, error) {
	return nil, nil
}
func (m *mockSecurityRepo) GetByTags(tagIDs []string) ([]universe.Security, error) { return nil, nil }
func (m *mockSecurityRepo) GetPositionsByTags(positionSymbols []string, tagIDs []string) ([]universe.Security, error) {
	return nil, nil
}
func (m *mockSecurityRepo) GetDistinctGeographies() ([]string, error) { return nil, nil }
func (m *mockSecurityRepo) GetDistinctIndustries() ([]string, error)  { return nil, nil }
func (m *mockSecurityRepo) GetDistinctExchanges() ([]string, error)   { return nil, nil }
func (m *mockSecurityRepo) GetGeographiesAndIndustries() (map[string][]string, error) {
	return nil, nil
}
func (m *mockSecurityRepo) GetSecuritiesForOptimization() ([]universe.SecurityOptimizationData, error) {
	return nil, nil
}
func (m *mockSecurityRepo) GetSecuritiesForCharts() ([]universe.SecurityChartData, error) {
	return nil, nil
}
func (m *mockSecurityRepo) GetISINBySymbol(symbol string) (string, error) { return "", nil }
func (m *mockSecurityRepo) GetSymbolByISIN(isin string) (string, error)   { return "", nil }
func (m *mockSecurityRepo) BatchGetISINsBySymbols(symbols []string) (map[string]string, error) {
	return nil, nil
}
func (m *mockSecurityRepo) ExistsBySymbol(symbol string) (bool, error) { return false, nil }
func (m *mockSecurityRepo) CountTradable() (int, error)                { return 0, nil }
func (m *mockSecurityRepo) GetWithScores(portfolioDB *sql.DB) ([]universe.SecurityWithScore, error) {
	return nil, nil
}
func (m *mockSecurityRepo) Delete(isin string) error                                { return nil }
func (m *mockSecurityRepo) HardDelete(isin string) error                            { return nil }
func (m *mockSecurityRepo) SetTagsForSecurity(symbol string, tagIDs []string) error { return nil }
func (m *mockSecurityRepo) GetTagsForSecurity(symbol string) ([]string, error)      { return nil, nil }
func (m *mockSecurityRepo) GetTagsWithUpdateTimes(symbol string) (map[string]time.Time, error) {
	return nil, nil
}
func (m *mockSecurityRepo) UpdateSpecificTags(symbol string, tagIDs []string) error { return nil }

// mockOverrideRepo implements OverrideRepositoryInterface for testing
type mockOverrideRepo struct{}

func (m *mockOverrideRepo) SetOverride(isin, field, value string) error    { return nil }
func (m *mockOverrideRepo) GetOverride(isin, field string) (string, error) { return "", nil }
func (m *mockOverrideRepo) GetOverrides(isin string) (map[string]string, error) {
	return nil, nil
}
func (m *mockOverrideRepo) GetAllOverrides() (map[string]map[string]string, error) {
	return nil, nil
}
func (m *mockOverrideRepo) DeleteOverride(isin, field string) error { return nil }
func (m *mockOverrideRepo) DeleteAllOverrides(isin string) error    { return nil }
func (m *mockOverrideRepo) GetAllSecuritiesWithOverrides() (map[string]map[string]string, error) {
	return nil, nil
}

// setupDetectorTestDBs sets up all databases needed for detector calculation tests
func setupDetectorTestDBs(t *testing.T) (*sql.DB, *sql.DB, *sql.DB, *universe.HistoryDB) {
	// Universe DB - securities table
	universeDB, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)
	_, err = universeDB.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			name TEXT NOT NULL,
			product_type TEXT,
			market_code TEXT,
			active INTEGER DEFAULT 1,
			allow_buy INTEGER DEFAULT 1,
			allow_sell INTEGER DEFAULT 1,
			created_at INTEGER NOT NULL,
			updated_at INTEGER NOT NULL
		)
	`)
	require.NoError(t, err)

	// History DB - daily_prices table
	historyDB, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)
	_, err = historyDB.Exec(`
		CREATE TABLE daily_prices (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			isin TEXT NOT NULL,
			date INTEGER NOT NULL,
			open REAL,
			high REAL,
			low REAL,
			close REAL NOT NULL,
			volume INTEGER,
			adjusted_close REAL
		)
	`)
	require.NoError(t, err)

	// Config DB - market_regime_history table
	configDB := setupRegimeTestDB(t)

	// Create HistoryDB wrapper (nil filter for tests - no filtering)
	log := zerolog.New(nil).Level(zerolog.Disabled)
	historyDBClient := universe.NewHistoryDB(historyDB, nil, log)

	return universeDB, historyDB, configDB, historyDBClient
}

// insertTestIndex inserts a test index into the universe DB
func insertTestIndex(t *testing.T, universeDB *sql.DB, symbol, name, marketCode string) {
	isin := "INDEX-" + symbol
	_, err := universeDB.Exec(`
		INSERT INTO securities (isin, symbol, name, product_type, market_code, active, allow_buy, allow_sell, created_at, updated_at)
		VALUES (?, ?, ?, 'INDEX', ?, 1, 0, 0, 1704067200, 1704067200)
	`, isin, symbol, name, marketCode)
	require.NoError(t, err)
}

// insertTestPrices inserts test daily prices for an index
func insertTestPrices(t *testing.T, historyDB *sql.DB, symbol string, prices []float64) {
	isin := "INDEX-" + symbol
	baseDate := int64(1704067200) // 2024-01-01

	for i, price := range prices {
		date := baseDate + int64(i)*86400 // Add one day per price
		// Insert full OHLC data (use close for all OHLC since we only care about close for returns)
		_, err := historyDB.Exec(`
			INSERT INTO daily_prices (isin, date, open, high, low, close)
			VALUES (?, ?, ?, ?, ?, ?)
		`, isin, date, price, price, price, price)
		require.NoError(t, err)
	}
}

// ============================================================================
// Per-Region Detector Tests
// ============================================================================

func TestMarketRegimeDetector_GetRegimeScoreForSecurity(t *testing.T) {
	db := setupRegimeTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	persistence := NewRegimePersistence(db, log)
	detector := NewMarketRegimeDetector(log)
	detector.SetRegimePersistence(persistence)

	// Record scores for regions with indices
	_ = persistence.RecordRegimeScoreForRegion(RegionUS, MarketRegimeScore(0.4))
	_ = persistence.RecordRegimeScoreForRegion(RegionEU, MarketRegimeScore(0.2))
	_ = persistence.RecordRegimeScoreForRegion(RegionAsia, MarketRegimeScore(-0.1))

	// Test: US security gets US score
	usScore, err := detector.GetRegimeScoreForSecurity(RegionUS)
	require.NoError(t, err)
	assert.InDelta(t, 0.4, float64(usScore), 0.01)

	// Test: EU security gets EU score
	euScore, err := detector.GetRegimeScoreForSecurity(RegionEU)
	require.NoError(t, err)
	assert.InDelta(t, 0.2, float64(euScore), 0.01)

	// Test: Asia security gets Asia score
	asiaScore, err := detector.GetRegimeScoreForSecurity(RegionAsia)
	require.NoError(t, err)
	assert.InDelta(t, -0.1, float64(asiaScore), 0.01)
}

func TestMarketRegimeDetector_GetRegimeScoreForSecurity_GlobalAverageFallback(t *testing.T) {
	db := setupRegimeTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	persistence := NewRegimePersistence(db, log)
	detector := NewMarketRegimeDetector(log)
	detector.SetRegimePersistence(persistence)

	// Record scores for regions with indices
	_ = persistence.RecordRegimeScoreForRegion(RegionUS, MarketRegimeScore(0.6))
	_ = persistence.RecordRegimeScoreForRegion(RegionEU, MarketRegimeScore(0.3))
	_ = persistence.RecordRegimeScoreForRegion(RegionAsia, MarketRegimeScore(0.0))

	// Global average = (0.6 + 0.3 + 0.0) / 3 = 0.3

	// Test: RUSSIA security (no indices) gets global average
	russiaScore, err := detector.GetRegimeScoreForSecurity(RegionRussia)
	require.NoError(t, err)
	assert.InDelta(t, 0.3, float64(russiaScore), 0.01)

	// Test: MIDDLE_EAST security gets global average
	meScore, err := detector.GetRegimeScoreForSecurity(RegionMiddleEast)
	require.NoError(t, err)
	assert.InDelta(t, 0.3, float64(meScore), 0.01)

	// Test: UNKNOWN region gets global average
	unknownScore, err := detector.GetRegimeScoreForSecurity(RegionUnknown)
	require.NoError(t, err)
	assert.InDelta(t, 0.3, float64(unknownScore), 0.01)
}

func TestMarketRegimeDetector_GetCurrentRegimeScores(t *testing.T) {
	db := setupRegimeTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	persistence := NewRegimePersistence(db, log)
	detector := NewMarketRegimeDetector(log)
	detector.SetRegimePersistence(persistence)

	// Record scores
	_ = persistence.RecordRegimeScoreForRegion(RegionUS, MarketRegimeScore(0.5))
	_ = persistence.RecordRegimeScoreForRegion(RegionEU, MarketRegimeScore(0.3))
	_ = persistence.RecordRegimeScoreForRegion(RegionAsia, MarketRegimeScore(-0.2))

	// Get all scores
	scores, err := detector.GetCurrentRegimeScores()
	require.NoError(t, err)

	assert.InDelta(t, 0.5, scores[RegionUS], 0.01)
	assert.InDelta(t, 0.3, scores[RegionEU], 0.01)
	assert.InDelta(t, -0.2, scores[RegionAsia], 0.01)
}

func TestMarketRegimeDetector_GetCurrentRegimeScores_IncludesGlobalAverage(t *testing.T) {
	db := setupRegimeTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	persistence := NewRegimePersistence(db, log)
	detector := NewMarketRegimeDetector(log)
	detector.SetRegimePersistence(persistence)

	// Record scores for regions with indices
	_ = persistence.RecordRegimeScoreForRegion(RegionUS, MarketRegimeScore(0.6))
	_ = persistence.RecordRegimeScoreForRegion(RegionEU, MarketRegimeScore(0.3))
	_ = persistence.RecordRegimeScoreForRegion(RegionAsia, MarketRegimeScore(0.0))

	// Get all scores - should include computed global average
	scores, err := detector.GetCurrentRegimeScores()
	require.NoError(t, err)

	// Should have US, EU, ASIA plus GLOBAL_AVERAGE
	assert.Contains(t, scores, RegionUS)
	assert.Contains(t, scores, RegionEU)
	assert.Contains(t, scores, RegionAsia)
	assert.Contains(t, scores, "GLOBAL_AVERAGE")

	// Global average = (0.6 + 0.3 + 0.0) / 3 = 0.3
	assert.InDelta(t, 0.3, scores["GLOBAL_AVERAGE"], 0.01)
}

func TestMarketRegimeDetector_NoDataReturnsNeutral(t *testing.T) {
	db := setupRegimeTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	persistence := NewRegimePersistence(db, log)
	detector := NewMarketRegimeDetector(log)
	detector.SetRegimePersistence(persistence)

	// No data recorded

	// Test: Should return neutral for any region
	score, err := detector.GetRegimeScoreForSecurity(RegionUS)
	require.NoError(t, err)
	assert.Equal(t, NeutralScore, score)
}

func TestMarketRegimeDetector_PartialDataUsesAvailableRegions(t *testing.T) {
	db := setupRegimeTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	persistence := NewRegimePersistence(db, log)
	detector := NewMarketRegimeDetector(log)
	detector.SetRegimePersistence(persistence)

	// Only US data available
	_ = persistence.RecordRegimeScoreForRegion(RegionUS, MarketRegimeScore(0.6))

	// US security gets US score
	usScore, err := detector.GetRegimeScoreForSecurity(RegionUS)
	require.NoError(t, err)
	assert.InDelta(t, 0.6, float64(usScore), 0.01)

	// EU security (no EU data) gets global average (which is just US = 0.6)
	euScore, err := detector.GetRegimeScoreForSecurity(RegionEU)
	require.NoError(t, err)
	assert.InDelta(t, 0.6, float64(euScore), 0.01) // Only US available, so average is US

	// RUSSIA gets same global average
	russiaScore, err := detector.GetRegimeScoreForSecurity(RegionRussia)
	require.NoError(t, err)
	assert.InDelta(t, 0.6, float64(russiaScore), 0.01)
}

// ============================================================================
// Calculation Tests (requires index service with price data)
// ============================================================================

func TestCalculateRegimeScoreForRegion_BullMarket(t *testing.T) {
	universeDB, historyDB, configDB, historyDBClient := setupDetectorTestDBs(t)
	defer universeDB.Close()
	defer historyDB.Close()
	defer configDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create services
	indexService := NewMarketIndexService(&mockSecurityProvider{db: universeDB}, historyDBClient, nil, log)
	persistence := NewRegimePersistence(configDB, log)
	detector := NewMarketRegimeDetector(log)
	detector.SetMarketIndexService(indexService)
	detector.SetRegimePersistence(persistence)

	// Insert US index
	insertTestIndex(t, universeDB, "SP500.IDX", "S&P 500", "FIX")

	// Insert positive-return price data (prices increasing = positive returns)
	prices := []float64{100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0}
	insertTestPrices(t, historyDB, "SP500.IDX", prices)

	// Calculate regime score for US
	score, err := detector.CalculateRegimeScoreForRegion(RegionUS, 10)
	require.NoError(t, err)

	// With positive returns, score should be positive
	assert.Greater(t, float64(score), 0.0, "Positive returns should give positive score")

	// Verify score was persisted
	storedScore, err := persistence.GetCurrentRegimeScoreForRegion(RegionUS)
	require.NoError(t, err)
	assert.Equal(t, score, storedScore, "Stored score should match returned score")
}

func TestCalculateRegimeScoreForRegion_BearMarket(t *testing.T) {
	universeDB, historyDB, configDB, historyDBClient := setupDetectorTestDBs(t)
	defer universeDB.Close()
	defer historyDB.Close()
	defer configDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create services
	indexService := NewMarketIndexService(&mockSecurityProvider{db: universeDB}, historyDBClient, nil, log)
	persistence := NewRegimePersistence(configDB, log)
	detector := NewMarketRegimeDetector(log)
	detector.SetMarketIndexService(indexService)
	detector.SetRegimePersistence(persistence)

	// Insert EU index
	insertTestIndex(t, universeDB, "DAX.IDX", "DAX", "EU")

	// Insert negative-return price data (prices decreasing = negative returns)
	prices := []float64{110.0, 109.0, 108.0, 107.0, 106.0, 105.0, 104.0, 103.0, 102.0, 101.0, 100.0}
	insertTestPrices(t, historyDB, "DAX.IDX", prices)

	// Calculate regime score for EU
	score, err := detector.CalculateRegimeScoreForRegion(RegionEU, 10)
	require.NoError(t, err)

	// With negative returns, score should be negative
	assert.Less(t, float64(score), 0.0, "Negative returns should give negative score")
}

func TestCalculateRegimeScoreForRegion_NoIndicesForRegion(t *testing.T) {
	universeDB, historyDB, configDB, historyDBClient := setupDetectorTestDBs(t)
	defer universeDB.Close()
	defer historyDB.Close()
	defer configDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create services
	indexService := NewMarketIndexService(&mockSecurityProvider{db: universeDB}, historyDBClient, nil, log)
	persistence := NewRegimePersistence(configDB, log)
	detector := NewMarketRegimeDetector(log)
	detector.SetMarketIndexService(indexService)
	detector.SetRegimePersistence(persistence)

	// Try to calculate for region without indices (Russia)
	_, err := detector.CalculateRegimeScoreForRegion(RegionRussia, 10)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "no dedicated indices")
}

func TestCalculateRegimeScoreForRegion_MissingIndexService(t *testing.T) {
	configDB := setupRegimeTestDB(t)
	defer configDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)

	persistence := NewRegimePersistence(configDB, log)
	detector := NewMarketRegimeDetector(log)
	detector.SetRegimePersistence(persistence)
	// Note: Not setting index service

	_, err := detector.CalculateRegimeScoreForRegion(RegionUS, 10)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "market index service not set")
}

func TestCalculateAllRegionScores(t *testing.T) {
	universeDB, historyDB, configDB, historyDBClient := setupDetectorTestDBs(t)
	defer universeDB.Close()
	defer historyDB.Close()
	defer configDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create services
	indexService := NewMarketIndexService(&mockSecurityProvider{db: universeDB}, historyDBClient, nil, log)
	persistence := NewRegimePersistence(configDB, log)
	detector := NewMarketRegimeDetector(log)
	detector.SetMarketIndexService(indexService)
	detector.SetRegimePersistence(persistence)

	// Insert indices for all regions
	insertTestIndex(t, universeDB, "SP500.IDX", "S&P 500", "FIX")
	insertTestIndex(t, universeDB, "DAX.IDX", "DAX", "EU")
	insertTestIndex(t, universeDB, "HSI.IDX", "Hang Seng", "HKEX")

	// Insert price data - US bullish, EU bearish, Asia flat
	usPrices := []float64{100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0}
	euPrices := []float64{110.0, 109.0, 108.0, 107.0, 106.0, 105.0, 104.0, 103.0, 102.0, 101.0, 100.0}
	asiaPrices := []float64{100.0, 100.5, 99.5, 100.0, 100.5, 99.5, 100.0, 100.5, 99.5, 100.0, 100.0}

	insertTestPrices(t, historyDB, "SP500.IDX", usPrices)
	insertTestPrices(t, historyDB, "DAX.IDX", euPrices)
	insertTestPrices(t, historyDB, "HSI.IDX", asiaPrices)

	// Calculate all region scores
	scores, err := detector.CalculateAllRegionScores(10)
	require.NoError(t, err)

	// Should have US, EU, ASIA, and GLOBAL_AVERAGE
	assert.Contains(t, scores, RegionUS)
	assert.Contains(t, scores, RegionEU)
	assert.Contains(t, scores, RegionAsia)
	assert.Contains(t, scores, "GLOBAL_AVERAGE")

	// US should be positive (bullish)
	assert.Greater(t, scores[RegionUS], 0.0, "US should be positive")

	// EU should be negative (bearish)
	assert.Less(t, scores[RegionEU], 0.0, "EU should be negative")

	// Asia should be near zero (sideways)
	assert.InDelta(t, 0.0, scores[RegionAsia], 0.3, "Asia should be near neutral")
}

func TestCalculateAllRegionScores_PartialFailure(t *testing.T) {
	universeDB, historyDB, configDB, historyDBClient := setupDetectorTestDBs(t)
	defer universeDB.Close()
	defer historyDB.Close()
	defer configDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create services
	indexService := NewMarketIndexService(&mockSecurityProvider{db: universeDB}, historyDBClient, nil, log)
	persistence := NewRegimePersistence(configDB, log)
	detector := NewMarketRegimeDetector(log)
	detector.SetMarketIndexService(indexService)
	detector.SetRegimePersistence(persistence)

	// Only insert US index - EU and Asia will fail
	insertTestIndex(t, universeDB, "SP500.IDX", "S&P 500", "FIX")
	usPrices := []float64{100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0}
	insertTestPrices(t, historyDB, "SP500.IDX", usPrices)

	// Should still succeed with partial results
	scores, err := detector.CalculateAllRegionScores(10)
	require.NoError(t, err)

	// Should have US and GLOBAL_AVERAGE
	assert.Contains(t, scores, RegionUS)
	assert.Contains(t, scores, "GLOBAL_AVERAGE")

	// EU and Asia should not be present (failed)
	assert.NotContains(t, scores, RegionEU)
	assert.NotContains(t, scores, RegionAsia)
}

// ============================================================================
// Complete Flow Test - End-to-End Per-Region Regime Detection
// ============================================================================

func TestPerRegionRegimeDetection_CompleteFlow(t *testing.T) {
	universeDB, historyDB, configDB, historyDBClient := setupDetectorTestDBs(t)
	defer universeDB.Close()
	defer historyDB.Close()
	defer configDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Step 1: Create services
	securityRepo := &mockSecurityRepo{db: universeDB}
	overrideRepo := &mockOverrideRepo{}
	indexSyncService := NewIndexSyncService(securityRepo, overrideRepo, configDB, log)
	indexService := NewMarketIndexService(&mockSecurityProvider{db: universeDB}, historyDBClient, nil, log)
	persistence := NewRegimePersistence(configDB, log)
	detector := NewMarketRegimeDetector(log)
	detector.SetMarketIndexService(indexService)
	detector.SetRegimePersistence(persistence)

	// Step 2: Sync indices to securities table (simulates startup)
	err := indexSyncService.SyncIndicesToSecurities()
	require.NoError(t, err)

	// Verify indices exist
	var indexCount int
	err = universeDB.QueryRow(`SELECT COUNT(*) FROM securities WHERE product_type = 'INDEX'`).Scan(&indexCount)
	require.NoError(t, err)
	assert.Greater(t, indexCount, 0, "Should have synced indices to securities table")

	// Step 3: Insert test price data for each region's primary index
	// US - bull market (prices rising)
	insertTestPrices(t, historyDB, "SP500.IDX", []float64{
		100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0,
	})
	// EU - bear market (prices falling)
	insertTestPrices(t, historyDB, "DAX.IDX", []float64{
		110.0, 109.0, 108.0, 107.0, 106.0, 105.0, 104.0, 103.0, 102.0, 101.0, 100.0,
	})
	// Asia - sideways market (prices flat)
	insertTestPrices(t, historyDB, "HSI.IDX", []float64{
		100.0, 100.5, 99.5, 100.0, 100.5, 99.5, 100.0, 100.5, 99.5, 100.0, 100.0,
	})

	// Step 4: Calculate per-region regime scores
	scores, err := detector.CalculateAllRegionScores(10)
	require.NoError(t, err)

	// Step 5: Verify per-region scores
	assert.Contains(t, scores, RegionUS, "Should have US score")
	assert.Contains(t, scores, RegionEU, "Should have EU score")
	assert.Contains(t, scores, RegionAsia, "Should have ASIA score")
	assert.Contains(t, scores, "GLOBAL_AVERAGE", "Should have global average")

	// Verify market direction detection
	assert.Greater(t, scores[RegionUS], 0.0, "US bull market should have positive score")
	assert.Less(t, scores[RegionEU], 0.0, "EU bear market should have negative score")
	assert.InDelta(t, 0.0, scores[RegionAsia], 0.3, "Asia sideways market should be near neutral")

	// Step 6: Verify scores are persisted
	storedUS, err := persistence.GetCurrentRegimeScoreForRegion(RegionUS)
	require.NoError(t, err)
	assert.InDelta(t, scores[RegionUS], float64(storedUS), 0.01, "Stored US score should match calculated")

	storedEU, err := persistence.GetCurrentRegimeScoreForRegion(RegionEU)
	require.NoError(t, err)
	assert.InDelta(t, scores[RegionEU], float64(storedEU), 0.01, "Stored EU score should match calculated")

	// Step 7: Test GetRegimeScoreForSecurity
	// US security gets US score
	usSecurityScore, err := detector.GetRegimeScoreForSecurity(RegionUS)
	require.NoError(t, err)
	assert.InDelta(t, scores[RegionUS], float64(usSecurityScore), 0.01)

	// EU security gets EU score
	euSecurityScore, err := detector.GetRegimeScoreForSecurity(RegionEU)
	require.NoError(t, err)
	assert.InDelta(t, scores[RegionEU], float64(euSecurityScore), 0.01)

	// Russia security (no indices) gets global average
	russiaScore, err := detector.GetRegimeScoreForSecurity(RegionRussia)
	require.NoError(t, err)
	assert.InDelta(t, scores["GLOBAL_AVERAGE"], float64(russiaScore), 0.01)

	// Step 8: Test GetCurrentRegimeScores includes global average
	allScores, err := detector.GetCurrentRegimeScores()
	require.NoError(t, err)
	assert.Contains(t, allScores, "GLOBAL_AVERAGE")
	assert.InDelta(t, scores["GLOBAL_AVERAGE"], allScores["GLOBAL_AVERAGE"], 0.01)
}
