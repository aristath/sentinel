package satellites

import (
	"database/sql"
	"math"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

// setupReconciliationTestDB creates an in-memory SQLite database for reconciliation testing
func setupReconciliationTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite3", ":memory:")
	if err != nil {
		t.Fatalf("Failed to open test database: %v", err)
	}

	err = InitSchema(db)
	if err != nil {
		t.Fatalf("Failed to initialize schema: %v", err)
	}

	return db
}

// ============================================================================
// CheckInvariant Tests
// ============================================================================

func TestCheckInvariant_Matched(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Set virtual balance to 1000 EUR
	_, err := balanceRepo.AdjustBalance("core", "EUR", 1000.0)
	assert.NoError(t, err)

	// Check against matching actual balance
	result, err := service.CheckInvariant("EUR", 1000.0)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, "EUR", result.Currency)
	assert.Equal(t, 1000.0, result.VirtualTotal)
	assert.Equal(t, 1000.0, result.ActualTotal)
	assert.Equal(t, 0.0, result.Difference)
	assert.True(t, result.IsReconciled)
}

func TestCheckInvariant_VirtualGreaterThanActual(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Virtual = 1000 EUR
	_, err := balanceRepo.AdjustBalance("core", "EUR", 1000.0)
	assert.NoError(t, err)

	// Actual = 950 EUR (virtual is higher)
	result, err := service.CheckInvariant("EUR", 950.0)

	assert.NoError(t, err)
	assert.Equal(t, 1000.0, result.VirtualTotal)
	assert.Equal(t, 950.0, result.ActualTotal)
	assert.Equal(t, 50.0, result.Difference) // Virtual - actual = 50
	assert.False(t, result.IsReconciled)
}

func TestCheckInvariant_VirtualLessThanActual(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Virtual = 1000 EUR
	_, err := balanceRepo.AdjustBalance("core", "EUR", 1000.0)
	assert.NoError(t, err)

	// Actual = 1050 EUR (virtual is lower)
	result, err := service.CheckInvariant("EUR", 1050.0)

	assert.NoError(t, err)
	assert.Equal(t, 1000.0, result.VirtualTotal)
	assert.Equal(t, 1050.0, result.ActualTotal)
	assert.Equal(t, -50.0, result.Difference) // Virtual - actual = -50
	assert.False(t, result.IsReconciled)
}

func TestCheckInvariant_ZeroBalance(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// No balances set - should be 0
	result, err := service.CheckInvariant("EUR", 0.0)

	assert.NoError(t, err)
	assert.Equal(t, 0.0, result.VirtualTotal)
	assert.Equal(t, 0.0, result.ActualTotal)
	assert.Equal(t, 0.0, result.Difference)
	assert.True(t, result.IsReconciled)
}

// ============================================================================
// Reconcile Tests - Auto-correction Logic
// ============================================================================

func TestReconcile_AlreadyReconciled(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Set virtual = 1000 EUR
	_, err := balanceRepo.AdjustBalance("core", "EUR", 1000.0)
	assert.NoError(t, err)

	// Reconcile with matching actual
	result, err := service.Reconcile("EUR", 1000.0, nil)

	assert.NoError(t, err)
	assert.True(t, result.IsReconciled)
	assert.Empty(t, result.AdjustmentsMade)

	// Verify no changes
	balance, err := balanceRepo.GetBalanceAmount("core", "EUR")
	assert.NoError(t, err)
	assert.Equal(t, 1000.0, balance)
}

func TestReconcile_SmallDifference_AutoCorrect(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Virtual = 1002 EUR (2 EUR higher than actual)
	_, err := balanceRepo.AdjustBalance("core", "EUR", 1002.0)
	assert.NoError(t, err)

	// Actual = 1000 EUR (difference = 2, within default threshold of 5)
	result, err := service.Reconcile("EUR", 1000.0, nil)

	assert.NoError(t, err)
	assert.True(t, result.IsReconciled)
	assert.Equal(t, 1002.0, result.VirtualTotal)
	assert.Equal(t, 1000.0, result.ActualTotal)
	assert.Equal(t, 2.0, result.Difference)

	// Should have adjusted core by -2
	assert.Contains(t, result.AdjustmentsMade, "core")
	assert.Equal(t, -2.0, result.AdjustmentsMade["core"])

	// Verify core balance was corrected
	balance, err := balanceRepo.GetBalanceAmount("core", "EUR")
	assert.NoError(t, err)
	assert.Equal(t, 1000.0, balance)

	// Verify transaction recorded
	txs, err := balanceRepo.GetRecentTransactions("core", 1)
	assert.NoError(t, err)
	assert.Len(t, txs, 1)
	assert.Equal(t, TransactionTypeReallocation, txs[0].Type)
	assert.Equal(t, -2.0, txs[0].Amount)
}

func TestReconcile_SmallNegativeDifference_AutoCorrect(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Virtual = 998 EUR (2 EUR lower than actual)
	_, err := balanceRepo.AdjustBalance("core", "EUR", 998.0)
	assert.NoError(t, err)

	// Actual = 1000 EUR (difference = -2)
	result, err := service.Reconcile("EUR", 1000.0, nil)

	assert.NoError(t, err)
	assert.True(t, result.IsReconciled)
	assert.Equal(t, -2.0, result.Difference)

	// Should have adjusted core by +2
	assert.Equal(t, 2.0, result.AdjustmentsMade["core"])

	// Verify core balance was corrected
	balance, err := balanceRepo.GetBalanceAmount("core", "EUR")
	assert.NoError(t, err)
	assert.Equal(t, 1000.0, balance)
}

func TestReconcile_LargeDifference_NoAutoCorrect(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Virtual = 1100 EUR (100 EUR higher, exceeds default threshold of 5)
	_, err := balanceRepo.AdjustBalance("core", "EUR", 1100.0)
	assert.NoError(t, err)

	// Actual = 1000 EUR (difference = 100)
	result, err := service.Reconcile("EUR", 1000.0, nil)

	assert.NoError(t, err)
	assert.False(t, result.IsReconciled)
	assert.Equal(t, 100.0, result.Difference)

	// Should NOT have made adjustments
	assert.Empty(t, result.AdjustmentsMade)

	// Verify core balance unchanged
	balance, err := balanceRepo.GetBalanceAmount("core", "EUR")
	assert.NoError(t, err)
	assert.Equal(t, 1100.0, balance)
}

func TestReconcile_CustomThreshold(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Virtual = 1010 EUR (10 EUR higher)
	_, err := balanceRepo.AdjustBalance("core", "EUR", 1010.0)
	assert.NoError(t, err)

	// Actual = 1000 EUR
	customThreshold := 20.0 // 20 EUR threshold

	result, err := service.Reconcile("EUR", 1000.0, &customThreshold)

	assert.NoError(t, err)
	assert.True(t, result.IsReconciled)

	// Should have adjusted because 10 < 20
	assert.Equal(t, -10.0, result.AdjustmentsMade["core"])

	// Verify core balance corrected
	balance, err := balanceRepo.GetBalanceAmount("core", "EUR")
	assert.NoError(t, err)
	assert.Equal(t, 1000.0, balance)
}

func TestReconcile_ExactlyAtThreshold(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Virtual = 1005 EUR (exactly 5 EUR higher, at threshold)
	_, err := balanceRepo.AdjustBalance("core", "EUR", 1005.0)
	assert.NoError(t, err)

	// Actual = 1000 EUR (difference = 5, exactly at default threshold)
	result, err := service.Reconcile("EUR", 1000.0, nil)

	assert.NoError(t, err)
	assert.True(t, result.IsReconciled)

	// Should auto-correct (threshold is inclusive: <= 5)
	assert.Equal(t, -5.0, result.AdjustmentsMade["core"])

	balance, err := balanceRepo.GetBalanceAmount("core", "EUR")
	assert.NoError(t, err)
	assert.Equal(t, 1000.0, balance)
}

// ============================================================================
// ReconcileAll Tests
// ============================================================================

func TestReconcileAll_MultipleCurrencies(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Set virtual balances: EUR=1002, USD=502
	_, err := balanceRepo.AdjustBalance("core", "EUR", 1002.0)
	assert.NoError(t, err)
	_, err = balanceRepo.AdjustBalance("core", "USD", 502.0)
	assert.NoError(t, err)

	actualBalances := map[string]float64{
		"EUR": 1000.0, // 2 EUR difference (auto-correctable)
		"USD": 500.0,  // 2 USD difference (auto-correctable)
	}

	results, err := service.ReconcileAll(actualBalances, nil)

	assert.NoError(t, err)
	assert.Len(t, results, 2)

	// Both should be reconciled
	for _, result := range results {
		assert.True(t, result.IsReconciled)
		assert.Contains(t, result.AdjustmentsMade, "core")
	}

	// Verify balances corrected
	eurBalance, _ := balanceRepo.GetBalanceAmount("core", "EUR")
	assert.Equal(t, 1000.0, eurBalance)

	usdBalance, _ := balanceRepo.GetBalanceAmount("core", "USD")
	assert.Equal(t, 500.0, usdBalance)
}

func TestReconcileAll_MixedResults(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// EUR: small difference (auto-correctable)
	// USD: large difference (requires manual intervention)
	_, err := balanceRepo.AdjustBalance("core", "EUR", 1002.0)
	assert.NoError(t, err)
	_, err = balanceRepo.AdjustBalance("core", "USD", 600.0)
	assert.NoError(t, err)

	actualBalances := map[string]float64{
		"EUR": 1000.0, // 2 EUR difference
		"USD": 500.0,  // 100 USD difference (exceeds threshold)
	}

	results, err := service.ReconcileAll(actualBalances, nil)

	assert.NoError(t, err)
	assert.Len(t, results, 2)

	// Find each result
	var eurResult, usdResult *ReconciliationResult
	for _, r := range results {
		if r.Currency == "EUR" {
			eurResult = r
		} else {
			usdResult = r
		}
	}

	// EUR should be auto-corrected
	assert.True(t, eurResult.IsReconciled)
	assert.NotEmpty(t, eurResult.AdjustmentsMade)

	// USD should NOT be auto-corrected
	assert.False(t, usdResult.IsReconciled)
	assert.Empty(t, usdResult.AdjustmentsMade)
}

// ============================================================================
// GetBalanceBreakdown Tests
// ============================================================================

func TestGetBalanceBreakdown_MultipleBuckets(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Create core bucket
	_, err := db.Exec(`INSERT INTO buckets (id, name, type, status, created_at, updated_at) VALUES ('core', 'Core', 'CORE', 'ACTIVE', datetime('now'), datetime('now'))`)
	assert.NoError(t, err)

	// Create satellites
	_, err = db.Exec(`INSERT INTO buckets (id, name, type, status, created_at, updated_at) VALUES ('sat1', 'Satellite 1', 'SATELLITE', 'ACTIVE', datetime('now'), datetime('now'))`)
	assert.NoError(t, err)

	// Set balances
	_, err = balanceRepo.AdjustBalance("core", "EUR", 800.0)
	assert.NoError(t, err)
	_, err = balanceRepo.AdjustBalance("sat1", "EUR", 200.0)
	assert.NoError(t, err)

	breakdown, err := service.GetBalanceBreakdown("EUR")

	assert.NoError(t, err)
	assert.Len(t, breakdown, 2)
	assert.Equal(t, 800.0, breakdown["core"])
	assert.Equal(t, 200.0, breakdown["sat1"])
}

func TestGetBalanceBreakdown_ExcludesZeroBalances(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Create core bucket
	_, err := db.Exec(`INSERT INTO buckets (id, name, type, status, created_at, updated_at) VALUES ('core', 'Core', 'CORE', 'ACTIVE', datetime('now'), datetime('now'))`)
	assert.NoError(t, err)

	// Create satellites
	_, err = db.Exec(`INSERT INTO buckets (id, name, type, status, created_at, updated_at) VALUES ('sat1', 'Satellite 1', 'SATELLITE', 'ACTIVE', datetime('now'), datetime('now'))`)
	assert.NoError(t, err)

	// Only set core balance, sat1 will be 0
	_, err = balanceRepo.AdjustBalance("core", "EUR", 1000.0)
	assert.NoError(t, err)

	breakdown, err := service.GetBalanceBreakdown("EUR")

	assert.NoError(t, err)
	// Should only include core (non-zero)
	assert.Len(t, breakdown, 1)
	assert.Equal(t, 1000.0, breakdown["core"])
	assert.NotContains(t, breakdown, "sat1")
}

func TestGetBalanceBreakdown_Empty(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// No balances set
	breakdown, err := service.GetBalanceBreakdown("EUR")

	assert.NoError(t, err)
	assert.Empty(t, breakdown)
}

// ============================================================================
// InitializeFromBrokerage Tests
// ============================================================================

func TestInitializeFromBrokerage_FirstTime(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	actualBalances := map[string]float64{
		"EUR": 5000.0,
		"USD": 3000.0,
	}

	results, err := service.InitializeFromBrokerage(actualBalances)

	assert.NoError(t, err)
	assert.Len(t, results, 2)

	// All should be reconciled
	for _, result := range results {
		assert.True(t, result.IsReconciled)
	}

	// Verify core balances initialized
	eurBalance, err := balanceRepo.GetBalanceAmount("core", "EUR")
	assert.NoError(t, err)
	assert.Equal(t, 5000.0, eurBalance)

	usdBalance, err := balanceRepo.GetBalanceAmount("core", "USD")
	assert.NoError(t, err)
	assert.Equal(t, 3000.0, usdBalance)

	// Verify transactions recorded
	eurTxs, err := balanceRepo.GetRecentTransactions("core", 10)
	assert.NoError(t, err)
	assert.GreaterOrEqual(t, len(eurTxs), 2) // At least one for each currency
}

func TestInitializeFromBrokerage_AlreadyInitialized(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Already have balances
	_, err := balanceRepo.AdjustBalance("core", "EUR", 1000.0)
	assert.NoError(t, err)

	actualBalances := map[string]float64{
		"EUR": 1000.0,
	}

	results, err := service.InitializeFromBrokerage(actualBalances)

	assert.NoError(t, err)
	assert.Len(t, results, 1)
	assert.True(t, results[0].IsReconciled)

	// Should not double-initialize
	balance, err := balanceRepo.GetBalanceAmount("core", "EUR")
	assert.NoError(t, err)
	assert.Equal(t, 1000.0, balance) // Not 2000
}

func TestInitializeFromBrokerage_ZeroBalance(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	actualBalances := map[string]float64{
		"EUR": 0.0,
	}

	results, err := service.InitializeFromBrokerage(actualBalances)

	assert.NoError(t, err)
	assert.Len(t, results, 1)

	// Should not create balance for zero
	balance, err := balanceRepo.GetBalanceAmount("core", "EUR")
	assert.NoError(t, err)
	assert.Equal(t, 0.0, balance)
}

// ============================================================================
// ForceReconcileToCore Tests
// ============================================================================

func TestForceReconcileToCore_AdjustUp(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Current state: core=800, total should be 1000
	_, err := balanceRepo.AdjustBalance("core", "EUR", 800.0)
	assert.NoError(t, err)

	// Force reconcile to 1000 actual
	result, err := service.ForceReconcileToCore("EUR", 1000.0)

	assert.NoError(t, err)
	assert.True(t, result.IsReconciled)
	assert.Equal(t, 1000.0, result.VirtualTotal)
	assert.Equal(t, 1000.0, result.ActualTotal)
	assert.Equal(t, 0.0, result.Difference)

	// Core should be adjusted from 800 to 1000
	assert.Equal(t, 200.0, result.AdjustmentsMade["core"])

	balance, err := balanceRepo.GetBalanceAmount("core", "EUR")
	assert.NoError(t, err)
	assert.Equal(t, 1000.0, balance)
}

func TestForceReconcileToCore_AdjustDown(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Current state: core=1200
	_, err := balanceRepo.AdjustBalance("core", "EUR", 1200.0)
	assert.NoError(t, err)

	// Force reconcile to 1000 actual
	result, err := service.ForceReconcileToCore("EUR", 1000.0)

	assert.NoError(t, err)
	assert.True(t, result.IsReconciled)

	// Core should be adjusted from 1200 to 1000
	assert.Equal(t, -200.0, result.AdjustmentsMade["core"])

	balance, err := balanceRepo.GetBalanceAmount("core", "EUR")
	assert.NoError(t, err)
	assert.Equal(t, 1000.0, balance)
}

func TestForceReconcileToCore_WithSatellites(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Create satellite
	_, err := db.Exec(`INSERT INTO buckets (id, name, type, status, created_at, updated_at) VALUES ('sat1', 'Satellite 1', 'SATELLITE', 'ACTIVE', datetime('now'), datetime('now'))`)
	assert.NoError(t, err)

	// Current state: core=500, sat1=300, total=800
	// Actual brokerage: 1000
	// Core should be: 1000 - 300 = 700
	_, err = balanceRepo.AdjustBalance("core", "EUR", 500.0)
	assert.NoError(t, err)
	_, err = balanceRepo.AdjustBalance("sat1", "EUR", 300.0)
	assert.NoError(t, err)

	result, err := service.ForceReconcileToCore("EUR", 1000.0)

	assert.NoError(t, err)
	assert.True(t, result.IsReconciled)

	// Core should be adjusted from 500 to 700
	assert.Equal(t, 200.0, result.AdjustmentsMade["core"])

	coreBalance, err := balanceRepo.GetBalanceAmount("core", "EUR")
	assert.NoError(t, err)
	assert.Equal(t, 700.0, coreBalance)

	// Satellite should be unchanged
	sat1Balance, err := balanceRepo.GetBalanceAmount("sat1", "EUR")
	assert.NoError(t, err)
	assert.Equal(t, 300.0, sat1Balance)

	// Total should match actual
	total, err := balanceRepo.GetTotalByCurrency("EUR")
	assert.NoError(t, err)
	assert.Equal(t, 1000.0, total)
}

func TestForceReconcileToCore_NoAdjustmentNeeded(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Already correct: core=1000, actual=1000
	_, err := balanceRepo.AdjustBalance("core", "EUR", 1000.0)
	assert.NoError(t, err)

	result, err := service.ForceReconcileToCore("EUR", 1000.0)

	assert.NoError(t, err)
	assert.True(t, result.IsReconciled)

	// No adjustments needed
	assert.Empty(t, result.AdjustmentsMade)

	balance, err := balanceRepo.GetBalanceAmount("core", "EUR")
	assert.NoError(t, err)
	assert.Equal(t, 1000.0, balance)
}

// ============================================================================
// DiagnoseDiscrepancy Tests
// ============================================================================

func TestDiagnoseDiscrepancy_WithDiscrepancy(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Create core bucket
	_, err := db.Exec(`INSERT INTO buckets (id, name, type, status, created_at, updated_at) VALUES ('core', 'Core', 'CORE', 'ACTIVE', datetime('now'), datetime('now'))`)
	assert.NoError(t, err)

	// Create discrepancy
	_, err = balanceRepo.AdjustBalance("core", "EUR", 1100.0)
	assert.NoError(t, err)

	diagnosis, err := service.DiagnoseDiscrepancy("EUR", 1000.0)

	assert.NoError(t, err)
	assert.NotNil(t, diagnosis)
	assert.Equal(t, "EUR", diagnosis["currency"])
	assert.Equal(t, 1000.0, diagnosis["actual_balance"])
	assert.Equal(t, 1100.0, diagnosis["virtual_total"])
	assert.Equal(t, 100.0, diagnosis["difference"])

	breakdown := diagnosis["breakdown"].(map[string]float64)
	assert.Equal(t, 1100.0, breakdown["core"])
}

func TestDiagnoseDiscrepancy_WithRecentTransactions(t *testing.T) {
	db := setupReconciliationTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	balanceRepo := NewBalanceRepository(db, log)
	bucketRepo := NewBucketRepository(db, log)
	service := NewReconciliationService(balanceRepo, bucketRepo, log)

	// Create core bucket
	_, err := db.Exec(`INSERT INTO buckets (id, name, type, status, created_at, updated_at) VALUES ('core', 'Core', 'CORE', 'ACTIVE', datetime('now'), datetime('now'))`)
	assert.NoError(t, err)

	// Create some transactions
	_, err = balanceRepo.AdjustBalance("core", "EUR", 1000.0)
	assert.NoError(t, err)

	desc := "Test deposit"
	tx := &BucketTransaction{
		BucketID:    "core",
		Type:        TransactionTypeDeposit,
		Amount:      100.0,
		Currency:    "EUR",
		Description: &desc,
	}
	err = balanceRepo.RecordTransaction(tx, nil)
	assert.NoError(t, err)

	diagnosis, err := service.DiagnoseDiscrepancy("EUR", 1000.0)

	assert.NoError(t, err)
	transactions := diagnosis["recent_transactions"].([]map[string]interface{})
	assert.GreaterOrEqual(t, len(transactions), 1)
}

// ============================================================================
// DifferencePct Tests
// ============================================================================

func TestDifferencePct_Normal(t *testing.T) {
	result := &ReconciliationResult{
		VirtualTotal: 1100.0,
		ActualTotal:  1000.0,
		Difference:   100.0,
	}

	pct := result.DifferencePct()

	// |100| / 1000 = 0.10 (10%)
	assert.Equal(t, 0.10, pct)
}

func TestDifferencePct_ZeroActual_ZeroVirtual(t *testing.T) {
	result := &ReconciliationResult{
		VirtualTotal: 0.0,
		ActualTotal:  0.0,
		Difference:   0.0,
	}

	pct := result.DifferencePct()

	assert.Equal(t, 0.0, pct)
}

func TestDifferencePct_ZeroActual_NonZeroVirtual(t *testing.T) {
	result := &ReconciliationResult{
		VirtualTotal: 100.0,
		ActualTotal:  0.0,
		Difference:   100.0,
	}

	pct := result.DifferencePct()

	// Should return infinity
	assert.True(t, math.IsInf(pct, 1))
}

func TestDifferencePct_NegativeDifference(t *testing.T) {
	result := &ReconciliationResult{
		VirtualTotal: 900.0,
		ActualTotal:  1000.0,
		Difference:   -100.0,
	}

	pct := result.DifferencePct()

	// |-100| / 1000 = 0.10 (uses absolute value)
	assert.Equal(t, 0.10, pct)
}
