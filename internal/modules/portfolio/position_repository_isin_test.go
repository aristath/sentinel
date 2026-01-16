package portfolio

import (
	"database/sql"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	_ "github.com/mattn/go-sqlite3"
)

func setupTestDBForPositionsWithISIN(t *testing.T) (*sql.DB, *sql.DB) {
	portfolioDB, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)

	// Create positions table with ISIN as PRIMARY KEY (post-migration schema)
	_, err = portfolioDB.Exec(`
		CREATE TABLE positions (
			isin TEXT PRIMARY KEY,
			quantity REAL NOT NULL,
			avg_price REAL NOT NULL,
			current_price REAL,
			currency TEXT,
			currency_rate REAL DEFAULT 1.0,
			market_value_eur REAL,
			cost_basis_eur REAL,
			unrealized_pnl REAL,
			unrealized_pnl_pct REAL,
			last_updated TEXT,
			first_bought TEXT,
			last_sold TEXT,
			symbol TEXT
		)
	`)
	require.NoError(t, err)

	// Create index on symbol for lookups
	_, err = portfolioDB.Exec(`CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)`)
	require.NoError(t, err)

	// Create universe DB with securities table
	universeDB, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)

	_, err = universeDB.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			data TEXT NOT NULL,
			last_synced INTEGER
		) STRICT
	`)
	require.NoError(t, err)

	return portfolioDB, universeDB
}

func TestPositionRepository_GetByISIN_PrimaryMethod(t *testing.T) {
	portfolioDB, universeDB := setupTestDBForPositionsWithISIN(t)
	defer portfolioDB.Close()
	defer universeDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewPositionRepository(portfolioDB, universeDB, nil, log)

	// Insert test data
	_, err := portfolioDB.Exec(`
		INSERT INTO positions (isin, symbol, quantity, avg_price, currency)
		VALUES ('US0378331005', 'AAPL.US', 10.0, 150.0, 'USD')
	`)
	require.NoError(t, err)

	// Execute
	position, err := repo.GetByISIN("US0378331005")

	// Assert
	require.NoError(t, err)
	require.NotNil(t, position)
	assert.Equal(t, "US0378331005", position.ISIN)
	assert.Equal(t, "AAPL.US", position.Symbol)
	assert.Equal(t, 10.0, position.Quantity)
}

func TestPositionRepository_GetByISIN_NotFound(t *testing.T) {
	portfolioDB, universeDB := setupTestDBForPositionsWithISIN(t)
	defer portfolioDB.Close()
	defer universeDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewPositionRepository(portfolioDB, universeDB, nil, log)

	// Execute
	position, err := repo.GetByISIN("US0000000000")

	// Assert
	require.NoError(t, err)
	assert.Nil(t, position)
}

func TestPositionRepository_GetBySymbol_HelperMethod(t *testing.T) {
	portfolioDB, universeDB := setupTestDBForPositionsWithISIN(t)
	defer portfolioDB.Close()
	defer universeDB.Close()

	// Insert security (JSON storage - migration 038)
	_, err := universeDB.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES ('US0378331005', 'AAPL.US', json_object('name', 'Apple Inc.'), NULL)
	`)
	require.NoError(t, err)

	// Insert position
	_, err = portfolioDB.Exec(`
		INSERT INTO positions (isin, symbol, quantity, avg_price, currency)
		VALUES ('US0378331005', 'AAPL.US', 10.0, 150.0, 'USD')
	`)
	require.NoError(t, err)

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityProvider := newTestSecurityProvider(universeDB, log)
	repo := NewPositionRepository(portfolioDB, universeDB, securityProvider, log)

	// GetBySymbol should lookup ISIN first, then query by ISIN
	position, err := repo.GetBySymbol("AAPL.US")
	require.NoError(t, err)
	require.NotNil(t, position)
	assert.Equal(t, "US0378331005", position.ISIN)
	assert.Equal(t, "AAPL.US", position.Symbol)
}

func TestPositionRepository_Delete_ByISIN(t *testing.T) {
	portfolioDB, universeDB := setupTestDBForPositionsWithISIN(t)
	defer portfolioDB.Close()
	defer universeDB.Close()

	// Insert test data
	_, err := portfolioDB.Exec(`
		INSERT INTO positions (isin, symbol, quantity, avg_price, currency)
		VALUES ('US0378331005', 'AAPL.US', 10.0, 150.0, 'USD')
	`)
	require.NoError(t, err)

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewPositionRepository(portfolioDB, universeDB, nil, log)

	// Execute - Delete should use ISIN
	err = repo.Delete("US0378331005")
	require.NoError(t, err)

	// Verify deletion
	position, err := repo.GetByISIN("US0378331005")
	require.NoError(t, err)
	assert.Nil(t, position, "Position should be deleted")
}

func TestPositionRepository_UpdatePrice_ByISIN(t *testing.T) {
	portfolioDB, universeDB := setupTestDBForPositionsWithISIN(t)
	defer portfolioDB.Close()
	defer universeDB.Close()

	// Insert test data
	_, err := portfolioDB.Exec(`
		INSERT INTO positions (isin, symbol, quantity, avg_price, currency, current_price)
		VALUES ('US0378331005', 'AAPL.US', 10.0, 150.0, 'USD', 150.0)
	`)
	require.NoError(t, err)

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewPositionRepository(portfolioDB, universeDB, nil, log)

	// Execute - UpdatePrice should use ISIN
	err = repo.UpdatePrice("US0378331005", 160.0, 1.0)
	require.NoError(t, err)

	// Verify update
	position, err := repo.GetByISIN("US0378331005")
	require.NoError(t, err)
	require.NotNil(t, position)
	assert.Equal(t, 160.0, position.CurrentPrice)
}
