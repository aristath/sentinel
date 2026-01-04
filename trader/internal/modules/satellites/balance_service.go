package satellites

import (
	"database/sql"
	"fmt"

	"github.com/aristath/arduino-trader/internal/modules/cash_utils"
	"github.com/rs/zerolog"
)

// CashManager interface defines operations for managing cash as securities and positions
// This interface breaks the circular dependency between satellites and cash_flows packages
type CashManager interface {
	UpdateCashPosition(bucketID string, currency string, balance float64) error
	GetCashBalance(bucketID string, currency string) (float64, error)
	GetAllCashBalances(bucketID string) (map[string]float64, error)
	GetTotalByCurrency(currency string) (float64, error)
	GetAllCashSymbols() ([]string, error) // Returns all cash position symbols
	AdjustCashBalance(bucketID string, currency string, delta float64) (float64, error)
}

// BalanceService provides atomic cash operations using cash positions.
//
// ARCHITECTURAL CHANGE: Cash balances are now stored as positions in portfolio.db
// (synthetic securities with product_type="CASH" and symbols like "CASH:EUR:core").
//
// This eliminates the bucket_balances table and uses positions as the single source of truth.
// All operations that affect cash balances update positions and record transactions atomically.
//
// Rewritten from Python faithful translation to use cash-as-positions architecture.
type BalanceService struct {
	cashManager CashManager        // Interface to break circular dependency
	balanceRepo *BalanceRepository // Still used for transaction recording
	bucketRepo  *BucketRepository
	log         zerolog.Logger
}

// Maximum allowed satellite budget (safety limit to prevent over-allocation)
const MaxSatelliteBudgetPct = 0.30 // 30%

// NewBalanceService creates a new balance service
func NewBalanceService(
	cashManager CashManager,
	balanceRepo *BalanceRepository,
	bucketRepo *BucketRepository,
	log zerolog.Logger,
) *BalanceService {
	return &BalanceService{
		cashManager: cashManager,
		balanceRepo: balanceRepo,
		bucketRepo:  bucketRepo,
		log:         log,
	}
}

// Query methods

// GetBalance gets balance for a bucket in a specific currency
// Now queries cash positions instead of bucket_balances table
func (s *BalanceService) GetBalance(bucketID string, currency string) (*BucketBalance, error) {
	amount, err := s.cashManager.GetCashBalance(bucketID, currency)
	if err != nil {
		return nil, fmt.Errorf("failed to get cash balance: %w", err)
	}

	if amount == 0 {
		return nil, nil // No balance = nil (consistent with old behavior)
	}

	return &BucketBalance{
		BucketID: bucketID,
		Currency: currency,
		Balance:  amount,
	}, nil
}

// GetBalanceAmount gets balance amount, returning 0 if not found
func (s *BalanceService) GetBalanceAmount(bucketID string, currency string) (float64, error) {
	return s.cashManager.GetCashBalance(bucketID, currency)
}

// GetAllBalances gets all currency balances for a bucket
func (s *BalanceService) GetAllBalances(bucketID string) ([]*BucketBalance, error) {
	balancesMap, err := s.cashManager.GetAllCashBalances(bucketID)
	if err != nil {
		return nil, fmt.Errorf("failed to get all cash balances: %w", err)
	}

	var balances []*BucketBalance
	for currency, amount := range balancesMap {
		balances = append(balances, &BucketBalance{
			BucketID: bucketID,
			Currency: currency,
			Balance:  amount,
		})
	}

	return balances, nil
}

// GetTotalByCurrency gets total virtual balance across all buckets for a currency
func (s *BalanceService) GetTotalByCurrency(currency string) (float64, error) {
	return s.cashManager.GetTotalByCurrency(currency)
}

// GetAllCurrencies gets all distinct currencies that have balances
func (s *BalanceService) GetAllCurrencies() ([]string, error) {
	// Get all cash symbols
	symbols, err := s.cashManager.GetAllCashSymbols()
	if err != nil {
		return nil, fmt.Errorf("failed to get all cash symbols: %w", err)
	}

	// Extract unique currencies
	currencySet := make(map[string]bool)
	for _, symbol := range symbols {
		currency, _, err := cash_utils.ParseCashSymbol(symbol)
		if err != nil {
			s.log.Warn().Err(err).Str("symbol", symbol).Msg("Failed to parse cash symbol")
			continue
		}
		currencySet[currency] = true
	}

	var currencies []string
	for currency := range currencySet {
		currencies = append(currencies, currency)
	}

	return currencies, nil
}

// GetPortfolioSummary gets summary of all buckets and their balances.
//
// Returns:
//
//	Map of bucket_id to map of currency -> balance
//	Returns empty map if no buckets exist (fresh installation)
func (s *BalanceService) GetPortfolioSummary() (map[string]map[string]float64, error) {
	buckets, err := s.bucketRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get buckets: %w", err)
	}

	// Handle empty buckets (fresh installation)
	summary := make(map[string]map[string]float64)
	if len(buckets) == 0 {
		return summary, nil
	}

	for _, bucket := range buckets {
		balances, err := s.cashManager.GetAllCashBalances(bucket.ID)
		if err != nil {
			return nil, fmt.Errorf("failed to get balances for bucket %s: %w", bucket.ID, err)
		}

		// Initialize map for bucket if it doesn't exist
		if summary[bucket.ID] == nil {
			summary[bucket.ID] = make(map[string]float64)
		}
		summary[bucket.ID] = balances
	}

	return summary, nil
}

// Atomic cash operations

// RecordTradeSettlement records a trade settlement, atomically updating balance.
//
// Args:
//
//	bucketID: Bucket that executed the trade
//	amount: Trade amount (positive)
//	currency: Currency code
//	isBuy: true for buy (cash out), false for sell (cash in)
//	description: Optional description
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

	// Atomic operation: adjust cash position and record transaction together
	// Note: We use satellitesDB transaction for bucket_transactions table
	tx, err := s.balanceRepo.satellitesDB.Begin()
	if err != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() {
		if err != nil {
			tx.Rollback()
		}
	}()

	// Adjust cash position (updates positions table in portfolio.db)
	newBalance, err := s.cashManager.AdjustCashBalance(bucketID, currency, delta)
	if err != nil {
		return nil, fmt.Errorf("failed to adjust cash balance: %w", err)
	}

	// Record transaction in satellites.db
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

	err = s.balanceRepo.RecordTransaction(transaction, tx)
	if err != nil {
		return nil, fmt.Errorf("failed to record transaction: %w", err)
	}

	err = tx.Commit()
	if err != nil {
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
		Float64("new_balance", newBalance).
		Msg("Recorded trade settlement")

	return &BucketBalance{
		BucketID: bucketID,
		Currency: currency,
		Balance:  newBalance,
	}, nil
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
		return nil, fmt.Errorf("amount must be positive")
	}

	// Atomic operation
	tx, err := s.balanceRepo.satellitesDB.Begin()
	if err != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() {
		if err != nil {
			tx.Rollback()
		}
	}()

	// Add cash (positive delta)
	newBalance, err := s.cashManager.AdjustCashBalance(bucketID, currency, amount)
	if err != nil {
		return nil, fmt.Errorf("failed to adjust cash balance: %w", err)
	}

	// Record transaction
	desc := "Dividend payment"
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

	err = s.balanceRepo.RecordTransaction(transaction, tx)
	if err != nil {
		return nil, fmt.Errorf("failed to record transaction: %w", err)
	}

	err = tx.Commit()
	if err != nil {
		return nil, fmt.Errorf("failed to commit transaction: %w", err)
	}

	s.log.Info().
		Str("bucket_id", bucketID).
		Float64("amount", amount).
		Str("currency", currency).
		Float64("new_balance", newBalance).
		Msg("Recorded dividend")

	return &BucketBalance{
		BucketID: bucketID,
		Currency: currency,
		Balance:  newBalance,
	}, nil
}

// TransferBetweenBuckets transfers cash between two buckets atomically.
//
// Args:
//
//	fromBucketID: Source bucket
//	toBucketID: Destination bucket
//	amount: Amount to transfer (positive)
//	currency: Currency code
//	description: Optional description
//
// Returns:
//
//	(source balance, dest balance, error)
func (s *BalanceService) TransferBetweenBuckets(
	fromBucketID string,
	toBucketID string,
	amount float64,
	currency string,
	description *string,
) (*BucketBalance, *BucketBalance, error) {
	if amount <= 0 {
		return nil, nil, fmt.Errorf("amount must be positive")
	}

	if fromBucketID == toBucketID {
		return nil, nil, fmt.Errorf("cannot transfer to same bucket")
	}

	// Verify buckets exist
	fromBucket, err := s.bucketRepo.GetByID(fromBucketID)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to get source bucket: %w", err)
	}
	if fromBucket == nil {
		return nil, nil, fmt.Errorf("source bucket not found: %s", fromBucketID)
	}

	toBucket, err := s.bucketRepo.GetByID(toBucketID)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to get destination bucket: %w", err)
	}
	if toBucket == nil {
		return nil, nil, fmt.Errorf("destination bucket not found: %s", toBucketID)
	}

	// Check sufficient balance
	fromBalance, err := s.cashManager.GetCashBalance(fromBucketID, currency)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to get source balance: %w", err)
	}
	if fromBalance < amount {
		return nil, nil, fmt.Errorf(
			"insufficient balance in %s: has %.2f %s, needs %.2f",
			fromBucket.Name, fromBalance, currency, amount,
		)
	}

	// Atomic operation
	tx, err := s.balanceRepo.satellitesDB.Begin()
	if err != nil {
		return nil, nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() {
		if err != nil {
			tx.Rollback()
		}
	}()

	// Deduct from source
	newFromBalance, err := s.cashManager.AdjustCashBalance(fromBucketID, currency, -amount)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to deduct from source: %w", err)
	}

	// Add to destination
	newToBalance, err := s.cashManager.AdjustCashBalance(toBucketID, currency, amount)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to add to destination: %w", err)
	}

	// Record transfer_out transaction
	desc := fmt.Sprintf("Transfer to %s", toBucket.Name)
	if description != nil {
		desc = *description
	}

	outTx := &BucketTransaction{
		BucketID:    fromBucketID,
		Type:        TransactionTypeTransferOut,
		Amount:      amount,
		Currency:    currency,
		Description: &desc,
	}

	err = s.balanceRepo.RecordTransaction(outTx, tx)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to record transfer out: %w", err)
	}

	// Record transfer_in transaction
	inDesc := fmt.Sprintf("Transfer from %s", fromBucket.Name)
	if description != nil {
		inDesc = *description
	}

	inTx := &BucketTransaction{
		BucketID:    toBucketID,
		Type:        TransactionTypeTransferIn,
		Amount:      amount,
		Currency:    currency,
		Description: &inDesc,
	}

	err = s.balanceRepo.RecordTransaction(inTx, tx)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to record transfer in: %w", err)
	}

	err = tx.Commit()
	if err != nil {
		return nil, nil, fmt.Errorf("failed to commit transaction: %w", err)
	}

	s.log.Info().
		Str("from_bucket", fromBucket.Name).
		Str("to_bucket", toBucket.Name).
		Float64("amount", amount).
		Str("currency", currency).
		Msg("Transferred between buckets")

	return &BucketBalance{
			BucketID: fromBucketID,
			Currency: currency,
			Balance:  newFromBalance,
		}, &BucketBalance{
			BucketID: toBucketID,
			Currency: currency,
			Balance:  newToBalance,
		}, nil
}

// AllocateDeposit allocates a new deposit across buckets based on allocation settings.
//
// Args:
//
//	amount: Deposit amount (positive)
//	currency: Currency code
//	description: Optional description
//
// Returns:
//
//	Map of bucket_id -> allocated amount
func (s *BalanceService) AllocateDeposit(
	amount float64,
	currency string,
	description *string,
) (map[string]float64, error) {
	if amount <= 0 {
		return nil, fmt.Errorf("amount must be positive")
	}

	// Get allocation settings
	settings, err := s.balanceRepo.GetAllAllocationSettings()
	if err != nil {
		return nil, fmt.Errorf("failed to get allocation settings: %w", err)
	}

	satelliteBudgetPct := settings["satellite_budget_pct"]

	// Calculate allocation
	coreAmount := amount
	satelliteAmount := 0.0

	if satelliteBudgetPct > 0 {
		satelliteAmount = amount * satelliteBudgetPct
		coreAmount = amount - satelliteAmount
	}

	// Get active satellites before starting transaction (to avoid transaction isolation issues)
	var activeSatellites []*Bucket
	if satelliteAmount > 0 {
		satellites, err := s.bucketRepo.GetByType(BucketTypeSatellite)
		if err != nil {
			return nil, fmt.Errorf("failed to get satellites: %w", err)
		}

		activeSatellites = make([]*Bucket, 0)
		for _, sat := range satellites {
			if sat.Status == BucketStatusActive || sat.Status == BucketStatusAccumulating {
				activeSatellites = append(activeSatellites, sat)
			}
		}
	}

	// Atomic operation
	tx, err := s.balanceRepo.satellitesDB.Begin()
	if err != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() {
		if err != nil {
			tx.Rollback()
		}
	}()

	allocation := make(map[string]float64)

	// Allocate to core
	if coreAmount > 0 {
		_, err = s.cashManager.AdjustCashBalance("core", currency, coreAmount)
		if err != nil {
			return nil, fmt.Errorf("failed to allocate to core: %w", err)
		}

		desc := fmt.Sprintf("Deposit allocation (%.1f%% to core)", (1-satelliteBudgetPct)*100)
		if description != nil {
			desc = *description
		}

		coreTx := &BucketTransaction{
			BucketID:    "core",
			Type:        TransactionTypeDeposit,
			Amount:      coreAmount,
			Currency:    currency,
			Description: &desc,
		}

		err = s.balanceRepo.RecordTransaction(coreTx, tx)
		if err != nil {
			return nil, fmt.Errorf("failed to record core deposit: %w", err)
		}

		allocation["core"] = coreAmount
	}

	// Allocate to satellites if configured
	if satelliteAmount > 0 {
		if len(activeSatellites) > 0 {
			// Split equally among active satellites for now
			// TODO: Implement weighted allocation based on performance
			perSatellite := satelliteAmount / float64(len(activeSatellites))

			for _, sat := range activeSatellites {
				_, err = s.cashManager.AdjustCashBalance(sat.ID, currency, perSatellite)
				if err != nil {
					return nil, fmt.Errorf("failed to allocate to satellite %s: %w", sat.ID, err)
				}

				satDesc := fmt.Sprintf("Deposit allocation to %s", sat.Name)
				satTx := &BucketTransaction{
					BucketID:    sat.ID,
					Type:        TransactionTypeDeposit,
					Amount:      perSatellite,
					Currency:    currency,
					Description: &satDesc,
				}

				err = s.balanceRepo.RecordTransaction(satTx, tx)
				if err != nil {
					return nil, fmt.Errorf("failed to record satellite deposit: %w", err)
				}

				allocation[sat.ID] = perSatellite
			}
		} else {
			// No active satellites, allocate all to core
			_, err = s.cashManager.AdjustCashBalance("core", currency, satelliteAmount)
			if err != nil {
				return nil, fmt.Errorf("failed to allocate satellite portion to core: %w", err)
			}

			desc := "Deposit - no active satellites, allocated to core"
			extraTx := &BucketTransaction{
				BucketID:    "core",
				Type:        TransactionTypeDeposit,
				Amount:      satelliteAmount,
				Currency:    currency,
				Description: &desc,
			}

			err = s.balanceRepo.RecordTransaction(extraTx, tx)
			if err != nil {
				return nil, fmt.Errorf("failed to record extra core deposit: %w", err)
			}

			allocation["core"] += satelliteAmount
		}
	}

	// Commit transaction if all operations succeeded
	err = tx.Commit()
	if err != nil {
		return nil, fmt.Errorf("failed to commit transaction: %w", err)
	}

	s.log.Info().
		Float64("total_amount", amount).
		Str("currency", currency).
		Interface("allocation", allocation).
		Msg("Allocated deposit")

	return allocation, nil
}

// Reallocate reallocates cash between core and satellites based on performance.
//
// Args:
//
//	currency: Currency to reallocate
//
// Returns:
//
//	Map of bucket_id -> new balance
func (s *BalanceService) Reallocate(currency string) (map[string]float64, error) {
	// Get current total balance
	totalBalance, err := s.cashManager.GetTotalByCurrency(currency)
	if err != nil {
		return nil, fmt.Errorf("failed to get total balance: %w", err)
	}

	if totalBalance == 0 {
		return map[string]float64{}, nil
	}

	// Get allocation settings
	settings, err := s.balanceRepo.GetAllAllocationSettings()
	if err != nil {
		return nil, fmt.Errorf("failed to get allocation settings: %w", err)
	}

	satelliteBudgetPct := settings["satellite_budget_pct"]

	// Calculate target allocations
	targetCore := totalBalance * (1 - satelliteBudgetPct)

	// Get current core balance
	coreBalance, err := s.cashManager.GetCashBalance("core", currency)
	if err != nil {
		return nil, fmt.Errorf("failed to get core balance: %w", err)
	}

	// Calculate reallocation needed
	coreAdjustment := targetCore - coreBalance
	satelliteAdjustment := -coreAdjustment

	if satelliteAdjustment < 0.01 && satelliteAdjustment > -0.01 {
		// No significant reallocation needed
		s.log.Info().
			Str("currency", currency).
			Float64("total_balance", totalBalance).
			Msg("No reallocation needed")

		return map[string]float64{
			"core": coreBalance,
		}, nil
	}

	// Atomic operation
	tx, err := s.balanceRepo.satellitesDB.Begin()
	if err != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() {
		if err != nil {
			tx.Rollback()
		}
	}()

	newBalances := make(map[string]float64)

	// Adjust core
	newCoreBalance, err := s.cashManager.AdjustCashBalance("core", currency, coreAdjustment)
	if err != nil {
		return nil, fmt.Errorf("failed to adjust core: %w", err)
	}
	newBalances["core"] = newCoreBalance

	// Record core transaction
	coreDesc := fmt.Sprintf("Reallocation adjustment")
	coreTxType := TransactionTypeReallocation
	coreTx := &BucketTransaction{
		BucketID:    "core",
		Type:        coreTxType,
		Amount:      coreAdjustment,
		Currency:    currency,
		Description: &coreDesc,
	}

	err = s.balanceRepo.RecordTransaction(coreTx, tx)
	if err != nil {
		return nil, fmt.Errorf("failed to record core reallocation: %w", err)
	}

	// Adjust satellites proportionally
	satellites, err := s.bucketRepo.GetByType(BucketTypeSatellite)
	if err != nil {
		return nil, fmt.Errorf("failed to get satellites: %w", err)
	}

	activeSatellites := make([]*Bucket, 0)
	for _, sat := range satellites {
		if sat.Status == BucketStatusActive {
			activeSatellites = append(activeSatellites, sat)
		}
	}

	if len(activeSatellites) > 0 {
		perSatellite := satelliteAdjustment / float64(len(activeSatellites))

		for _, sat := range activeSatellites {
			newSatBalance, err := s.cashManager.AdjustCashBalance(sat.ID, currency, perSatellite)
			if err != nil {
				return nil, fmt.Errorf("failed to adjust satellite %s: %w", sat.ID, err)
			}
			newBalances[sat.ID] = newSatBalance

			satDesc := fmt.Sprintf("Reallocation adjustment")
			satTx := &BucketTransaction{
				BucketID:    sat.ID,
				Type:        TransactionTypeReallocation,
				Amount:      perSatellite,
				Currency:    currency,
				Description: &satDesc,
			}

			err = s.balanceRepo.RecordTransaction(satTx, tx)
			if err != nil {
				return nil, fmt.Errorf("failed to record satellite reallocation: %w", err)
			}
		}
	}

	err = tx.Commit()
	if err != nil {
		return nil, fmt.Errorf("failed to commit transaction: %w", err)
	}

	s.log.Info().
		Str("currency", currency).
		Float64("core_adjustment", coreAdjustment).
		Int("satellites_adjusted", len(activeSatellites)).
		Msg("Completed reallocation")

	return newBalances, nil
}

// GetTransactions gets transactions for a bucket
func (s *BalanceService) GetTransactions(bucketID string, limit int, offset int, transactionType *TransactionType) ([]*BucketTransaction, error) {
	return s.balanceRepo.GetTransactions(bucketID, limit, offset, transactionType)
}

// GetRecentTransactions gets recent transactions for a bucket within a time window
func (s *BalanceService) GetRecentTransactions(bucketID string, days int) ([]*BucketTransaction, error) {
	return s.balanceRepo.GetRecentTransactions(bucketID, days)
}

// GetAllocationSettings gets the allocation settings
func (s *BalanceService) GetAllocationSettings() (map[string]float64, error) {
	return s.balanceRepo.GetAllAllocationSettings()
}

// UpdateSatelliteBudget updates the satellite budget percentage
func (s *BalanceService) UpdateSatelliteBudget(budgetPct float64) error {
	if budgetPct < 0 || budgetPct > MaxSatelliteBudgetPct {
		return fmt.Errorf(
			"satellite budget must be between 0 and %.0f%%, got %.1f%%",
			MaxSatelliteBudgetPct*100,
			budgetPct*100,
		)
	}

	return s.balanceRepo.SetAllocationSetting("satellite_budget_pct", budgetPct, nil)
}

// BeginTx begins a transaction on the satellites database
func (s *BalanceService) BeginTx() (*sql.Tx, error) {
	return s.balanceRepo.satellitesDB.Begin()
}
