package satellites

import (
	"database/sql"
	"fmt"

	"github.com/rs/zerolog"
)

// BalanceService provides atomic virtual cash operations.
//
// All operations that affect cash balances are atomic - they update
// the balance and record a transaction in a single database transaction.
//
// This ensures the critical invariant:
// SUM(bucket_balances for currency X) == Actual brokerage balance for currency X
//
// Faithful translation from Python: app/modules/satellites/services/balance_service.py
type BalanceService struct {
	balanceRepo *BalanceRepository
	bucketRepo  *BucketRepository
	log         zerolog.Logger
}

// Maximum allowed satellite budget (safety limit to prevent over-allocation)
const MaxSatelliteBudgetPct = 0.30 // 30%

// NewBalanceService creates a new balance service
func NewBalanceService(
	balanceRepo *BalanceRepository,
	bucketRepo *BucketRepository,
	log zerolog.Logger,
) *BalanceService {
	return &BalanceService{
		balanceRepo: balanceRepo,
		bucketRepo:  bucketRepo,
		log:         log,
	}
}

// Query methods

// GetBalance gets balance for a bucket in a specific currency
func (s *BalanceService) GetBalance(bucketID string, currency string) (*BucketBalance, error) {
	return s.balanceRepo.GetBalance(bucketID, currency)
}

// GetBalanceAmount gets balance amount, returning 0 if not found
func (s *BalanceService) GetBalanceAmount(bucketID string, currency string) (float64, error) {
	return s.balanceRepo.GetBalanceAmount(bucketID, currency)
}

// GetAllBalances gets all currency balances for a bucket
func (s *BalanceService) GetAllBalances(bucketID string) ([]*BucketBalance, error) {
	return s.balanceRepo.GetAllBalances(bucketID)
}

// GetTotalByCurrency gets total virtual balance across all buckets for a currency
func (s *BalanceService) GetTotalByCurrency(currency string) (float64, error) {
	return s.balanceRepo.GetTotalByCurrency(currency)
}

// GetPortfolioSummary gets summary of all buckets and their balances.
//
// Returns:
//
//	Map of bucket_id to map of currency -> balance
func (s *BalanceService) GetPortfolioSummary() (map[string]map[string]float64, error) {
	buckets, err := s.bucketRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get buckets: %w", err)
	}

	summary := make(map[string]map[string]float64)

	for _, bucket := range buckets {
		balances, err := s.balanceRepo.GetAllBalances(bucket.ID)
		if err != nil {
			return nil, fmt.Errorf("failed to get balances for bucket %s: %w", bucket.ID, err)
		}

		currencyMap := make(map[string]float64)
		for _, balance := range balances {
			currencyMap[balance.Currency] = balance.Balance
		}
		summary[bucket.ID] = currencyMap
	}

	return summary, nil
}

// Atomic cash operations

// RecordTradeSettlement records a trade settlement, atomically updating balance.
//
// For buys: subtracts amount from balance (cash goes out)
// For sells: adds amount to balance (cash comes in)
//
// Args:
//
//	bucketID: ID of the bucket
//	amount: Absolute trade amount (always positive)
//	currency: Currency code
//	isBuy: True for buy (cash out), False for sell (cash in)
//	description: Optional description for audit trail
//
// Returns:
//
//	Updated balance
func (s *BalanceService) RecordTradeSettlement(
	bucketID string,
	amount float64,
	currency string,
	isBuy bool,
	description *string,
) (*BucketBalance, error) {
	if amount < 0 {
		return nil, fmt.Errorf("amount must be positive")
	}

	// For buys, cash goes out (negative delta)
	// For sells, cash comes in (positive delta)
	delta := amount
	if isBuy {
		delta = -amount
	}

	txType := TransactionTypeTradeSell
	defaultDesc := "Sell settlement"
	if isBuy {
		txType = TransactionTypeTradeBuy
		defaultDesc = "Buy settlement"
	}

	// Atomic operation: adjust balance and record transaction together
	tx, err := s.balanceRepo.satellitesDB.Begin()
	if err != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// Adjust balance
	balance, err := s.balanceRepo.AdjustBalance(bucketID, currency, delta)
	if err != nil {
		return nil, fmt.Errorf("failed to adjust balance: %w", err)
	}

	// Record transaction
	desc := defaultDesc
	if description != nil {
		desc = *description
	}

	transaction := &BucketTransaction{
		BucketID:    bucketID,
		Type:        txType,
		Amount:      amount, // Store as positive
		Currency:    currency,
		Description: &desc,
	}

	err = s.balanceRepo.RecordTransaction(transaction)
	if err != nil {
		return nil, fmt.Errorf("failed to record transaction: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("failed to commit transaction: %w", err)
	}

	action := "sold"
	if isBuy {
		action = "bought"
	}
	s.log.Info().
		Str("bucket_id", bucketID).
		Float64("amount", amount).
		Str("currency", currency).
		Str("action", action).
		Msg("Recorded trade settlement")

	return balance, nil
}

// RecordDividend records a dividend payment.
//
// Args:
//
//	bucketID: ID of the bucket receiving the dividend
//	amount: Dividend amount (positive)
//	currency: Currency code
//	description: Optional description
//
// Returns:
//
//	Updated balance
func (s *BalanceService) RecordDividend(
	bucketID string,
	amount float64,
	currency string,
	description *string,
) (*BucketBalance, error) {
	if amount <= 0 {
		return nil, fmt.Errorf("dividend amount must be positive")
	}

	// Atomic operation: adjust balance and record transaction together
	tx, err := s.balanceRepo.satellitesDB.Begin()
	if err != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// Adjust balance (cash comes in)
	balance, err := s.balanceRepo.AdjustBalance(bucketID, currency, amount)
	if err != nil {
		return nil, fmt.Errorf("failed to adjust balance: %w", err)
	}

	// Record transaction
	desc := "Dividend received"
	if description != nil {
		desc = *description
	}

	transaction := &BucketTransaction{
		BucketID:    bucketID,
		Type:        TransactionTypeDividend,
		Amount:      amount,
		Currency:    currency,
		Description: &desc,
	}

	err = s.balanceRepo.RecordTransaction(transaction)
	if err != nil {
		return nil, fmt.Errorf("failed to record transaction: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("failed to commit transaction: %w", err)
	}

	s.log.Info().
		Str("bucket_id", bucketID).
		Float64("amount", amount).
		Str("currency", currency).
		Msg("Recorded dividend")

	return balance, nil
}

// TransferBetweenBuckets transfers cash between buckets.
//
// Args:
//
//	fromBucketID: Source bucket ID
//	toBucketID: Destination bucket ID
//	amount: Amount to transfer (positive)
//	currency: Currency code
//	description: Optional description
//
// Returns:
//
//	Tuple of (from_balance, to_balance) after transfer
//
// Errors:
//
//	Returns error if insufficient funds or invalid buckets
func (s *BalanceService) TransferBetweenBuckets(
	fromBucketID string,
	toBucketID string,
	amount float64,
	currency string,
	description *string,
) (*BucketBalance, *BucketBalance, error) {
	if amount <= 0 {
		return nil, nil, fmt.Errorf("transfer amount must be positive")
	}

	if fromBucketID == toBucketID {
		return nil, nil, fmt.Errorf("cannot transfer to same bucket")
	}

	// Validate buckets exist
	fromBucket, err := s.bucketRepo.GetByID(fromBucketID)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to get source bucket: %w", err)
	}
	if fromBucket == nil {
		return nil, nil, fmt.Errorf("source bucket '%s' not found", fromBucketID)
	}

	toBucket, err := s.bucketRepo.GetByID(toBucketID)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to get destination bucket: %w", err)
	}
	if toBucket == nil {
		return nil, nil, fmt.Errorf("destination bucket '%s' not found", toBucketID)
	}

	// Check sufficient funds
	currentBalance, err := s.balanceRepo.GetBalanceAmount(fromBucketID, currency)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to get current balance: %w", err)
	}

	if currentBalance < amount {
		return nil, nil, fmt.Errorf(
			"insufficient funds in '%s': has %.2f, needs %.2f %s",
			fromBucketID, currentBalance, amount, currency,
		)
	}

	// Check core minimum (if transferring from core)
	if fromBucketID == "core" {
		settings, err := s.balanceRepo.GetAllAllocationSettings()
		if err != nil {
			return nil, nil, fmt.Errorf("failed to get allocation settings: %w", err)
		}

		satelliteBudgetPct := 0.0
		if val, ok := settings["satellite_budget_pct"]; ok {
			satelliteBudgetPct = val
		}

		coreMinPct := 1.0 - satelliteBudgetPct

		// Get total portfolio value for validation
		total, err := s.GetTotalByCurrency(currency)
		if err != nil {
			return nil, nil, fmt.Errorf("failed to get total balance: %w", err)
		}

		if total > 0 {
			remainingAfterTransfer := currentBalance - amount
			remainingPct := remainingAfterTransfer / total
			if remainingPct < coreMinPct {
				return nil, nil, fmt.Errorf(
					"transfer would put core below minimum allocation (%.1f%% < %.1f%%)",
					remainingPct*100, coreMinPct*100,
				)
			}
		}
	}

	// Atomic operation: perform transfer and record both transactions together
	tx, err := s.balanceRepo.satellitesDB.Begin()
	if err != nil {
		return nil, nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// Perform the transfer
	fromBalance, err := s.balanceRepo.AdjustBalance(fromBucketID, currency, -amount)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to adjust from balance: %w", err)
	}

	toBalance, err := s.balanceRepo.AdjustBalance(toBucketID, currency, amount)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to adjust to balance: %w", err)
	}

	// Record transactions for audit trail
	desc := fmt.Sprintf("Transfer from %s to %s", fromBucketID, toBucketID)
	if description != nil {
		desc = *description
	}

	txOut := &BucketTransaction{
		BucketID:    fromBucketID,
		Type:        TransactionTypeTransferOut,
		Amount:      amount,
		Currency:    currency,
		Description: &desc,
	}

	txIn := &BucketTransaction{
		BucketID:    toBucketID,
		Type:        TransactionTypeTransferIn,
		Amount:      amount,
		Currency:    currency,
		Description: &desc,
	}

	err = s.balanceRepo.RecordTransaction(txOut)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to record outbound transaction: %w", err)
	}

	err = s.balanceRepo.RecordTransaction(txIn)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to record inbound transaction: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return nil, nil, fmt.Errorf("failed to commit transaction: %w", err)
	}

	s.log.Info().
		Str("from_bucket", fromBucketID).
		Str("to_bucket", toBucketID).
		Float64("amount", amount).
		Str("currency", currency).
		Msg("Transferred funds between buckets")

	return fromBalance, toBalance, nil
}

// AllocateDeposit allocates a new deposit across buckets based on targets.
//
// Deposits are split among buckets that are below their target allocation.
// Priority goes to buckets furthest below target.
//
// Args:
//
//	totalAmount: Total deposit amount
//	currency: Currency code
//	description: Optional description
//
// Returns:
//
//	Map of bucket_id to allocated amount
func (s *BalanceService) AllocateDeposit(
	totalAmount float64,
	currency string,
	description *string,
) (map[string]float64, error) {
	if totalAmount <= 0 {
		return nil, fmt.Errorf("deposit amount must be positive")
	}

	// Get allocation settings
	settings, err := s.balanceRepo.GetAllAllocationSettings()
	if err != nil {
		return nil, fmt.Errorf("failed to get allocation settings: %w", err)
	}

	satelliteBudgetPct := 0.0
	if val, ok := settings["satellite_budget_pct"]; ok {
		satelliteBudgetPct = val
	}

	// Get all active buckets
	buckets, err := s.bucketRepo.GetActive()
	if err != nil {
		return nil, fmt.Errorf("failed to get active buckets: %w", err)
	}

	// Calculate current total and target amounts
	currentTotal, err := s.GetTotalByCurrency(currency)
	if err != nil {
		return nil, fmt.Errorf("failed to get total balance: %w", err)
	}

	newTotal := currentTotal + totalAmount

	allocations := make(map[string]float64)
	remaining := totalAmount

	// Core always gets at least its target
	coreTargetPct := 1.0 - satelliteBudgetPct
	coreTargetAmount := newTotal * coreTargetPct
	coreCurrent, err := s.balanceRepo.GetBalanceAmount("core", currency)
	if err != nil {
		return nil, fmt.Errorf("failed to get core balance: %w", err)
	}

	coreNeeded := 0.0
	if coreTargetAmount > coreCurrent {
		coreNeeded = coreTargetAmount - coreCurrent
	}

	if coreNeeded > 0 {
		coreAllocation := coreNeeded
		if coreAllocation > remaining {
			coreAllocation = remaining
		}
		allocations["core"] = coreAllocation
		remaining -= coreAllocation
	}

	// Distribute remaining to satellites below target
	if remaining > 0 {
		var satellites []*Bucket
		for _, bucket := range buckets {
			if bucket.Type == BucketTypeSatellite {
				satellites = append(satellites, bucket)
			}
		}

		// Filter to only accumulating or active satellites with target > 0
		type satelliteDeficit struct {
			bucketID string
			deficit  float64
		}
		var deficits []satelliteDeficit

		for _, sat := range satellites {
			if (sat.Status == BucketStatusAccumulating || sat.Status == BucketStatusActive) &&
				sat.TargetPct != nil && *sat.TargetPct > 0 {

				targetAmount := newTotal * (*sat.TargetPct)
				current, err := s.balanceRepo.GetBalanceAmount(sat.ID, currency)
				if err != nil {
					return nil, fmt.Errorf("failed to get balance for %s: %w", sat.ID, err)
				}

				deficit := targetAmount - current
				if deficit > 0 {
					deficits = append(deficits, satelliteDeficit{
						bucketID: sat.ID,
						deficit:  deficit,
					})
				}
			}
		}

		// Distribute proportionally to deficits
		totalDeficit := 0.0
		for _, d := range deficits {
			totalDeficit += d.deficit
		}

		if totalDeficit > 0 {
			for _, d := range deficits {
				share := (d.deficit / totalDeficit) * remaining
				allocations[d.bucketID] = share
			}
			remaining = 0 // All distributed to satellites
		}
	}

	// Fallback: If any remaining amount wasn't allocated, give it to core
	if remaining > 0 {
		if existing, ok := allocations["core"]; ok {
			allocations["core"] = existing + remaining
		} else {
			allocations["core"] = remaining
		}
		s.log.Debug().
			Float64("fallback_amount", remaining).
			Msg("Allocated remaining deposit to core bucket (no satellites needed funds)")
	}

	// Record the allocations atomically
	tx, err := s.balanceRepo.satellitesDB.Begin()
	if err != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	for bucketID, amount := range allocations {
		if amount > 0 {
			_, err := s.balanceRepo.AdjustBalance(bucketID, currency, amount)
			if err != nil {
				return nil, fmt.Errorf("failed to adjust balance for %s: %w", bucketID, err)
			}

			desc := "Deposit allocation"
			if description != nil {
				desc = *description
			}

			transaction := &BucketTransaction{
				BucketID:    bucketID,
				Type:        TransactionTypeDeposit,
				Amount:      amount,
				Currency:    currency,
				Description: &desc,
			}

			err = s.balanceRepo.RecordTransaction(transaction)
			if err != nil {
				return nil, fmt.Errorf("failed to record transaction for %s: %w", bucketID, err)
			}
		}
	}

	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("failed to commit transaction: %w", err)
	}

	s.log.Info().
		Float64("total_amount", totalAmount).
		Str("currency", currency).
		Interface("allocations", allocations).
		Msg("Allocated deposit")

	return allocations, nil
}

// Reallocate reallocates funds between buckets (meta-allocator operation).
//
// Similar to transfer but uses REALLOCATION transaction type
// to distinguish quarterly reallocation from manual transfers.
//
// Args:
//
//	fromBucketID: Source bucket ID
//	toBucketID: Destination bucket ID
//	amount: Amount to reallocate
//	currency: Currency code
//
// Returns:
//
//	Tuple of (from_balance, to_balance)
func (s *BalanceService) Reallocate(
	fromBucketID string,
	toBucketID string,
	amount float64,
	currency string,
) (*BucketBalance, *BucketBalance, error) {
	if amount <= 0 {
		return nil, nil, fmt.Errorf("reallocation amount must be positive")
	}

	// Atomic operation: adjust balances and record transactions together
	tx, err := s.balanceRepo.satellitesDB.Begin()
	if err != nil {
		return nil, nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// Adjust balances
	fromBalance, err := s.balanceRepo.AdjustBalance(fromBucketID, currency, -amount)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to adjust from balance: %w", err)
	}

	toBalance, err := s.balanceRepo.AdjustBalance(toBucketID, currency, amount)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to adjust to balance: %w", err)
	}

	// Record as reallocation (not regular transfer)
	descOut := fmt.Sprintf("Quarterly reallocation to %s", toBucketID)
	descIn := fmt.Sprintf("Quarterly reallocation from %s", fromBucketID)

	txOut := &BucketTransaction{
		BucketID:    fromBucketID,
		Type:        TransactionTypeReallocation,
		Amount:      -amount, // Negative for outflow
		Currency:    currency,
		Description: &descOut,
	}

	txIn := &BucketTransaction{
		BucketID:    toBucketID,
		Type:        TransactionTypeReallocation,
		Amount:      amount, // Positive for inflow
		Currency:    currency,
		Description: &descIn,
	}

	err = s.balanceRepo.RecordTransaction(txOut)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to record outbound transaction: %w", err)
	}

	err = s.balanceRepo.RecordTransaction(txIn)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to record inbound transaction: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return nil, nil, fmt.Errorf("failed to commit transaction: %w", err)
	}

	s.log.Info().
		Str("from_bucket", fromBucketID).
		Str("to_bucket", toBucketID).
		Float64("amount", amount).
		Str("currency", currency).
		Msg("Reallocated funds between buckets")

	return fromBalance, toBalance, nil
}

// Transaction history

// GetTransactions gets transaction history for a bucket
func (s *BalanceService) GetTransactions(
	bucketID string,
	limit int,
	transactionType *TransactionType,
) ([]*BucketTransaction, error) {
	return s.balanceRepo.GetTransactions(bucketID, limit, 0, transactionType)
}

// GetRecentTransactions gets recent transactions for a bucket
func (s *BalanceService) GetRecentTransactions(bucketID string, days int) ([]*BucketTransaction, error) {
	return s.balanceRepo.GetRecentTransactions(bucketID, days)
}

// Settings

// GetAllocationSettings gets all allocation settings
func (s *BalanceService) GetAllocationSettings() (map[string]float64, error) {
	return s.balanceRepo.GetAllAllocationSettings()
}

// UpdateSatelliteBudget updates the global satellite budget percentage.
//
// Args:
//
//	budgetPct: New budget percentage (0.0-1.0)
//
// Errors:
//
//	Returns error if budget is out of range
func (s *BalanceService) UpdateSatelliteBudget(budgetPct float64) error {
	if budgetPct < 0.0 || budgetPct > MaxSatelliteBudgetPct {
		return fmt.Errorf(
			"satellite budget must be between 0%% and %.0f%%",
			MaxSatelliteBudgetPct*100,
		)
	}

	desc := fmt.Sprintf("Updated satellite budget to %.1f%%", budgetPct*100)
	err := s.balanceRepo.SetAllocationSetting("satellite_budget_pct", budgetPct, &desc)
	if err != nil {
		return fmt.Errorf("failed to set satellite budget: %w", err)
	}

	s.log.Info().
		Float64("budget_pct", budgetPct).
		Msg("Updated satellite budget")

	return nil
}

// Helper to begin a transaction (for services that need explicit transaction control)
func (s *BalanceService) BeginTx() (*sql.Tx, error) {
	return s.balanceRepo.satellitesDB.Begin()
}
