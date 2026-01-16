package universe

import (
	"database/sql"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	_ "github.com/mattn/go-sqlite3"
)

func setupTestDBWithISINPrimaryKey(t *testing.T) *sql.DB {
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

	// Create index on symbol for lookups
	_, err = db.Exec(`CREATE INDEX IF NOT EXISTS idx_securities_symbol ON securities(symbol)`)
	require.NoError(t, err)

	// Create tags tables (needed for HardDelete)
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

	// Create broker_symbols table (needed for HardDelete)
	_, err = db.Exec(`
		CREATE TABLE broker_symbols (
			isin TEXT NOT NULL,
			broker TEXT NOT NULL,
			symbol TEXT NOT NULL,
			created_at INTEGER NOT NULL,
			updated_at INTEGER NOT NULL,
			PRIMARY KEY (isin, broker)
		)
	`)
	require.NoError(t, err)

	// Create client_symbols table (needed for HardDelete)
	_, err = db.Exec(`
		CREATE TABLE client_symbols (
			isin TEXT NOT NULL,
			client TEXT NOT NULL,
			symbol TEXT NOT NULL,
			created_at INTEGER NOT NULL,
			updated_at INTEGER NOT NULL,
			PRIMARY KEY (isin, client)
		)
	`)
	require.NoError(t, err)

	return db
}

func TestGetByISIN_PrimaryMethod(t *testing.T) {
	db := setupTestDBWithISINPrimaryKey(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Insert test data
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES ('US0378331005', 'AAPL.US', json_object('name', 'Apple Inc.'), NULL)
	`)
	require.NoError(t, err)

	// Execute
	security, err := repo.GetByISIN("US0378331005")

	// Assert
	require.NoError(t, err)
	require.NotNil(t, security)
	assert.Equal(t, "US0378331005", security.ISIN)
	assert.Equal(t, "AAPL.US", security.Symbol)
	assert.Equal(t, "Apple Inc.", security.Name)
}

func TestGetByISIN_NotFound(t *testing.T) {
	db := setupTestDBWithISINPrimaryKey(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Execute
	security, err := repo.GetByISIN("US0000000000")

	// Assert
	require.NoError(t, err)
	assert.Nil(t, security)
}

func TestGetBySymbol_HelperMethod_LooksUpISINFirst(t *testing.T) {
	db := setupTestDBWithISINPrimaryKey(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Insert test data
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES ('US0378331005', 'AAPL.US', json_object('name', 'Apple Inc.'), NULL)
	`)
	require.NoError(t, err)

	// Execute - GetBySymbol should lookup ISIN first, then query by ISIN
	security, err := repo.GetBySymbol("AAPL.US")

	// Assert
	require.NoError(t, err)
	require.NotNil(t, security)
	assert.Equal(t, "US0378331005", security.ISIN)
	assert.Equal(t, "AAPL.US", security.Symbol)
}

func TestUpdate_ByISIN(t *testing.T) {
	db := setupTestDBWithISINPrimaryKey(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Insert test data
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES ('US0378331005', 'AAPL.US', json_object('name', 'Apple Inc.', 'geography', 'US'), NULL)
	`)
	require.NoError(t, err)

	// Execute - Update should use ISIN
	err = repo.Update("US0378331005", map[string]interface{}{
		"name":      "Apple Inc. Updated",
		"geography": "CN",
	})
	require.NoError(t, err)

	// Verify update
	security, err := repo.GetByISIN("US0378331005")
	require.NoError(t, err)
	require.NotNil(t, security)
	assert.Equal(t, "Apple Inc. Updated", security.Name)
	assert.Equal(t, "CN", security.Geography)
}

func TestDelete_ByISIN(t *testing.T) {
	db := setupTestDBWithISINPrimaryKey(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Insert test data
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES ('US0378331005', 'AAPL.US', json_object('name', 'Apple Inc.'), NULL)
	`)
	require.NoError(t, err)

	// Execute - HardDelete should use ISIN (hard delete in new schema)
	err = repo.HardDelete("US0378331005")
	require.NoError(t, err)

	// Verify hard delete (security no longer exists)
	security, err := repo.GetByISIN("US0378331005")
	require.NoError(t, err)
	assert.Nil(t, security, "Security should be deleted (hard delete)")
}

func TestCreate_WithISINAsPrimaryKey(t *testing.T) {
	db := setupTestDBWithISINPrimaryKey(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Execute - Create should use ISIN as PRIMARY KEY
	security := Security{
		ISIN:      "US0378331005",
		Symbol:    "AAPL.US",
		Name:      "Apple Inc.",
		AllowBuy:  true,
		AllowSell: true,
	}

	err := repo.Create(security)
	require.NoError(t, err)

	// Verify creation
	created, err := repo.GetByISIN("US0378331005")
	require.NoError(t, err)
	require.NotNil(t, created)
	assert.Equal(t, "US0378331005", created.ISIN)
	assert.Equal(t, "AAPL.US", created.Symbol)
	assert.Equal(t, "Apple Inc.", created.Name)
}

func TestGetBySymbol_FallbackToSymbolLookup(t *testing.T) {
	db := setupTestDBWithISINPrimaryKey(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Insert test data
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES ('US0378331005', 'AAPL.US', json_object('name', 'Apple Inc.'), NULL)
	`)
	require.NoError(t, err)

	// GetBySymbol should lookup by symbol column (indexed)
	security, err := repo.GetBySymbol("AAPL.US")

	// Assert
	require.NoError(t, err)
	require.NotNil(t, security)
	assert.Equal(t, "US0378331005", security.ISIN)
	assert.Equal(t, "AAPL.US", security.Symbol)
}

func TestGetByIdentifier_PrioritizesISIN(t *testing.T) {
	db := setupTestDBWithISINPrimaryKey(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Insert test data
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES ('US0378331005', 'AAPL.US', json_object('name', 'Apple Inc.'), NULL)
	`)
	require.NoError(t, err)

	// Test with ISIN
	security, err := repo.GetByIdentifier("US0378331005")
	require.NoError(t, err)
	require.NotNil(t, security)
	assert.Equal(t, "US0378331005", security.ISIN)

	// Test with symbol
	security, err = repo.GetByIdentifier("AAPL.US")
	require.NoError(t, err)
	require.NotNil(t, security)
	assert.Equal(t, "AAPL.US", security.Symbol)
}
