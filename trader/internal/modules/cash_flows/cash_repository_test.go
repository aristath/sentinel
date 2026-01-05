package cash_flows

import (
	"database/sql"
	"testing"
	"time"

	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func setupTestDBForCashBalances(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)

	// Create cash_balances table
	_, err = db.Exec(`
		CREATE TABLE cash_balances (
			currency TEXT PRIMARY KEY,
			balance REAL NOT NULL,
			last_updated TEXT NOT NULL
		) STRICT
	`)
	require.NoError(t, err)

	return db
}

func TestCashRepository_Get(t *testing.T) {
	db := setupTestDBForCashBalances(t)
	defer db.Close()

	repo := NewCashRepository(db, zerolog.Nop())

	// Test getting non-existent currency (should return 0, no error)
	balance, err := repo.Get("EUR")
	require.NoError(t, err)
	assert.Equal(t, 0.0, balance)

	// Insert a balance
	_, err = db.Exec(`
		INSERT INTO cash_balances (currency, balance, last_updated)
		VALUES ('EUR', 1000.50, ?)
	`, time.Now().Format(time.RFC3339))
	require.NoError(t, err)

	// Get existing balance
	balance, err = repo.Get("EUR")
	require.NoError(t, err)
	assert.Equal(t, 1000.50, balance)

	// Get different currency (should return 0)
	balance, err = repo.Get("USD")
	require.NoError(t, err)
	assert.Equal(t, 0.0, balance)
}

func TestCashRepository_GetAll(t *testing.T) {
	db := setupTestDBForCashBalances(t)
	defer db.Close()

	repo := NewCashRepository(db, zerolog.Nop())

	// Test empty repository
	all, err := repo.GetAll()
	require.NoError(t, err)
	assert.Empty(t, all)

	// Insert multiple currencies
	now := time.Now().Format(time.RFC3339)
	_, err = db.Exec(`
		INSERT INTO cash_balances (currency, balance, last_updated) VALUES
		('EUR', 1000.0, ?),
		('USD', 500.0, ?),
		('GBP', 750.0, ?)
	`, now, now, now)
	require.NoError(t, err)

	// Get all balances
	all, err = repo.GetAll()
	require.NoError(t, err)
	assert.Len(t, all, 3)
	assert.Equal(t, 1000.0, all["EUR"])
	assert.Equal(t, 500.0, all["USD"])
	assert.Equal(t, 750.0, all["GBP"])
}

func TestCashRepository_Upsert(t *testing.T) {
	db := setupTestDBForCashBalances(t)
	defer db.Close()

	repo := NewCashRepository(db, zerolog.Nop())

	// Insert new balance
	err := repo.Upsert("EUR", 1000.0)
	require.NoError(t, err)

	// Verify it was inserted
	var balance float64
	var lastUpdated string
	err = db.QueryRow("SELECT balance, last_updated FROM cash_balances WHERE currency = 'EUR'").Scan(&balance, &lastUpdated)
	require.NoError(t, err)
	assert.Equal(t, 1000.0, balance)
	assert.NotEmpty(t, lastUpdated)

	// Update existing balance
	err = repo.Upsert("EUR", 2000.0)
	require.NoError(t, err)

	// Verify it was updated
	err = db.QueryRow("SELECT balance FROM cash_balances WHERE currency = 'EUR'").Scan(&balance)
	require.NoError(t, err)
	assert.Equal(t, 2000.0, balance)

	// Insert zero balance (should be allowed)
	err = repo.Upsert("USD", 0.0)
	require.NoError(t, err)

	balance, err = repo.Get("USD")
	require.NoError(t, err)
	assert.Equal(t, 0.0, balance)
}

func TestCashRepository_Delete(t *testing.T) {
	db := setupTestDBForCashBalances(t)
	defer db.Close()

	repo := NewCashRepository(db, zerolog.Nop())

	// Insert a balance
	err := repo.Upsert("EUR", 1000.0)
	require.NoError(t, err)

	// Verify it exists
	balance, err := repo.Get("EUR")
	require.NoError(t, err)
	assert.Equal(t, 1000.0, balance)

	// Delete it
	err = repo.Delete("EUR")
	require.NoError(t, err)

	// Verify it's gone (should return 0)
	balance, err = repo.Get("EUR")
	require.NoError(t, err)
	assert.Equal(t, 0.0, balance)

	// Delete non-existent currency (should not error)
	err = repo.Delete("USD")
	require.NoError(t, err)
}

func TestCashRepository_MultipleCurrencies(t *testing.T) {
	db := setupTestDBForCashBalances(t)
	defer db.Close()

	repo := NewCashRepository(db, zerolog.Nop())

	// Insert multiple currencies
	err := repo.Upsert("EUR", 1000.0)
	require.NoError(t, err)
	err = repo.Upsert("USD", 500.0)
	require.NoError(t, err)
	err = repo.Upsert("GBP", 750.0)
	require.NoError(t, err)

	// Get all
	all, err := repo.GetAll()
	require.NoError(t, err)
	assert.Len(t, all, 3)

	// Update one
	err = repo.Upsert("USD", 600.0)
	require.NoError(t, err)

	// Verify update
	balance, err := repo.Get("USD")
	require.NoError(t, err)
	assert.Equal(t, 600.0, balance)

	// Others should be unchanged
	balance, err = repo.Get("EUR")
	require.NoError(t, err)
	assert.Equal(t, 1000.0, balance)

	// Delete one
	err = repo.Delete("GBP")
	require.NoError(t, err)

	// Verify deletion
	all, err = repo.GetAll()
	require.NoError(t, err)
	assert.Len(t, all, 2)
	assert.NotContains(t, all, "GBP")
}

func TestCashRepository_EdgeCases(t *testing.T) {
	db := setupTestDBForCashBalances(t)
	defer db.Close()

	repo := NewCashRepository(db, zerolog.Nop())

	// Test negative balance (should be allowed - might happen during trades)
	err := repo.Upsert("EUR", -100.0)
	require.NoError(t, err)

	balance, err := repo.Get("EUR")
	require.NoError(t, err)
	assert.Equal(t, -100.0, balance)

	// Test very large balance
	err = repo.Upsert("USD", 999999999.99)
	require.NoError(t, err)

	balance, err = repo.Get("USD")
	require.NoError(t, err)
	assert.Equal(t, 999999999.99, balance)

	// Test empty currency string (edge case)
	err = repo.Upsert("", 100.0)
	require.NoError(t, err) // SQLite allows empty string as key

	balance, err = repo.Get("")
	require.NoError(t, err)
	assert.Equal(t, 100.0, balance)
}
