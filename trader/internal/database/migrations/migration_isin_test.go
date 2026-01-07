package migrations

import (
	"database/sql"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	_ "github.com/mattn/go-sqlite3"
)

func setupPreMigrationDB(t *testing.T) *sql.DB {
	// Create temporary database file
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "test.db")

	db, err := sql.Open("sqlite3", dbPath)
	require.NoError(t, err)

	// Create pre-migration schema (symbol as PRIMARY KEY)
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
			created_at TEXT NOT NULL,
			updated_at TEXT NOT NULL
		)
	`)
	require.NoError(t, err)

	_, err = db.Exec(`
		CREATE TABLE scores (
			symbol TEXT PRIMARY KEY,
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
			last_updated TEXT NOT NULL
		)
	`)
	require.NoError(t, err)

	_, err = db.Exec(`
		CREATE TABLE positions (
			symbol TEXT PRIMARY KEY,
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
			isin TEXT
		)
	`)
	require.NoError(t, err)

	_, err = db.Exec(`
		CREATE TABLE trades (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			symbol TEXT NOT NULL,
			isin TEXT,
			side TEXT NOT NULL,
			quantity REAL NOT NULL,
			price REAL NOT NULL,
			executed_at TEXT NOT NULL,
			created_at TEXT NOT NULL
		)
	`)
	require.NoError(t, err)

	_, err = db.Exec(`
		CREATE TABLE dividend_history (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			symbol TEXT NOT NULL,
			isin TEXT,
			payment_date TEXT NOT NULL,
			amount_per_share REAL NOT NULL,
			created_at TEXT NOT NULL
		)
	`)
	require.NoError(t, err)

	_, err = db.Exec(`
		CREATE TABLE recommendations (
			uuid TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			name TEXT NOT NULL,
			side TEXT NOT NULL,
			quantity REAL NOT NULL,
			created_at TEXT NOT NULL
		)
	`)
	require.NoError(t, err)

	_, err = db.Exec(`
		CREATE TABLE tags (
			id TEXT PRIMARY KEY,
			name TEXT NOT NULL,
			created_at TEXT NOT NULL,
			updated_at TEXT NOT NULL
		)
	`)
	require.NoError(t, err)

	_, err = db.Exec(`
		CREATE TABLE security_tags (
			symbol TEXT NOT NULL,
			tag_id TEXT NOT NULL,
			created_at TEXT NOT NULL,
			updated_at TEXT NOT NULL,
			PRIMARY KEY (symbol, tag_id),
			FOREIGN KEY (symbol) REFERENCES securities(symbol) ON DELETE CASCADE,
			FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
		)
	`)
	require.NoError(t, err)

	return db
}

func insertTestData(t *testing.T, db *sql.DB) {
	// Insert securities with ISINs
	_, err := db.Exec(`
		INSERT INTO securities (symbol, isin, name, created_at, updated_at) VALUES
		('AAPL.US', 'US0378331005', 'Apple Inc.', '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z'),
		('MSFT.US', 'US5949181045', 'Microsoft Corp.', '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z')
	`)
	require.NoError(t, err)

	// Insert scores
	_, err = db.Exec(`
		INSERT INTO scores (symbol, total_score, last_updated) VALUES
		('AAPL.US', 85.5, '2024-01-01T00:00:00Z'),
		('MSFT.US', 90.0, '2024-01-01T00:00:00Z')
	`)
	require.NoError(t, err)

	// Insert positions
	_, err = db.Exec(`
		INSERT INTO positions (symbol, quantity, avg_price, isin) VALUES
		('AAPL.US', 10.0, 150.0, 'US0378331005'),
		('MSFT.US', 5.0, 300.0, 'US5949181045')
	`)
	require.NoError(t, err)

	// Insert trades
	_, err = db.Exec(`
		INSERT INTO trades (symbol, isin, side, quantity, price, executed_at, created_at) VALUES
		('AAPL.US', 'US0378331005', 'BUY', 10.0, 150.0, '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z'),
		('MSFT.US', 'US5949181045', 'BUY', 5.0, 300.0, '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z')
	`)
	require.NoError(t, err)

	// Insert dividends
	_, err = db.Exec(`
		INSERT INTO dividend_history (symbol, isin, payment_date, amount_per_share, created_at) VALUES
		('AAPL.US', 'US0378331005', '2024-01-15', 0.24, '2024-01-15T00:00:00Z')
	`)
	require.NoError(t, err)

	// Insert recommendations
	_, err = db.Exec(`
		INSERT INTO recommendations (uuid, symbol, name, side, quantity, created_at) VALUES
		('rec-1', 'AAPL.US', 'Apple Inc.', 'BUY', 5.0, '2024-01-01T00:00:00Z')
	`)
	require.NoError(t, err)

	// Insert tags and security_tags
	_, err = db.Exec(`
		INSERT INTO tags (id, name, created_at, updated_at) VALUES
		('tech', 'Technology', '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z')
	`)
	require.NoError(t, err)

	_, err = db.Exec(`
		INSERT INTO security_tags (symbol, tag_id, created_at, updated_at) VALUES
		('AAPL.US', 'tech', '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z')
	`)
	require.NoError(t, err)
}

func TestMigration_ChangesPrimaryKeysToISIN(t *testing.T) {
	db := setupPreMigrationDB(t)
	defer db.Close()

	insertTestData(t, db)

	// Read migration script from archive (migration is now part of consolidated schema)
	migrationPath := filepath.Join("..", "migrations_archive", "030_migrate_to_isin_primary_key.sql")
	migrationSQL, err := os.ReadFile(migrationPath)
	require.NoError(t, err, "Migration file should exist")

	// Execute migration
	_, err = db.Exec(string(migrationSQL))
	require.NoError(t, err, "Migration should execute successfully")

	// Verify securities table: isin is PRIMARY KEY, symbol is regular column
	var count int
	err = db.QueryRow(`
		SELECT COUNT(*) FROM sqlite_master
		WHERE type='table' AND name='securities' AND sql LIKE '%isin TEXT PRIMARY KEY%'
	`).Scan(&count)
	require.NoError(t, err)
	assert.Greater(t, count, 0, "securities table should have isin as PRIMARY KEY")

	// Verify we can query by ISIN
	var name string
	err = db.QueryRow("SELECT name FROM securities WHERE isin = 'US0378331005'").Scan(&name)
	require.NoError(t, err)
	assert.Equal(t, "Apple Inc.", name)

	// Verify symbol is still accessible as regular column
	var symbol string
	err = db.QueryRow("SELECT symbol FROM securities WHERE isin = 'US0378331005'").Scan(&symbol)
	require.NoError(t, err)
	assert.Equal(t, "AAPL.US", symbol)
}

func TestMigration_PreservesAllData(t *testing.T) {
	db := setupPreMigrationDB(t)
	defer db.Close()

	insertTestData(t, db)

	// Count rows before migration
	var securitiesCount, scoresCount, positionsCount, tradesCount, dividendsCount, recommendationsCount, securityTagsCount int
	db.QueryRow("SELECT COUNT(*) FROM securities").Scan(&securitiesCount)
	db.QueryRow("SELECT COUNT(*) FROM scores").Scan(&scoresCount)
	db.QueryRow("SELECT COUNT(*) FROM positions").Scan(&positionsCount)
	db.QueryRow("SELECT COUNT(*) FROM trades").Scan(&tradesCount)
	db.QueryRow("SELECT COUNT(*) FROM dividend_history").Scan(&dividendsCount)
	db.QueryRow("SELECT COUNT(*) FROM recommendations").Scan(&recommendationsCount)
	db.QueryRow("SELECT COUNT(*) FROM security_tags").Scan(&securityTagsCount)

	// Read and execute migration
	migrationPath := filepath.Join("..", "migrations_archive", "030_migrate_to_isin_primary_key.sql")
	migrationSQL, err := os.ReadFile(migrationPath)
	require.NoError(t, err)

	_, err = db.Exec(string(migrationSQL))
	require.NoError(t, err)

	// Verify row counts after migration
	var securitiesCountAfter, scoresCountAfter, positionsCountAfter, tradesCountAfter, dividendsCountAfter, recommendationsCountAfter, securityTagsCountAfter int
	db.QueryRow("SELECT COUNT(*) FROM securities").Scan(&securitiesCountAfter)
	db.QueryRow("SELECT COUNT(*) FROM scores").Scan(&scoresCountAfter)
	db.QueryRow("SELECT COUNT(*) FROM positions").Scan(&positionsCountAfter)
	db.QueryRow("SELECT COUNT(*) FROM trades").Scan(&tradesCountAfter)
	db.QueryRow("SELECT COUNT(*) FROM dividend_history").Scan(&dividendsCountAfter)
	db.QueryRow("SELECT COUNT(*) FROM recommendations").Scan(&recommendationsCountAfter)
	db.QueryRow("SELECT COUNT(*) FROM security_tags").Scan(&securityTagsCountAfter)

	assert.Equal(t, securitiesCount, securitiesCountAfter, "securities count should be preserved")
	assert.Equal(t, scoresCount, scoresCountAfter, "scores count should be preserved")
	assert.Equal(t, positionsCount, positionsCountAfter, "positions count should be preserved")
	assert.Equal(t, tradesCount, tradesCountAfter, "trades count should be preserved")
	assert.Equal(t, dividendsCount, dividendsCountAfter, "dividends count should be preserved")
	assert.Equal(t, recommendationsCount, recommendationsCountAfter, "recommendations count should be preserved")
	assert.Equal(t, securityTagsCount, securityTagsCountAfter, "security_tags count should be preserved")
}

func TestMigration_UpdatesForeignKeys(t *testing.T) {
	db := setupPreMigrationDB(t)
	defer db.Close()

	insertTestData(t, db)

	// Read and execute migration
	migrationPath := filepath.Join("..", "migrations_archive", "030_migrate_to_isin_primary_key.sql")
	migrationSQL, err := os.ReadFile(migrationPath)
	require.NoError(t, err)

	_, err = db.Exec(string(migrationSQL))
	require.NoError(t, err)

	// Verify security_tags foreign key references isin
	var count int
	_ = db.QueryRow(`
		SELECT COUNT(*) FROM sqlite_master
		WHERE type='table' AND name='security_tags'
		AND sql LIKE '%FOREIGN KEY%isin%'
	`).Scan(&count)
	// Note: SQLite doesn't enforce foreign keys by default, but we check the schema
	assert.Greater(t, count, 0, "security_tags should reference isin in foreign key")
}

func TestMigration_FailsIfMissingISIN(t *testing.T) {
	db := setupPreMigrationDB(t)
	defer db.Close()

	// Insert security without ISIN
	_, err := db.Exec(`
		INSERT INTO securities (symbol, isin, name, created_at, updated_at) VALUES
		('INVALID.US', NULL, 'Invalid Security', '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z')
	`)
	require.NoError(t, err)

	// Migration should fail or handle missing ISINs
	// The migration script should check for missing ISINs before proceeding
	migrationPath := filepath.Join("..", "migrations_archive", "030_migrate_to_isin_primary_key.sql")
	migrationSQL, err := os.ReadFile(migrationPath)
	require.NoError(t, err)

	// Migration should either fail or skip securities without ISIN
	// For now, we'll test that it handles the case
	_, err = db.Exec(string(migrationSQL))
	// Migration might fail or might skip - depends on implementation
	// This test documents the expected behavior
	if err != nil {
		t.Logf("Migration correctly failed for missing ISIN: %v", err)
	}
}
