package satellites

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestBalanceRepository_SetBalance(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	balance, err := repo.SetBalance("core", "USD", 5000.0)
	require.NoError(t, err)
	assert.Equal(t, "core", balance.BucketID)
	assert.Equal(t, "USD", balance.Currency)
	assert.Equal(t, 5000.0, balance.Balance)
	assert.NotEmpty(t, balance.LastUpdated)
}

func TestBalanceRepository_GetBalance(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	// Set balance
	repo.SetBalance("core", "EUR", 10000.0)

	// Get balance
	balance, err := repo.GetBalance("core", "EUR")
	require.NoError(t, err)
	require.NotNil(t, balance)
	assert.Equal(t, 10000.0, balance.Balance)
}

func TestBalanceRepository_GetBalance_NotFound(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	balance, err := repo.GetBalance("nonexistent", "USD")
	require.NoError(t, err)
	assert.Nil(t, balance)
}

func TestBalanceRepository_GetBalanceAmount(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	// Set balance
	repo.SetBalance("sat1", "USD", 1234.56)

	// Get amount
	amount, err := repo.GetBalanceAmount("sat1", "USD")
	require.NoError(t, err)
	assert.Equal(t, 1234.56, amount)

	// Get non-existent balance (should return 0)
	amount, err = repo.GetBalanceAmount("sat1", "GBP")
	require.NoError(t, err)
	assert.Equal(t, 0.0, amount)
}

func TestBalanceRepository_AdjustBalance(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	// Adjust from zero (creates record)
	balance, err := repo.AdjustBalance("core", "USD", 1000.0)
	require.NoError(t, err)
	assert.Equal(t, 1000.0, balance.Balance)

	// Adjust again (adds to existing)
	balance, err = repo.AdjustBalance("core", "USD", 500.0)
	require.NoError(t, err)
	assert.Equal(t, 1500.0, balance.Balance)

	// Adjust with negative (subtract)
	balance, err = repo.AdjustBalance("core", "USD", -200.0)
	require.NoError(t, err)
	assert.Equal(t, 1300.0, balance.Balance)
}

func TestBalanceRepository_GetAllBalances(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	// Set multiple currency balances for same bucket
	repo.SetBalance("core", "USD", 5000.0)
	repo.SetBalance("core", "EUR", 3000.0)
	repo.SetBalance("core", "GBP", 2000.0)

	// Get all balances for bucket
	balances, err := repo.GetAllBalances("core")
	require.NoError(t, err)
	assert.Len(t, balances, 3)

	// Verify all currencies present
	currencies := make(map[string]float64)
	for _, b := range balances {
		currencies[b.Currency] = b.Balance
	}
	assert.Equal(t, 5000.0, currencies["USD"])
	assert.Equal(t, 3000.0, currencies["EUR"])
	assert.Equal(t, 2000.0, currencies["GBP"])
}

func TestBalanceRepository_GetAllBalancesByCurrency(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	// Set balances for multiple buckets in USD
	repo.SetBalance("core", "USD", 10000.0)
	repo.SetBalance("sat1", "USD", 2000.0)
	repo.SetBalance("sat2", "USD", 1500.0)

	// Get all USD balances
	balances, err := repo.GetAllBalancesByCurrency("USD")
	require.NoError(t, err)
	assert.Len(t, balances, 3)
}

func TestBalanceRepository_GetTotalByCurrency(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	// Set balances
	repo.SetBalance("core", "EUR", 5000.0)
	repo.SetBalance("sat1", "EUR", 1000.0)
	repo.SetBalance("sat2", "EUR", 500.0)

	// Get total
	total, err := repo.GetTotalByCurrency("EUR")
	require.NoError(t, err)
	assert.Equal(t, 6500.0, total)

	// Get total for non-existent currency
	total, err = repo.GetTotalByCurrency("JPY")
	require.NoError(t, err)
	assert.Equal(t, 0.0, total)
}

func TestBalanceRepository_DeleteBalances(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	// Set multiple balances
	repo.SetBalance("sat1", "USD", 1000.0)
	repo.SetBalance("sat1", "EUR", 2000.0)

	// Delete all balances for bucket
	count, err := repo.DeleteBalances("sat1")
	require.NoError(t, err)
	assert.Equal(t, 2, count)

	// Verify deleted
	balances, err := repo.GetAllBalances("sat1")
	require.NoError(t, err)
	assert.Len(t, balances, 0)
}

func TestBalanceRepository_RecordTransaction(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	desc := "Monthly deposit"
	tx := NewBucketTransaction("core", TransactionTypeDeposit, 1000.0, "USD", &desc)

	err := repo.RecordTransaction(tx, nil)
	require.NoError(t, err)
	assert.NotNil(t, tx.ID)
	assert.NotEmpty(t, tx.CreatedAt)
}

func TestBalanceRepository_GetTransactions(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	// Record transactions
	tx1 := NewBucketTransaction("core", TransactionTypeDeposit, 1000.0, "USD", nil)
	repo.RecordTransaction(tx1, nil)

	tx2 := NewBucketTransaction("core", TransactionTypeTradeBuy, -500.0, "USD", nil)
	repo.RecordTransaction(tx2, nil)

	tx3 := NewBucketTransaction("core", TransactionTypeDividend, 50.0, "USD", nil)
	repo.RecordTransaction(tx3, nil)

	// Get all transactions
	transactions, err := repo.GetTransactions("core", 100, 0, nil)
	require.NoError(t, err)
	assert.Len(t, transactions, 3)

	// Get with type filter
	depositType := TransactionTypeDeposit
	transactions, err = repo.GetTransactions("core", 100, 0, &depositType)
	require.NoError(t, err)
	assert.Len(t, transactions, 1)
	assert.Equal(t, TransactionTypeDeposit, transactions[0].Type)
}

func TestBalanceRepository_GetTransactions_Pagination(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	// Create 5 transactions
	for i := 0; i < 5; i++ {
		tx := NewBucketTransaction("core", TransactionTypeDeposit, 100.0, "USD", nil)
		repo.RecordTransaction(tx, nil)
	}

	// Get first 2
	transactions, err := repo.GetTransactions("core", 2, 0, nil)
	require.NoError(t, err)
	assert.Len(t, transactions, 2)

	// Get next 2
	transactions, err = repo.GetTransactions("core", 2, 2, nil)
	require.NoError(t, err)
	assert.Len(t, transactions, 2)

	// Get last 1
	transactions, err = repo.GetTransactions("core", 2, 4, nil)
	require.NoError(t, err)
	assert.Len(t, transactions, 1)
}

func TestBalanceRepository_GetTransactionsByType(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	// Record different types
	repo.RecordTransaction(NewBucketTransaction("core", TransactionTypeDeposit, 1000.0, "USD", nil), nil)
	repo.RecordTransaction(NewBucketTransaction("sat1", TransactionTypeDeposit, 500.0, "USD", nil), nil)
	repo.RecordTransaction(NewBucketTransaction("core", TransactionTypeTradeBuy, -200.0, "USD", nil), nil)

	// Get all deposits across all buckets
	transactions, err := repo.GetTransactionsByType(TransactionTypeDeposit, 100)
	require.NoError(t, err)
	assert.Len(t, transactions, 2)
	for _, tx := range transactions {
		assert.Equal(t, TransactionTypeDeposit, tx.Type)
	}
}

func TestBalanceRepository_DeleteTransactions(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	// Record transactions
	repo.RecordTransaction(NewBucketTransaction("sat1", TransactionTypeDeposit, 1000.0, "USD", nil), nil)
	repo.RecordTransaction(NewBucketTransaction("sat1", TransactionTypeTradeBuy, -500.0, "USD", nil), nil)

	// Delete all transactions for bucket
	count, err := repo.DeleteTransactions("sat1")
	require.NoError(t, err)
	assert.Equal(t, 2, count)

	// Verify deleted
	transactions, err := repo.GetTransactions("sat1", 100, 0, nil)
	require.NoError(t, err)
	assert.Len(t, transactions, 0)
}

func TestBalanceRepository_AllocationSettings(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	// Get default setting (from schema initialization)
	value, err := repo.GetAllocationSetting("satellite_budget_pct")
	require.NoError(t, err)
	require.NotNil(t, value)
	assert.Equal(t, 0.00, *value)

	// Update setting
	err = repo.SetAllocationSetting("satellite_budget_pct", 0.15, nil)
	require.NoError(t, err)

	// Verify updated
	value, err = repo.GetAllocationSetting("satellite_budget_pct")
	require.NoError(t, err)
	assert.Equal(t, 0.15, *value)

	// Set new setting with description
	desc := "Test setting"
	err = repo.SetAllocationSetting("test_key", 0.5, &desc)
	require.NoError(t, err)

	value, err = repo.GetAllocationSetting("test_key")
	require.NoError(t, err)
	assert.Equal(t, 0.5, *value)
}

func TestBalanceRepository_GetAllAllocationSettings(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	// Get all settings (should include defaults from schema)
	settings, err := repo.GetAllAllocationSettings()
	require.NoError(t, err)
	assert.NotEmpty(t, settings)

	// Verify default settings are present
	assert.Contains(t, settings, "satellite_budget_pct")
	assert.Contains(t, settings, "satellite_min_pct")
	assert.Contains(t, settings, "satellite_max_pct")
}

func TestBalanceRepository_CurrencyCaseInsensitive(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBalanceRepository(db, zerolog.Nop())

	// Set balance with lowercase currency
	_, err := repo.SetBalance("core", "usd", 1000.0)
	require.NoError(t, err)

	// Get with uppercase (should find it)
	balance, err := repo.GetBalance("core", "USD")
	require.NoError(t, err)
	require.NotNil(t, balance)
	assert.Equal(t, "USD", balance.Currency) // Stored as uppercase
	assert.Equal(t, 1000.0, balance.Balance)

	// Get with mixed case
	balance, err = repo.GetBalance("core", "UsD")
	require.NoError(t, err)
	require.NotNil(t, balance)
}
