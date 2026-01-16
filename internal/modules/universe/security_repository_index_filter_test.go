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

// setupTestDBForIndexFiltering creates a test database with JSON storage schema
func setupTestDBForIndexFiltering(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite3", ":memory:")
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

	// Create indices
	_, err = db.Exec(`CREATE INDEX IF NOT EXISTS idx_securities_symbol ON securities(symbol)`)
	require.NoError(t, err)

	// Create tags tables (needed for scanSecurity)
	_, err = db.Exec(`
		CREATE TABLE tags (
			id TEXT PRIMARY KEY,
			name TEXT NOT NULL,
			created_at INTEGER NOT NULL,
			updated_at INTEGER NOT NULL
		)
	`)
	require.NoError(t, err)

	_, err = db.Exec(`
		CREATE TABLE security_tags (
			isin TEXT NOT NULL,
			tag_id TEXT NOT NULL,
			created_at INTEGER NOT NULL,
			updated_at INTEGER NOT NULL,
			PRIMARY KEY (isin, tag_id)
		)
	`)
	require.NoError(t, err)

	return db
}

// insertTestSecurities inserts test securities including indices
func insertTestSecurities(t *testing.T, db *sql.DB) {
	// Insert regular securities (EQUITY, ETF)
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced) VALUES
		('US0378331005', 'AAPL.US', json_object('name', 'Apple Inc.', 'product_type', 'EQUITY', 'market_code', 'FIX', 'fullExchangeName', 'NASDAQ'), NULL),
		('US5949181045', 'MSFT.US', json_object('name', 'Microsoft Corp', 'product_type', 'EQUITY', 'market_code', 'FIX', 'fullExchangeName', 'NASDAQ'), NULL),
		('IE00B3XXRP09', 'VUSA.EU', json_object('name', 'Vanguard S&P 500 ETF', 'product_type', 'ETF', 'market_code', 'EU', 'fullExchangeName', 'LSE'), NULL),
		('US0000000001', 'NULL_TYPE.US', json_object('name', 'Security with NULL type', 'market_code', 'FIX', 'fullExchangeName', 'NYSE'), NULL)
	`)
	require.NoError(t, err)

	// Insert market indices (should be excluded from tradable queries)
	_, err = db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced) VALUES
		('INDEX-SP500.IDX', 'SP500.IDX', json_object('name', 'S&P 500', 'product_type', 'INDEX', 'market_code', 'FIX'), NULL),
		('INDEX-NASDAQ.IDX', 'NASDAQ.IDX', json_object('name', 'NASDAQ Composite', 'product_type', 'INDEX', 'market_code', 'FIX'), NULL),
		('INDEX-DAX.IDX', 'DAX.IDX', json_object('name', 'DAX (Germany)', 'product_type', 'INDEX', 'market_code', 'EU'), NULL)
	`)
	require.NoError(t, err)
}

func TestGetAllActive_ExcludesIndices(t *testing.T) {
	db := setupTestDBForIndexFiltering(t)
	defer db.Close()
	insertTestSecurities(t, db)

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	securities, err := repo.GetAllActive()
	require.NoError(t, err)

	// Should return 4 securities (3 tradable + 1 NULL type), excluding 3 indices and 1 inactive
	assert.Len(t, securities, 4)

	// Verify no indices in result
	for _, sec := range securities {
		assert.NotEqual(t, "INDEX", sec.ProductType, "Index %s should be excluded", sec.Symbol)
		assert.NotContains(t, sec.Symbol, ".IDX", "Index symbol %s should be excluded", sec.Symbol)
	}
}

func TestGetAllActive_IncludesNullProductType(t *testing.T) {
	db := setupTestDBForIndexFiltering(t)
	defer db.Close()
	insertTestSecurities(t, db)

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	securities, err := repo.GetAllActive()
	require.NoError(t, err)

	// Verify NULL product_type security is included
	var foundNullType bool
	for _, sec := range securities {
		if sec.Symbol == "NULL_TYPE.US" {
			foundNullType = true
			assert.Equal(t, "", sec.ProductType) // NULL scans as empty string
			break
		}
	}
	assert.True(t, foundNullType, "Security with NULL product_type should be included")
}

func TestGetAllActiveTradable_ExcludesIndices(t *testing.T) {
	db := setupTestDBForIndexFiltering(t)
	defer db.Close()
	insertTestSecurities(t, db)

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	securities, err := repo.GetAllActiveTradable()
	require.NoError(t, err)

	// Should return 4 tradable securities, excluding indices
	assert.Len(t, securities, 4)

	// Verify no indices in result
	for _, sec := range securities {
		assert.NotEqual(t, "INDEX", sec.ProductType, "Index %s should be excluded", sec.Symbol)
	}
}

func TestGetByMarketCode_ExcludesIndices(t *testing.T) {
	db := setupTestDBForIndexFiltering(t)
	defer db.Close()
	insertTestSecurities(t, db)

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Test FIX market code - should return AAPL, MSFT, NULL_TYPE but not SP500.IDX, NASDAQ.IDX
	fixSecurities, err := repo.GetByMarketCode("FIX")
	require.NoError(t, err)
	assert.Len(t, fixSecurities, 3) // AAPL, MSFT, NULL_TYPE

	for _, sec := range fixSecurities {
		assert.NotEqual(t, "INDEX", sec.ProductType, "Index %s should be excluded", sec.Symbol)
	}

	// Test EU market code - should return VUSA but not DAX.IDX
	euSecurities, err := repo.GetByMarketCode("EU")
	require.NoError(t, err)
	assert.Len(t, euSecurities, 1) // VUSA only
	assert.Equal(t, "VUSA.EU", euSecurities[0].Symbol)
}

func TestGetDistinctExchanges_ExcludesIndices(t *testing.T) {
	db := setupTestDBForIndexFiltering(t)
	defer db.Close()
	insertTestSecurities(t, db)

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	exchanges, err := repo.GetDistinctExchanges()
	require.NoError(t, err)

	// Should return NASDAQ, LSE, NYSE (from tradable securities)
	// Indices have NULL fullExchangeName, so they wouldn't appear anyway
	assert.Contains(t, exchanges, "NASDAQ")
	assert.Contains(t, exchanges, "LSE")
	assert.Contains(t, exchanges, "NYSE")
}

func TestGetByTags_ExcludesIndices(t *testing.T) {
	db := setupTestDBForIndexFiltering(t)
	defer db.Close()
	insertTestSecurities(t, db)

	now := time.Now().Unix()

	// Create a tag
	_, err := db.Exec(`INSERT INTO tags (id, name, created_at, updated_at) VALUES ('test-tag', 'Test Tag', ?, ?)`, now, now)
	require.NoError(t, err)

	// Associate tag with both a regular security and an index
	_, err = db.Exec(`INSERT INTO security_tags (isin, tag_id, created_at, updated_at) VALUES
		('US0378331005', 'test-tag', ?, ?),
		('INDEX-SP500.IDX', 'test-tag', ?, ?)
	`, now, now, now, now)
	require.NoError(t, err)

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	securities, err := repo.GetByTags([]string{"test-tag"})
	require.NoError(t, err)

	// Should return only AAPL (regular security), not SP500.IDX (index)
	assert.Len(t, securities, 1)
	assert.Equal(t, "AAPL.US", securities[0].Symbol)
}
