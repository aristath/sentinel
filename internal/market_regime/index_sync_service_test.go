package market_regime

import (
	"database/sql"
	"testing"

	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	_ "github.com/mattn/go-sqlite3"
)

func setupUniverseTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)

	// Enable foreign keys
	_, err = db.Exec("PRAGMA foreign_keys = ON")
	require.NoError(t, err)

	// Create securities table with JSON storage (migration 038 schema)
	_, err = db.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			data TEXT NOT NULL,
			last_synced INTEGER
		) STRICT
	`)
	require.NoError(t, err)

	// Create index on symbol for lookups
	_, err = db.Exec(`CREATE INDEX IF NOT EXISTS idx_securities_symbol ON securities(symbol)`)
	require.NoError(t, err)

	// Create security_overrides table (EAV pattern for user customizations)
	_, err = db.Exec(`
		CREATE TABLE security_overrides (
			isin TEXT NOT NULL,
			field TEXT NOT NULL,
			value TEXT NOT NULL,
			created_at INTEGER NOT NULL,
			updated_at INTEGER NOT NULL,
			PRIMARY KEY (isin, field),
			FOREIGN KEY (isin) REFERENCES securities(isin) ON DELETE CASCADE
		)
	`)
	require.NoError(t, err)

	return db
}

func TestIndexSyncService_SyncIndicesToSecurities(t *testing.T) {
	universeDB := setupUniverseTestDB(t)
	defer universeDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityRepo := universe.NewSecurityRepository(universeDB, log)
	overrideRepo := universe.NewOverrideRepository(universeDB, log)
	service := NewIndexSyncService(securityRepo, overrideRepo, nil, log)

	// Execute
	err := service.SyncIndicesToSecurities()
	require.NoError(t, err)

	// Verify indices were created
	var count int
	err = universeDB.QueryRow(`SELECT COUNT(*) FROM securities WHERE json_extract(data, '$.product_type') = 'INDEX'`).Scan(&count)
	require.NoError(t, err)

	// Should have all known indices
	knownCount := len(GetKnownIndices())
	assert.Equal(t, knownCount, count, "All known indices should be in securities table")

	// Verify specific index using JSON extraction
	var isin, symbol, name, productType, marketCode string
	err = universeDB.QueryRow(`
		SELECT isin, symbol,
		       json_extract(data, '$.name') as name,
		       json_extract(data, '$.product_type') as product_type,
		       json_extract(data, '$.market_code') as market_code
		FROM securities WHERE symbol = 'SP500.IDX'
	`).Scan(&isin, &symbol, &name, &productType, &marketCode)
	require.NoError(t, err)

	assert.Equal(t, "INDEX-SP500.IDX", isin)
	assert.Equal(t, "SP500.IDX", symbol)
	assert.Equal(t, "S&P 500", name)
	assert.Equal(t, "INDEX", productType)
	assert.Equal(t, "FIX", marketCode)

	// Verify allow_buy and allow_sell are set to false via security_overrides
	var allowBuyValue, allowSellValue string
	err = universeDB.QueryRow(`
		SELECT value FROM security_overrides WHERE isin = 'INDEX-SP500.IDX' AND field = 'allow_buy'
	`).Scan(&allowBuyValue)
	require.NoError(t, err)
	assert.Equal(t, "false", allowBuyValue, "Indices should not be buyable")

	err = universeDB.QueryRow(`
		SELECT value FROM security_overrides WHERE isin = 'INDEX-SP500.IDX' AND field = 'allow_sell'
	`).Scan(&allowSellValue)
	require.NoError(t, err)
	assert.Equal(t, "false", allowSellValue, "Indices should not be sellable")
}

func TestIndexSyncService_Idempotent(t *testing.T) {
	universeDB := setupUniverseTestDB(t)
	defer universeDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityRepo := universe.NewSecurityRepository(universeDB, log)
	overrideRepo := universe.NewOverrideRepository(universeDB, log)
	service := NewIndexSyncService(securityRepo, overrideRepo, nil, log)

	// Execute twice
	err := service.SyncIndicesToSecurities()
	require.NoError(t, err)

	err = service.SyncIndicesToSecurities()
	require.NoError(t, err)

	// Verify no duplicates
	var count int
	err = universeDB.QueryRow(`SELECT COUNT(*) FROM securities WHERE json_extract(data, '$.product_type') = 'INDEX'`).Scan(&count)
	require.NoError(t, err)

	knownCount := len(GetKnownIndices())
	assert.Equal(t, knownCount, count, "Should not create duplicates on second run")
}

func TestIndexSyncService_EnsureIndexExists(t *testing.T) {
	universeDB := setupUniverseTestDB(t)
	defer universeDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityRepo := universe.NewSecurityRepository(universeDB, log)
	overrideRepo := universe.NewOverrideRepository(universeDB, log)
	service := NewIndexSyncService(securityRepo, overrideRepo, nil, log)

	// Test creating a new index
	isin, err := service.EnsureIndexExists("DAX.IDX")
	require.NoError(t, err)
	assert.Equal(t, "INDEX-DAX.IDX", isin)

	// Verify it was created (using JSON extraction for name field after migration 038)
	var name string
	err = universeDB.QueryRow(`SELECT json_extract(data, '$.name') FROM securities WHERE isin = ?`, isin).Scan(&name)
	require.NoError(t, err)
	assert.Equal(t, "DAX (Germany)", name)

	// Test calling again (upsert)
	isin2, err := service.EnsureIndexExists("DAX.IDX")
	require.NoError(t, err)
	assert.Equal(t, isin, isin2)

	// Verify only one entry
	var count int
	err = universeDB.QueryRow(`SELECT COUNT(*) FROM securities WHERE symbol = 'DAX.IDX'`).Scan(&count)
	require.NoError(t, err)
	assert.Equal(t, 1, count)
}

func TestIndexSyncService_EnsureIndexExists_UnknownSymbol(t *testing.T) {
	universeDB := setupUniverseTestDB(t)
	defer universeDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityRepo := universe.NewSecurityRepository(universeDB, log)
	overrideRepo := universe.NewOverrideRepository(universeDB, log)
	service := NewIndexSyncService(securityRepo, overrideRepo, nil, log)

	// Test with unknown symbol
	_, err := service.EnsureIndexExists("UNKNOWN.IDX")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "unknown index symbol")
}

func TestIndexSyncService_GetIndicesWithISIN(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	service := NewIndexSyncService(nil, nil, nil, log)

	indices := service.GetIndicesWithISIN()

	// Should have all PRICE indices (not VOLATILITY like VIX)
	assert.Greater(t, len(indices), 0, "Should return indices")

	// Verify format
	for _, idx := range indices {
		assert.NotEmpty(t, idx.Symbol)
		assert.Equal(t, "INDEX-"+idx.Symbol, idx.ISIN)
		assert.NotEmpty(t, idx.Region)
	}

	// Verify VIX is NOT included (it's VOLATILITY type)
	for _, idx := range indices {
		assert.NotEqual(t, "VIX.IDX", idx.Symbol, "VIX should not be in PRICE indices")
	}
}

func TestIndexSyncService_SyncAll(t *testing.T) {
	universeDB := setupUniverseTestDB(t)
	defer universeDB.Close()

	configDB := setupIndexTestDB(t)
	defer configDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityRepo := universe.NewSecurityRepository(universeDB, log)
	overrideRepo := universe.NewOverrideRepository(universeDB, log)
	service := NewIndexSyncService(securityRepo, overrideRepo, configDB, log)

	// Execute
	err := service.SyncAll()
	require.NoError(t, err)

	// Verify indices in securities table
	var secCount int
	err = universeDB.QueryRow(`SELECT COUNT(*) FROM securities WHERE json_extract(data, '$.product_type') = 'INDEX'`).Scan(&secCount)
	require.NoError(t, err)
	assert.Greater(t, secCount, 0, "Should have indices in securities table")

	// Verify indices in market_indices table
	var configCount int
	err = configDB.QueryRow(`SELECT COUNT(*) FROM market_indices`).Scan(&configCount)
	require.NoError(t, err)
	assert.Greater(t, configCount, 0, "Should have indices in market_indices table")
}

func TestIndexSyncService_RegionMapping(t *testing.T) {
	universeDB := setupUniverseTestDB(t)
	defer universeDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityRepo := universe.NewSecurityRepository(universeDB, log)
	overrideRepo := universe.NewOverrideRepository(universeDB, log)
	service := NewIndexSyncService(securityRepo, overrideRepo, nil, log)

	err := service.SyncIndicesToSecurities()
	require.NoError(t, err)

	// Verify US indices have FIX market code
	var usMarketCode string
	err = universeDB.QueryRow(`SELECT json_extract(data, '$.market_code') FROM securities WHERE symbol = 'SP500.IDX'`).Scan(&usMarketCode)
	require.NoError(t, err)
	assert.Equal(t, "FIX", usMarketCode)

	// Verify EU indices have EU market code
	var euMarketCode string
	err = universeDB.QueryRow(`SELECT json_extract(data, '$.market_code') FROM securities WHERE symbol = 'DAX.IDX'`).Scan(&euMarketCode)
	require.NoError(t, err)
	assert.Equal(t, "EU", euMarketCode)

	// Verify Asia indices have HKEX market code
	var asiaMarketCode string
	err = universeDB.QueryRow(`SELECT json_extract(data, '$.market_code') FROM securities WHERE symbol = 'HSI.IDX'`).Scan(&asiaMarketCode)
	require.NoError(t, err)
	assert.Equal(t, "HKEX", asiaMarketCode)
}
