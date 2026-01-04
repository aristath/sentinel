package cash_flows

import (
	"database/sql"
	"fmt"
	"testing"

	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func setupTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)

	err = InitSchema(db)
	require.NoError(t, err)

	return db
}

func TestCreate(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	txType := "DEPOSIT"
	status := "COMPLETED"
	statusC := 1
	desc := "Test deposit"

	cashFlow := &CashFlow{
		TransactionID:   "TX12345",
		TypeDocID:       100,
		TransactionType: &txType,
		Date:            "2024-01-15",
		Amount:          1000.00,
		Currency:        "EUR",
		AmountEUR:       1000.00,
		Status:          &status,
		StatusC:         &statusC,
		Description:     &desc,
	}

	created, err := repo.Create(cashFlow)
	require.NoError(t, err)
	assert.NotZero(t, created.ID)
	assert.NotZero(t, created.CreatedAt)
	assert.Equal(t, "TX12345", created.TransactionID)
	assert.Equal(t, 100, created.TypeDocID)
	assert.Equal(t, "DEPOSIT", *created.TransactionType)
}

func TestCreateDuplicateTransactionID(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	txType := "DEPOSIT"
	cashFlow := &CashFlow{
		TransactionID:   "TX_DUPLICATE",
		TypeDocID:       100,
		TransactionType: &txType,
		Date:            "2024-01-15",
		Amount:          1000.00,
		Currency:        "EUR",
		AmountEUR:       1000.00,
	}

	// First insert should succeed
	_, err := repo.Create(cashFlow)
	require.NoError(t, err)

	// Second insert with same transaction_id should fail
	_, err = repo.Create(cashFlow)
	assert.Error(t, err, "Expected error for duplicate transaction_id")
}

func TestGetByTransactionID(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	// Create cash flow
	txType := "DEPOSIT"
	cashFlow := &CashFlow{
		TransactionID:   "TX99999",
		TypeDocID:       100,
		TransactionType: &txType,
		Date:            "2024-01-15",
		Amount:          500.00,
		Currency:        "EUR",
		AmountEUR:       500.00,
	}
	repo.Create(cashFlow)

	// Retrieve
	retrieved, err := repo.GetByTransactionID("TX99999")
	require.NoError(t, err)
	require.NotNil(t, retrieved)
	assert.Equal(t, "TX99999", retrieved.TransactionID)
	assert.Equal(t, 500.00, retrieved.Amount)
	assert.Equal(t, "DEPOSIT", *retrieved.TransactionType)

	// Non-existent
	nonExistent, err := repo.GetByTransactionID("NONEXISTENT")
	require.NoError(t, err)
	assert.Nil(t, nonExistent)
}

func TestExists(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	txType := "DEPOSIT"
	cashFlow := &CashFlow{
		TransactionID:   "TX11111",
		TypeDocID:       100,
		TransactionType: &txType,
		Date:            "2024-01-15",
		Amount:          100.00,
		Currency:        "EUR",
		AmountEUR:       100.00,
	}
	repo.Create(cashFlow)

	exists, err := repo.Exists("TX11111")
	require.NoError(t, err)
	assert.True(t, exists)

	exists, err = repo.Exists("NONEXISTENT")
	require.NoError(t, err)
	assert.False(t, exists)
}

func TestGetAll(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	// Create multiple cash flows
	for i := 1; i <= 5; i++ {
		txType := "DEPOSIT"
		cashFlow := &CashFlow{
			TransactionID:   fmt.Sprintf("TX%d", i),
			TypeDocID:       100,
			TransactionType: &txType,
			Date:            fmt.Sprintf("2024-01-%02d", i+10),
			Amount:          float64(i * 100),
			Currency:        "EUR",
			AmountEUR:       float64(i * 100),
		}
		repo.Create(cashFlow)
	}

	// Get all (should be ordered by date DESC)
	all, err := repo.GetAll(nil)
	require.NoError(t, err)
	assert.Len(t, all, 5)
	// First should be the latest date
	assert.Equal(t, "2024-01-15", all[0].Date)
	assert.Equal(t, "2024-01-11", all[4].Date)

	// Get with limit
	limit := 3
	limited, err := repo.GetAll(&limit)
	require.NoError(t, err)
	assert.Len(t, limited, 3)
}

func TestGetByDateRange(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	// Create cash flows on different dates
	dates := []string{"2024-01-10", "2024-01-15", "2024-01-20"}
	for i, date := range dates {
		txType := "DEPOSIT"
		cashFlow := &CashFlow{
			TransactionID:   fmt.Sprintf("TX_DATE_%d", i),
			TypeDocID:       100,
			TransactionType: &txType,
			Date:            date,
			Amount:          100.00,
			Currency:        "EUR",
			AmountEUR:       100.00,
		}
		repo.Create(cashFlow)
	}

	// Query range (should get only middle date)
	results, err := repo.GetByDateRange("2024-01-12", "2024-01-18")
	require.NoError(t, err)
	assert.Len(t, results, 1)
	assert.Equal(t, "2024-01-15", results[0].Date)

	// Query entire range
	results, err = repo.GetByDateRange("2024-01-01", "2024-01-31")
	require.NoError(t, err)
	assert.Len(t, results, 3)
	// Should be ordered ASC by date
	assert.Equal(t, "2024-01-10", results[0].Date)
	assert.Equal(t, "2024-01-20", results[2].Date)
}

func TestGetByType(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	// Create cash flows of different types
	types := []string{"DEPOSIT", "WITHDRAWAL", "DEPOSIT", "DIVIDEND"}
	for i, txType := range types {
		txTypeCopy := txType
		cashFlow := &CashFlow{
			TransactionID:   fmt.Sprintf("TX_TYPE_%d", i),
			TypeDocID:       100 + i,
			TransactionType: &txTypeCopy,
			Date:            "2024-01-15",
			Amount:          100.00,
			Currency:        "EUR",
			AmountEUR:       100.00,
		}
		repo.Create(cashFlow)
	}

	// Query by type
	deposits, err := repo.GetByType("DEPOSIT")
	require.NoError(t, err)
	assert.Len(t, deposits, 2)

	withdrawals, err := repo.GetByType("WITHDRAWAL")
	require.NoError(t, err)
	assert.Len(t, withdrawals, 1)

	dividends, err := repo.GetByType("DIVIDEND")
	require.NoError(t, err)
	assert.Len(t, dividends, 1)
}

func TestSyncFromAPI(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	// Create API transactions
	transactions := []APITransaction{
		{
			TransactionID:   "API_TX_1",
			TypeDocID:       100,
			TransactionType: "DEPOSIT",
			Date:            "2024-01-15",
			Amount:          1000.00,
			Currency:        "EUR",
			AmountEUR:       1000.00,
			Status:          "COMPLETED",
			StatusC:         1,
			Description:     "API deposit",
			Params:          map[string]interface{}{"source": "api"},
		},
		{
			TransactionID:   "API_TX_2",
			TypeDocID:       101,
			TransactionType: "WITHDRAWAL",
			Date:            "2024-01-16",
			Amount:          500.00,
			Currency:        "EUR",
			AmountEUR:       500.00,
			Status:          "COMPLETED",
			StatusC:         1,
			Description:     "API withdrawal",
			Params:          map[string]interface{}{},
		},
	}

	// First sync
	count, err := repo.SyncFromAPI(transactions)
	require.NoError(t, err)
	assert.Equal(t, 2, count)

	// Second sync (duplicates) - should return 0
	count, err = repo.SyncFromAPI(transactions)
	require.NoError(t, err)
	assert.Equal(t, 0, count, "Expected 0 synced on duplicate transactions")

	// Verify records exist
	all, _ := repo.GetAll(nil)
	assert.Len(t, all, 2)

	// Verify params were serialized
	retrieved, _ := repo.GetByTransactionID("API_TX_1")
	assert.NotNil(t, retrieved.ParamsJSON)
	assert.Contains(t, *retrieved.ParamsJSON, "source")
}

func TestGetTotalDeposits(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	// Create deposits and other types
	deposit := "DEPOSIT"
	refill := "REFILL"
	withdrawal := "WITHDRAWAL"

	cashFlows := []*CashFlow{
		{TransactionID: "TX1", TypeDocID: 100, TransactionType: &deposit, Date: "2024-01-10", Amount: 1000, Currency: "EUR", AmountEUR: 1000},
		{TransactionID: "TX2", TypeDocID: 100, TransactionType: &deposit, Date: "2024-01-15", Amount: 500, Currency: "EUR", AmountEUR: 500},
		{TransactionID: "TX3", TypeDocID: 100, TransactionType: &refill, Date: "2024-01-20", Amount: 300, Currency: "EUR", AmountEUR: 300},
		{TransactionID: "TX4", TypeDocID: 101, TransactionType: &withdrawal, Date: "2024-01-25", Amount: 200, Currency: "EUR", AmountEUR: 200},
	}

	for _, cf := range cashFlows {
		repo.Create(cf)
	}

	// Get total deposits (should include DEPOSIT and REFILL)
	total, err := repo.GetTotalDeposits()
	require.NoError(t, err)
	assert.Equal(t, 1800.0, total)
}

func TestGetTotalWithdrawals(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	deposit := "DEPOSIT"
	withdrawal := "WITHDRAWAL"

	cashFlows := []*CashFlow{
		{TransactionID: "TX1", TypeDocID: 100, TransactionType: &deposit, Date: "2024-01-10", Amount: 1000, Currency: "EUR", AmountEUR: 1000},
		{TransactionID: "TX2", TypeDocID: 101, TransactionType: &withdrawal, Date: "2024-01-15", Amount: 200, Currency: "EUR", AmountEUR: 200},
		{TransactionID: "TX3", TypeDocID: 101, TransactionType: &withdrawal, Date: "2024-01-20", Amount: 150, Currency: "EUR", AmountEUR: 150},
	}

	for _, cf := range cashFlows {
		repo.Create(cf)
	}

	// Get total withdrawals
	total, err := repo.GetTotalWithdrawals()
	require.NoError(t, err)
	assert.Equal(t, 350.0, total)
}

func TestGetCashBalanceHistory(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	// Create deposits, withdrawals, and dividends
	deposit := "DEPOSIT"
	withdrawal := "WITHDRAWAL"
	dividend := "DIVIDEND"

	cashFlows := []*CashFlow{
		{TransactionID: "TX1", TypeDocID: 100, TransactionType: &deposit, Date: "2024-01-10", Amount: 1000, Currency: "EUR", AmountEUR: 1000},
		{TransactionID: "TX2", TypeDocID: 100, TransactionType: &deposit, Date: "2024-01-15", Amount: 500, Currency: "EUR", AmountEUR: 500},
		{TransactionID: "TX3", TypeDocID: 101, TransactionType: &withdrawal, Date: "2024-01-20", Amount: 200, Currency: "EUR", AmountEUR: 200},
		{TransactionID: "TX4", TypeDocID: 102, TransactionType: &dividend, Date: "2024-01-25", Amount: 50, Currency: "EUR", AmountEUR: 50},
	}

	for _, cf := range cashFlows {
		repo.Create(cf)
	}

	// Get balance history starting from 0
	points, err := repo.GetCashBalanceHistory("2024-01-01", "2024-01-31", 0.0)
	require.NoError(t, err)

	// Should have 4 points (one per date)
	assert.Len(t, points, 4)

	// Verify running balance
	assert.Equal(t, "2024-01-10", points[0].Date)
	assert.Equal(t, 1000.0, points[0].Balance)

	assert.Equal(t, "2024-01-15", points[1].Date)
	assert.Equal(t, 1500.0, points[1].Balance)

	assert.Equal(t, "2024-01-20", points[2].Date)
	assert.Equal(t, 1300.0, points[2].Balance) // 1500 - 200

	assert.Equal(t, "2024-01-25", points[3].Date)
	assert.Equal(t, 1350.0, points[3].Balance) // 1300 + 50

	// Test with initial balance
	points, err = repo.GetCashBalanceHistory("2024-01-01", "2024-01-31", 500.0)
	require.NoError(t, err)
	assert.Equal(t, 1500.0, points[0].Balance) // 500 + 1000
	assert.Equal(t, 1850.0, points[3].Balance) // 500 + 1000 + 500 - 200 + 50
}

func TestGetCashBalanceHistoryMultipleTransactionsSameDay(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	deposit := "DEPOSIT"

	// Create multiple transactions on same day
	cashFlows := []*CashFlow{
		{TransactionID: "TX1", TypeDocID: 100, TransactionType: &deposit, Date: "2024-01-15", Amount: 100, Currency: "EUR", AmountEUR: 100},
		{TransactionID: "TX2", TypeDocID: 100, TransactionType: &deposit, Date: "2024-01-15", Amount: 200, Currency: "EUR", AmountEUR: 200},
		{TransactionID: "TX3", TypeDocID: 100, TransactionType: &deposit, Date: "2024-01-15", Amount: 300, Currency: "EUR", AmountEUR: 300},
	}

	for _, cf := range cashFlows {
		repo.Create(cf)
	}

	points, err := repo.GetCashBalanceHistory("2024-01-01", "2024-01-31", 0.0)
	require.NoError(t, err)

	// Should have 1 point (all on same day, aggregated)
	assert.Len(t, points, 1)
	assert.Equal(t, "2024-01-15", points[0].Date)
	assert.Equal(t, 600.0, points[0].Balance) // Sum of all three
}

func TestEmptyRepository(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	// Test GetAll on empty repo
	all, err := repo.GetAll(nil)
	require.NoError(t, err)
	assert.Len(t, all, 0)

	// Test totals on empty repo
	deposits, err := repo.GetTotalDeposits()
	require.NoError(t, err)
	assert.Equal(t, 0.0, deposits)

	withdrawals, err := repo.GetTotalWithdrawals()
	require.NoError(t, err)
	assert.Equal(t, 0.0, withdrawals)

	// Test balance history on empty repo
	points, err := repo.GetCashBalanceHistory("2024-01-01", "2024-01-31", 100.0)
	require.NoError(t, err)
	assert.Len(t, points, 0)
}
