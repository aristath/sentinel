package universe

import (
	"database/sql"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	_ "github.com/mattn/go-sqlite3"
)

// setupTestDBWithMarketCode creates a test database with JSON storage schema
func setupTestDBWithMarketCode(t *testing.T) *sql.DB {
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

	// Create tags table (needed for scanSecurity)
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

func TestCreate_WithMarketCode(t *testing.T) {
	db := setupTestDBWithMarketCode(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Create security with market_code
	security := Security{
		ISIN:       "US0378331005",
		Symbol:     "AAPL.US",
		Name:       "Apple Inc.",
		MarketCode: "FIX",
		AllowBuy:   true,
		AllowSell:  true,
	}

	err := repo.Create(security)
	require.NoError(t, err)

	// Verify creation
	created, err := repo.GetByISIN("US0378331005")
	require.NoError(t, err)
	require.NotNil(t, created)
	assert.Equal(t, "FIX", created.MarketCode)
}

func TestGetByISIN_ReturnsMarketCode(t *testing.T) {
	db := setupTestDBWithMarketCode(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Insert test data with market_code
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES ('US0378331005', 'AAPL.US', json_object('name', 'Apple Inc.', 'market_code', 'FIX'), NULL)
	`)
	require.NoError(t, err)

	// Execute
	security, err := repo.GetByISIN("US0378331005")

	// Assert
	require.NoError(t, err)
	require.NotNil(t, security)
	assert.Equal(t, "FIX", security.MarketCode)
}

func TestUpdate_MarketCode(t *testing.T) {
	db := setupTestDBWithMarketCode(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Insert test data
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES ('US0378331005', 'AAPL.US', json_object('name', 'Apple Inc.', 'market_code', 'FIX'), NULL)
	`)
	require.NoError(t, err)

	// Update market_code
	err = repo.Update("US0378331005", map[string]interface{}{
		"market_code": "EU",
	})
	require.NoError(t, err)

	// Verify update
	security, err := repo.GetByISIN("US0378331005")
	require.NoError(t, err)
	require.NotNil(t, security)
	assert.Equal(t, "EU", security.MarketCode)
}

func TestGetByMarketCode(t *testing.T) {
	db := setupTestDBWithMarketCode(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Insert test data with different market codes
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced) VALUES
		('US0378331005', 'AAPL.US', json_object('name', 'Apple Inc.', 'market_code', 'FIX'), NULL),
		('US5949181045', 'MSFT.US', json_object('name', 'Microsoft', 'market_code', 'FIX'), NULL),
		('DE0007164600', 'SAP.EU', json_object('name', 'SAP SE', 'market_code', 'EU'), NULL),
		('HK0000069689', 'BYD.AS', json_object('name', 'BYD Company', 'market_code', 'HKEX'), NULL)
	`)
	require.NoError(t, err)

	// Test GetByMarketCode for FIX (US markets)
	fixSecurities, err := repo.GetByMarketCode("FIX")
	require.NoError(t, err)
	assert.Len(t, fixSecurities, 2) // AAPL and MSFT
	for _, sec := range fixSecurities {
		assert.Equal(t, "FIX", sec.MarketCode)
	}

	// Test GetByMarketCode for EU
	euSecurities, err := repo.GetByMarketCode("EU")
	require.NoError(t, err)
	assert.Len(t, euSecurities, 1)
	assert.Equal(t, "SAP.EU", euSecurities[0].Symbol)

	// Test GetByMarketCode for HKEX
	hkexSecurities, err := repo.GetByMarketCode("HKEX")
	require.NoError(t, err)
	assert.Len(t, hkexSecurities, 1)
	assert.Equal(t, "BYD.AS", hkexSecurities[0].Symbol)

	// Test GetByMarketCode for non-existent market code
	unknownSecurities, err := repo.GetByMarketCode("UNKNOWN")
	require.NoError(t, err)
	assert.Len(t, unknownSecurities, 0)
}

func TestGetAllActive_IncludesMarketCode(t *testing.T) {
	db := setupTestDBWithMarketCode(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Insert test data
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES ('US0378331005', 'AAPL.US', json_object('name', 'Apple Inc.', 'market_code', 'FIX'), NULL)
	`)
	require.NoError(t, err)

	// Execute
	securities, err := repo.GetAllActive()
	require.NoError(t, err)
	require.Len(t, securities, 1)
	assert.Equal(t, "FIX", securities[0].MarketCode)
}

func TestMarketCode_EmptyIsValid(t *testing.T) {
	db := setupTestDBWithMarketCode(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Create security without market_code
	security := Security{
		ISIN:      "US0378331005",
		Symbol:    "AAPL.US",
		Name:      "Apple Inc.",
		AllowBuy:  true,
		AllowSell: true,
		// MarketCode intentionally empty
	}

	err := repo.Create(security)
	require.NoError(t, err)

	// Verify creation - empty market_code is valid
	created, err := repo.GetByISIN("US0378331005")
	require.NoError(t, err)
	require.NotNil(t, created)
	assert.Equal(t, "", created.MarketCode)
}
