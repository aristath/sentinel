package satellites

import (
	"database/sql"
	"testing"

	_ "github.com/mattn/go-sqlite3" // SQLite driver for tests
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

// setupBalanceTestDB creates an in-memory SQLite database for balance service testing
func setupBalanceTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite3", ":memory:")
	if err != nil {
		t.Fatalf("Failed to open test database: %v", err)
	}

	// Use existing schema initialization
	err = InitSchema(db)
	if err != nil {
		t.Fatalf("Failed to initialize schema: %v", err)
	}

	// Verify schema was created by checking if key tables exist
	var tableName string
	err = db.QueryRow("SELECT name FROM sqlite_master WHERE type='table' AND name='bucket_transactions'").Scan(&tableName)
	if err != nil {
		t.Fatalf("bucket_transactions table was not created: %v", err)
	}
	err = db.QueryRow("SELECT name FROM sqlite_master WHERE type='table' AND name='buckets'").Scan(&tableName)
	if err != nil {
		t.Fatalf("buckets table was not created: %v", err)
	}

	return db
}

// TestAllocateDeposit_CoreOnly tests deposit when no satellites need funds
func TestAllocateDeposit_CoreOnly(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	// Create core bucket
	_, err := db.Exec(`INSERT INTO buckets (id, name, type, status, created_at, updated_at) VALUES ('core', 'Core', 'CORE', 'ACTIVE', datetime('now'), datetime('now'))`)
	assert.NoError(t, err)

	// Set initial balance in mock cash manager
	_, err = cashManager.AdjustCashBalance("core", "EUR", 1000.0)
	assert.NoError(t, err)

	// Allocate 100 EUR deposit
	allocations, err := service.AllocateDeposit(100.0, "EUR", nil)

	assert.NoError(t, err)
	assert.NotNil(t, allocations)

	// All should go to core (no satellites)
	assert.Equal(t, 1, len(allocations))
	assert.Equal(t, 100.0, allocations["core"])

	// Verify balance updated (check via service which uses cash manager)
	balance, err := service.GetBalanceAmount("core", "EUR")
	assert.NoError(t, err)
	assert.Equal(t, 1100.0, balance)
}

// TestAllocateDeposit_WithSatellites tests deposit allocation to satellites
func TestAllocateDeposit_WithSatellites(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	// Create core bucket
	_, err := db.Exec(`INSERT INTO buckets (id, name, type, status, created_at, updated_at) VALUES ('core', 'Core', 'CORE', 'ACTIVE', datetime('now'), datetime('now'))`)
	assert.NoError(t, err)

	// Create satellites with targets
	target1 := 0.10 // 10%
	target2 := 0.10 // 10%

	_, err = db.Exec(`INSERT INTO buckets (id, name, type, status, target_pct, created_at, updated_at)
		VALUES ('sat1', 'Satellite 1', 'satellite', 'active', ?, datetime('now'), datetime('now')),
		       ('sat2', 'Satellite 2', 'satellite', 'accumulating', ?, datetime('now'), datetime('now'))`,
		target1, target2)
	assert.NoError(t, err)

	// Set initial balances: core=800, sat1=0, sat2=0 (total=800)
	_, err = cashManager.AdjustCashBalance("core", "EUR", 800.0)
	assert.NoError(t, err)

	// Set satellite budget to 20% (20% of 200 = 40 EUR total, split 2 ways = 20 EUR each)
	_, err = db.Exec(`UPDATE allocation_settings SET value = 0.20 WHERE key = 'satellite_budget_pct'`)
	assert.NoError(t, err)

	// Allocate 200 EUR deposit
	// With 20% satellite budget: 40 EUR to satellites (20 EUR each), 160 EUR to core
	allocations, err := service.AllocateDeposit(200.0, "EUR", nil)

	assert.NoError(t, err)

	// Should allocate to satellites
	assert.Contains(t, allocations, "sat1")
	assert.Contains(t, allocations, "sat2")
	assert.Contains(t, allocations, "core")

	// Each satellite should get 20 EUR (40 EUR total / 2 satellites)
	assert.InDelta(t, 20.0, allocations["sat1"], 0.01)
	assert.InDelta(t, 20.0, allocations["sat2"], 0.01)
	assert.InDelta(t, 160.0, allocations["core"], 0.01)

	// Verify balances (check via service which uses cash manager)
	sat1Balance, _ := service.GetBalanceAmount("sat1", "EUR")
	sat2Balance, _ := service.GetBalanceAmount("sat2", "EUR")
	coreBalance, _ := service.GetBalanceAmount("core", "EUR")
	assert.InDelta(t, 20.0, sat1Balance, 0.01)
	assert.InDelta(t, 20.0, sat2Balance, 0.01)
	assert.InDelta(t, 960.0, coreBalance, 0.01) // 800 initial + 160 new
}

// TestAllocateDeposit_CoreNeedsFunds tests when core is below target
func TestAllocateDeposit_CoreNeedsFunds(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	// Create core bucket
	_, err := db.Exec(`INSERT INTO buckets (id, name, type, status, created_at, updated_at) VALUES ('core', 'Core', 'CORE', 'ACTIVE', datetime('now'), datetime('now'))`)
	assert.NoError(t, err)

	// Core has only 500 EUR (needs 800 to reach 80% of 1000)
	_, err = cashManager.AdjustCashBalance("core", "EUR", 500.0)
	assert.NoError(t, err)

	// Allocate 500 EUR (new total = 1000, core needs 300 more to reach 800)
	allocations, err := service.AllocateDeposit(500.0, "EUR", nil)

	assert.NoError(t, err)

	// Core should get at least 300 EUR to reach its target
	assert.GreaterOrEqual(t, allocations["core"], 300.0)
}

// TestAllocateDeposit_ZeroAmount tests error on zero deposit
func TestAllocateDeposit_ZeroAmount(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	allocations, err := service.AllocateDeposit(0.0, "EUR", nil)

	assert.Error(t, err)
	assert.Nil(t, allocations)
	assert.Contains(t, err.Error(), "must be positive")
}

// TestAllocateDeposit_NegativeAmount tests error on negative deposit
func TestAllocateDeposit_NegativeAmount(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	allocations, err := service.AllocateDeposit(-100.0, "EUR", nil)

	assert.Error(t, err)
	assert.Nil(t, allocations)
	assert.Contains(t, err.Error(), "must be positive")
}

// TestRecordTradeSettlement_Buy tests buy trade settlement
func TestRecordTradeSettlement_Buy(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	// Create core bucket (needed for GetPortfolioSummary and other operations)
	_, err := db.Exec(`INSERT INTO buckets (id, name, type, status, created_at, updated_at) VALUES ('core', 'Core', 'CORE', 'ACTIVE', datetime('now'), datetime('now'))`)
	assert.NoError(t, err)

	// Set initial balance in mock cash manager
	_, err = cashManager.AdjustCashBalance("core", "EUR", 1000.0)
	assert.NoError(t, err)

	// Record buy: 100 EUR goes out
	balance, err := service.RecordTradeSettlement("core", 100.0, "EUR", true, nil)

	assert.NoError(t, err)
	assert.NotNil(t, balance)
	assert.Equal(t, 900.0, balance.Balance)

	// Verify transaction recorded
	txs, err := balanceRepo.GetTransactions("core", 10, 0, nil)
	assert.NoError(t, err)
	assert.Equal(t, 1, len(txs))
	assert.Equal(t, TransactionTypeTradeBuy, txs[0].Type)
	assert.Equal(t, 100.0, txs[0].Amount)
}

// TestRecordTradeSettlement_Sell tests sell trade settlement
func TestRecordTradeSettlement_Sell(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	// Set initial balance in mock cash manager
	_, err := cashManager.AdjustCashBalance("core", "EUR", 1000.0)
	assert.NoError(t, err)

	// Record sell: 100 EUR comes in
	balance, err := service.RecordTradeSettlement("core", 100.0, "EUR", false, nil)

	assert.NoError(t, err)
	assert.NotNil(t, balance)
	assert.Equal(t, 1100.0, balance.Balance)

	// Verify transaction recorded
	txs, err := balanceRepo.GetTransactions("core", 10, 0, nil)
	assert.NoError(t, err)
	assert.Equal(t, 1, len(txs))
	assert.Equal(t, TransactionTypeTradeSell, txs[0].Type)
}

// TestRecordTradeSettlement_NegativeAmount tests error on negative amount
func TestRecordTradeSettlement_NegativeAmount(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	balance, err := service.RecordTradeSettlement("core", -100.0, "EUR", true, nil)

	assert.Error(t, err)
	assert.Nil(t, balance)
	assert.Contains(t, err.Error(), "must be positive")
}

// TestRecordDividend tests dividend recording
func TestRecordDividend(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	// Set initial balance in mock cash manager
	_, err := cashManager.AdjustCashBalance("core", "EUR", 1000.0)
	assert.NoError(t, err)

	// Record dividend: 50 EUR
	balance, err := service.RecordDividend("core", 50.0, "EUR", nil)

	assert.NoError(t, err)
	assert.NotNil(t, balance)
	assert.Equal(t, 1050.0, balance.Balance)

	// Verify transaction
	txs, err := balanceRepo.GetTransactions("core", 10, 0, nil)
	assert.NoError(t, err)
	assert.Equal(t, 1, len(txs))
	assert.Equal(t, TransactionTypeDividend, txs[0].Type)
	assert.Equal(t, 50.0, txs[0].Amount)
}

// TestRecordDividend_ZeroAmount tests error on zero dividend
func TestRecordDividend_ZeroAmount(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	balance, err := service.RecordDividend("core", 0.0, "EUR", nil)

	assert.Error(t, err)
	assert.Nil(t, balance)
	assert.Contains(t, err.Error(), "must be positive")
}

// TestTransferBetweenBuckets_Success tests successful transfer
func TestTransferBetweenBuckets_Success(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	// Create core and satellite buckets
	_, err := db.Exec(`INSERT INTO buckets (id, name, type, status, created_at, updated_at)
		VALUES ('core', 'Core', 'core', 'active', datetime('now'), datetime('now')),
		       ('sat1', 'Satellite 1', 'satellite', 'active', datetime('now'), datetime('now'))`)
	assert.NoError(t, err)

	// Set balances in mock cash manager
	_, err = cashManager.AdjustCashBalance("core", "EUR", 1000.0)
	assert.NoError(t, err)
	_, err = cashManager.AdjustCashBalance("sat1", "EUR", 100.0)
	assert.NoError(t, err)

	// Transfer 50 EUR from core to sat1
	fromBal, toBal, err := service.TransferBetweenBuckets("core", "sat1", 50.0, "EUR", nil)

	assert.NoError(t, err)
	assert.NotNil(t, fromBal)
	assert.NotNil(t, toBal)
	assert.Equal(t, 950.0, fromBal.Balance)
	assert.Equal(t, 150.0, toBal.Balance)

	// Verify transactions recorded (both in and out)
	txsCore, _ := balanceRepo.GetTransactions("core", 10, 0, nil)
	txsSat1, _ := balanceRepo.GetTransactions("sat1", 10, 0, nil)
	assert.Equal(t, 1, len(txsCore))
	assert.Equal(t, 1, len(txsSat1))
	assert.Equal(t, TransactionTypeTransferOut, txsCore[0].Type)
	assert.Equal(t, TransactionTypeTransferIn, txsSat1[0].Type)
}

// TestTransferBetweenBuckets_InsufficientFunds tests insufficient funds error
func TestTransferBetweenBuckets_InsufficientFunds(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	// Create core and satellite buckets
	_, err := db.Exec(`INSERT INTO buckets (id, name, type, status, created_at, updated_at)
		VALUES ('core', 'Core', 'core', 'active', datetime('now'), datetime('now')),
		       ('sat1', 'Satellite 1', 'satellite', 'active', datetime('now'), datetime('now'))`)
	assert.NoError(t, err)

	// Core has only 50 EUR in mock cash manager
	_, err = cashManager.AdjustCashBalance("core", "EUR", 50.0)
	assert.NoError(t, err)

	// Try to transfer 100 EUR (more than available)
	fromBal, toBal, err := service.TransferBetweenBuckets("core", "sat1", 100.0, "EUR", nil)

	assert.Error(t, err)
	assert.Nil(t, fromBal)
	assert.Nil(t, toBal)
	assert.Contains(t, err.Error(), "insufficient")
}

// TestTransferBetweenBuckets_SameBucket tests error on same bucket transfer
func TestTransferBetweenBuckets_SameBucket(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	fromBal, toBal, err := service.TransferBetweenBuckets("core", "core", 50.0, "EUR", nil)

	assert.Error(t, err)
	assert.Nil(t, fromBal)
	assert.Nil(t, toBal)
	assert.Contains(t, err.Error(), "cannot transfer to same bucket")
}

// TestTransferBetweenBuckets_NonexistentBucket tests error on missing bucket
func TestTransferBetweenBuckets_NonexistentBucket(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	fromBal, toBal, err := service.TransferBetweenBuckets("core", "nonexistent", 50.0, "EUR", nil)

	assert.Error(t, err)
	assert.Nil(t, fromBal)
	assert.Nil(t, toBal)
	assert.Contains(t, err.Error(), "not found")
}

// TestUpdateSatelliteBudget tests budget update validation
func TestUpdateSatelliteBudget(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	// Valid budget (25%)
	err := service.UpdateSatelliteBudget(0.25)
	assert.NoError(t, err)

	// Verify it was set
	settings, err := service.GetAllocationSettings()
	assert.NoError(t, err)
	assert.Equal(t, 0.25, settings["satellite_budget_pct"])
}

// TestUpdateSatelliteBudget_ExceedsMax tests max budget validation
func TestUpdateSatelliteBudget_ExceedsMax(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	// Try to set 40% (exceeds 30% max)
	err := service.UpdateSatelliteBudget(0.40)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "between 0 and 30%")
}

// TestUpdateSatelliteBudget_Negative tests negative budget validation
func TestUpdateSatelliteBudget_Negative(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	err := service.UpdateSatelliteBudget(-0.10)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "between 0 and 30%")
}

// TestGetPortfolioSummary tests portfolio summary generation
func TestGetPortfolioSummary(t *testing.T) {
	db := setupBalanceTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	cashManager := NewMockCashManager()
	service := NewBalanceService(cashManager, balanceRepo, bucketRepo, log)

	// Create core and satellite buckets
	_, err := db.Exec(`INSERT INTO buckets (id, name, type, status, created_at, updated_at)
		VALUES ('core', 'Core', 'CORE', 'ACTIVE', datetime('now'), datetime('now'))`)
	assert.NoError(t, err)
	_, err = db.Exec(`INSERT INTO buckets (id, name, type, status, created_at, updated_at)
		VALUES ('sat1', 'Satellite 1', 'SATELLITE', 'ACTIVE', datetime('now'), datetime('now'))`)
	assert.NoError(t, err)

	// Set balances in mock cash manager (GetPortfolioSummary reads from cash manager)
	_, err = cashManager.AdjustCashBalance("core", "EUR", 1000.0)
	assert.NoError(t, err)
	_, err = cashManager.AdjustCashBalance("core", "USD", 500.0)
	assert.NoError(t, err)
	_, err = cashManager.AdjustCashBalance("sat1", "EUR", 200.0)
	assert.NoError(t, err)

	summary, err := service.GetPortfolioSummary()

	assert.NoError(t, err)
	assert.NotNil(t, summary)
	assert.Equal(t, 2, len(summary)) // core and sat1

	// Check core balances
	assert.Contains(t, summary, "core")
	assert.Equal(t, 1000.0, summary["core"]["EUR"])
	assert.Equal(t, 500.0, summary["core"]["USD"])

	// Check sat1 balance
	assert.Contains(t, summary, "sat1")
	assert.Equal(t, 200.0, summary["sat1"]["EUR"])
}
