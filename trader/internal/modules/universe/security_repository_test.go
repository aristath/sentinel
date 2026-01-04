package universe

import (
	"database/sql"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	_ "github.com/mattn/go-sqlite3"
)

func setupTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)

	// Create securities table
	_, err = db.Exec(`
		CREATE TABLE securities (
			symbol TEXT PRIMARY KEY,
			yahoo_symbol TEXT,
			isin TEXT,
			name TEXT NOT NULL,
			product_type TEXT,
			industry TEXT,
			country TEXT,
			fullExchangeName TEXT,
			priority_multiplier REAL DEFAULT 1.0,
			min_lot INTEGER DEFAULT 1,
			active INTEGER DEFAULT 1,
			allow_buy INTEGER DEFAULT 1,
			allow_sell INTEGER DEFAULT 1,
			currency TEXT,
			last_synced TEXT,
			min_portfolio_target REAL,
			max_portfolio_target REAL,
			created_at TEXT,
			updated_at TEXT,
			bucket_id TEXT DEFAULT 'core'
		)
	`)
	require.NoError(t, err)

	return db
}

func TestGetGroupedByExchange_Success(t *testing.T) {
	// Setup
	db := setupTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Insert test data
	_, err := db.Exec(`
		INSERT INTO securities (symbol, name, fullExchangeName, active)
		VALUES
			('AAPL', 'Apple Inc', 'NYSE', 1),
			('MSFT', 'Microsoft', 'NASDAQ', 1),
			('GOOGL', 'Alphabet', 'NASDAQ', 1),
			('BP', 'BP plc', 'LSE', 1),
			('VOD', 'Vodafone', 'LSE', 1)
	`)
	require.NoError(t, err)

	// Execute
	grouped, err := repo.GetGroupedByExchange()

	// Assert
	assert.NoError(t, err)
	assert.Len(t, grouped, 3) // NYSE, NASDAQ, LSE
	assert.Len(t, grouped["NYSE"], 1)
	assert.Len(t, grouped["NASDAQ"], 2)
	assert.Len(t, grouped["LSE"], 2)
	assert.Equal(t, "AAPL", grouped["NYSE"][0].Symbol)
	assert.Contains(t, []string{"MSFT", "GOOGL"}, grouped["NASDAQ"][0].Symbol)
}

func TestGetGroupedByExchange_EmptyDB(t *testing.T) {
	// Setup
	db := setupTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Execute
	grouped, err := repo.GetGroupedByExchange()

	// Assert
	assert.NoError(t, err)
	assert.Empty(t, grouped)
}

func TestGetGroupedByExchange_UnknownExchange(t *testing.T) {
	// Setup
	db := setupTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Insert test data with empty fullExchangeName
	_, err := db.Exec(`
		INSERT INTO securities (symbol, name, fullExchangeName, active)
		VALUES
			('AAPL', 'Apple Inc', 'NYSE', 1),
			('UNKNOWN', 'Unknown Security', '', 1)
	`)
	require.NoError(t, err)

	// Execute
	grouped, err := repo.GetGroupedByExchange()

	// Assert
	assert.NoError(t, err)
	assert.Len(t, grouped, 2) // NYSE and UNKNOWN
	assert.Len(t, grouped["NYSE"], 1)
	assert.Len(t, grouped["UNKNOWN"], 1)
	assert.Equal(t, "UNKNOWN", grouped["UNKNOWN"][0].Symbol)
}

func TestGetGroupedByExchange_OnlyActiveSecurities(t *testing.T) {
	// Setup
	db := setupTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Insert test data with mix of active and inactive
	_, err := db.Exec(`
		INSERT INTO securities (symbol, name, fullExchangeName, active)
		VALUES
			('AAPL', 'Apple Inc', 'NYSE', 1),
			('INACTIVE', 'Inactive Security', 'NYSE', 0),
			('MSFT', 'Microsoft', 'NASDAQ', 1)
	`)
	require.NoError(t, err)

	// Execute
	grouped, err := repo.GetGroupedByExchange()

	// Assert
	assert.NoError(t, err)
	assert.Len(t, grouped, 2) // Only NYSE and NASDAQ (no inactive securities)
	assert.Len(t, grouped["NYSE"], 1)
	assert.Equal(t, "AAPL", grouped["NYSE"][0].Symbol)

	// Ensure INACTIVE is not included
	for _, sec := range grouped["NYSE"] {
		assert.NotEqual(t, "INACTIVE", sec.Symbol)
	}
}

func TestGetGroupedByExchange_MultipleSecuritiesSameExchange(t *testing.T) {
	// Setup
	db := setupTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Insert multiple securities on the same exchange
	_, err := db.Exec(`
		INSERT INTO securities (symbol, name, fullExchangeName, active)
		VALUES
			('AAPL', 'Apple Inc', 'NASDAQ', 1),
			('MSFT', 'Microsoft', 'NASDAQ', 1),
			('GOOGL', 'Alphabet', 'NASDAQ', 1),
			('NVDA', 'NVIDIA', 'NASDAQ', 1),
			('TSLA', 'Tesla', 'NASDAQ', 1)
	`)
	require.NoError(t, err)

	// Execute
	grouped, err := repo.GetGroupedByExchange()

	// Assert
	assert.NoError(t, err)
	assert.Len(t, grouped, 1) // Only NASDAQ
	assert.Len(t, grouped["NASDAQ"], 5)

	// Verify all symbols are present
	symbols := make(map[string]bool)
	for _, sec := range grouped["NASDAQ"] {
		symbols[sec.Symbol] = true
	}
	assert.True(t, symbols["AAPL"])
	assert.True(t, symbols["MSFT"])
	assert.True(t, symbols["GOOGL"])
	assert.True(t, symbols["NVDA"])
	assert.True(t, symbols["TSLA"])
}
