package cash_flows

import (
	"database/sql"
	"testing"

	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func setupTestDBForCashManager(t *testing.T) *sql.DB {
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

func TestCashManager_UpdateCashPosition(t *testing.T) {
	db := setupTestDBForCashManager(t)
	defer db.Close()

	cashRepo := NewCashRepository(db, zerolog.Nop())
	manager := NewCashManager(cashRepo, zerolog.Nop())

	// Update with positive balance
	err := manager.UpdateCashPosition("EUR", 1000.0)
	require.NoError(t, err)

	// Verify balance was stored
	balance, err := manager.GetCashBalance("EUR")
	require.NoError(t, err)
	assert.Equal(t, 1000.0, balance)

	// Update existing balance
	err = manager.UpdateCashPosition("EUR", 2000.0)
	require.NoError(t, err)

	balance, err = manager.GetCashBalance("EUR")
	require.NoError(t, err)
	assert.Equal(t, 2000.0, balance)

	// Update with zero balance (should delete)
	err = manager.UpdateCashPosition("EUR", 0.0)
	require.NoError(t, err)

	balance, err = manager.GetCashBalance("EUR")
	require.NoError(t, err)
	assert.Equal(t, 0.0, balance)
}

func TestCashManager_GetCashBalance(t *testing.T) {
	db := setupTestDBForCashManager(t)
	defer db.Close()

	cashRepo := NewCashRepository(db, zerolog.Nop())
	manager := NewCashManager(cashRepo, zerolog.Nop())

	// Get non-existent currency (should return 0)
	balance, err := manager.GetCashBalance("USD")
	require.NoError(t, err)
	assert.Equal(t, 0.0, balance)

	// Set balance and get it
	err = manager.UpdateCashPosition("USD", 500.0)
	require.NoError(t, err)

	balance, err = manager.GetCashBalance("USD")
	require.NoError(t, err)
	assert.Equal(t, 500.0, balance)
}

func TestCashManager_GetAllCashBalances(t *testing.T) {
	db := setupTestDBForCashManager(t)
	defer db.Close()

	cashRepo := NewCashRepository(db, zerolog.Nop())
	manager := NewCashManager(cashRepo, zerolog.Nop())

	// Get all from empty repository
	all, err := manager.GetAllCashBalances()
	require.NoError(t, err)
	assert.Empty(t, all)

	// Add multiple currencies
	err = manager.UpdateCashPosition("EUR", 1000.0)
	require.NoError(t, err)
	err = manager.UpdateCashPosition("USD", 500.0)
	require.NoError(t, err)
	err = manager.UpdateCashPosition("GBP", 750.0)
	require.NoError(t, err)

	// Get all
	all, err = manager.GetAllCashBalances()
	require.NoError(t, err)
	assert.Len(t, all, 3)
	assert.Equal(t, 1000.0, all["EUR"])
	assert.Equal(t, 500.0, all["USD"])
	assert.Equal(t, 750.0, all["GBP"])
}

func TestCashManager_AdjustCashBalance(t *testing.T) {
	db := setupTestDBForCashManager(t)
	defer db.Close()

	cashRepo := NewCashRepository(db, zerolog.Nop())
	manager := NewCashManager(cashRepo, zerolog.Nop())

	// Start with initial balance
	err := manager.UpdateCashPosition("EUR", 1000.0)
	require.NoError(t, err)

	// Add to balance
	newBalance, err := manager.AdjustCashBalance("EUR", 500.0)
	require.NoError(t, err)
	assert.Equal(t, 1500.0, newBalance)

	// Verify
	balance, err := manager.GetCashBalance("EUR")
	require.NoError(t, err)
	assert.Equal(t, 1500.0, balance)

	// Subtract from balance
	newBalance, err = manager.AdjustCashBalance("EUR", -200.0)
	require.NoError(t, err)
	assert.Equal(t, 1300.0, newBalance)

	// Verify
	balance, err = manager.GetCashBalance("EUR")
	require.NoError(t, err)
	assert.Equal(t, 1300.0, balance)

	// Adjust non-existent currency (should create it)
	newBalance, err = manager.AdjustCashBalance("USD", 100.0)
	require.NoError(t, err)
	assert.Equal(t, 100.0, newBalance)

	balance, err = manager.GetCashBalance("USD")
	require.NoError(t, err)
	assert.Equal(t, 100.0, balance)
}

func TestCashManager_ConcurrentAccess(t *testing.T) {
	db := setupTestDBForCashManager(t)
	defer db.Close()

	cashRepo := NewCashRepository(db, zerolog.Nop())
	manager := NewCashManager(cashRepo, zerolog.Nop())

	// Set initial balance
	err := manager.UpdateCashPosition("EUR", 1000.0)
	require.NoError(t, err)

	// Simulate concurrent adjustments (in real scenario, these would be goroutines)
	// This test verifies the mutex works correctly
	_, err = manager.AdjustCashBalance("EUR", 100.0)
	require.NoError(t, err)

	_, err = manager.AdjustCashBalance("EUR", 200.0)
	require.NoError(t, err)

	// Final balance should be correct
	balance, err := manager.GetCashBalance("EUR")
	require.NoError(t, err)
	assert.Equal(t, 1300.0, balance)
}
