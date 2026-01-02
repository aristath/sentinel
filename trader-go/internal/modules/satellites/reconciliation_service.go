package satellites

import (
	"fmt"
	"math"
	"time"

	"github.com/rs/zerolog"
)

// ReconciliationResult represents the result of a reconciliation check or operation
type ReconciliationResult struct {
	Currency        string             `json:"currency"`
	VirtualTotal    float64            `json:"virtual_total"`
	ActualTotal     float64            `json:"actual_total"`
	Difference      float64            `json:"difference"`
	IsReconciled    bool               `json:"is_reconciled"`
	AdjustmentsMade map[string]float64 `json:"adjustments_made"` // bucket_id -> adjustment
	Timestamp       string             `json:"timestamp"`
}

// DifferencePct returns difference as percentage of actual
func (r *ReconciliationResult) DifferencePct() float64 {
	if r.ActualTotal == 0 {
		if r.VirtualTotal == 0 {
			return 0.0
		}
		return math.Inf(1)
	}
	return math.Abs(r.Difference) / r.ActualTotal
}

// ReconciliationService ensures virtual balances match brokerage reality.
//
// The critical invariant this service maintains:
// SUM(bucket_balances for currency X) == Actual brokerage balance for currency X
//
// Reconciliation can happen:
// 1. On startup - verify state
// 2. Periodically - catch drift
// 3. After significant operations - immediate verification
//
// Faithful translation from Python: app/modules/satellites/services/reconciliation_service.py
type ReconciliationService struct {
	balanceRepo *BalanceRepository
	bucketRepo  *BucketRepository
	log         zerolog.Logger
}

// Threshold below which differences are auto-corrected (rounding errors)
// Increased to €5 to handle accumulated rounding across multiple trades
const AutoCorrectThreshold = 5.0 // 5 EUR/USD

// NewReconciliationService creates a new reconciliation service
func NewReconciliationService(
	balanceRepo *BalanceRepository,
	bucketRepo *BucketRepository,
	log zerolog.Logger,
) *ReconciliationService {
	return &ReconciliationService{
		balanceRepo: balanceRepo,
		bucketRepo:  bucketRepo,
		log:         log,
	}
}

// CheckInvariant checks if virtual balances match actual brokerage balance.
//
// Args:
//
//	currency: Currency to check
//	actualBalance: Actual balance from brokerage
//
// Returns:
//
//	ReconciliationResult with check details
func (s *ReconciliationService) CheckInvariant(
	currency string,
	actualBalance float64,
) (*ReconciliationResult, error) {
	virtualTotal, err := s.balanceRepo.GetTotalByCurrency(currency)
	if err != nil {
		return nil, fmt.Errorf("failed to get virtual total: %w", err)
	}

	difference := virtualTotal - actualBalance

	return &ReconciliationResult{
		Currency:        currency,
		VirtualTotal:    virtualTotal,
		ActualTotal:     actualBalance,
		Difference:      difference,
		IsReconciled:    math.Abs(difference) < 0.01, // Allow 1 cent tolerance
		AdjustmentsMade: make(map[string]float64),
		Timestamp:       time.Now().Format(time.RFC3339),
	}, nil
}

// Reconcile reconciles virtual balances with actual brokerage balance.
//
// If there's a discrepancy:
// 1. Small differences (< threshold) are auto-corrected to core
// 2. Large differences log a warning and require manual intervention
//
// Args:
//
//	currency: Currency to reconcile
//	actualBalance: Actual balance from brokerage
//	autoCorrectThreshold: Max difference to auto-correct (nil = use default)
//
// Returns:
//
//	ReconciliationResult with reconciliation details
func (s *ReconciliationService) Reconcile(
	currency string,
	actualBalance float64,
	autoCorrectThreshold *float64,
) (*ReconciliationResult, error) {
	threshold := AutoCorrectThreshold
	if autoCorrectThreshold != nil {
		threshold = *autoCorrectThreshold
	}

	// Check current state
	result, err := s.CheckInvariant(currency, actualBalance)
	if err != nil {
		return nil, fmt.Errorf("failed to check invariant: %w", err)
	}

	if result.IsReconciled {
		s.log.Debug().
			Str("currency", currency).
			Msg("Reconciliation check passed")
		return result, nil
	}

	difference := result.Difference
	adjustments := make(map[string]float64)

	if math.Abs(difference) <= threshold {
		// Auto-correct small differences by adjusting core
		adjustment := -difference // If virtual > actual, reduce core

		_, err := s.balanceRepo.AdjustBalance("core", currency, adjustment)
		if err != nil {
			return nil, fmt.Errorf("failed to adjust core balance: %w", err)
		}

		// Record adjustment transaction
		desc := fmt.Sprintf("Reconciliation adjustment (%+.2f discrepancy)", difference)
		tx := &BucketTransaction{
			BucketID:    "core",
			Type:        TransactionTypeReallocation,
			Amount:      adjustment,
			Currency:    currency,
			Description: &desc,
		}

		err = s.balanceRepo.RecordTransaction(tx)
		if err != nil {
			return nil, fmt.Errorf("failed to record transaction: %w", err)
		}

		adjustments["core"] = adjustment
		s.log.Info().
			Str("currency", currency).
			Float64("discrepancy", difference).
			Msg("Auto-corrected discrepancy by adjusting core balance")

		result.AdjustmentsMade = adjustments
		result.IsReconciled = true
	} else {
		// Large discrepancy - log warning
		s.log.Warn().
			Str("currency", currency).
			Float64("virtual_total", result.VirtualTotal).
			Float64("actual_total", result.ActualTotal).
			Float64("difference", difference).
			Msg("Large discrepancy detected. Manual intervention required.")
	}

	return result, nil
}

// ReconcileAll reconciles all currencies.
//
// Args:
//
//	actualBalances: Map of currency -> actual balance
//	autoCorrectThreshold: Max difference to auto-correct (nil = use default)
//
// Returns:
//
//	List of reconciliation results
func (s *ReconciliationService) ReconcileAll(
	actualBalances map[string]float64,
	autoCorrectThreshold *float64,
) ([]*ReconciliationResult, error) {
	var results []*ReconciliationResult

	for currency, actualBalance := range actualBalances {
		result, err := s.Reconcile(currency, actualBalance, autoCorrectThreshold)
		if err != nil {
			return nil, fmt.Errorf("failed to reconcile %s: %w", currency, err)
		}
		results = append(results, result)
	}

	return results, nil
}

// GetBalanceBreakdown gets breakdown of virtual balances by bucket.
//
// Useful for debugging reconciliation issues.
//
// Args:
//
//	currency: Currency to break down
//
// Returns:
//
//	Map of bucket_id -> balance
func (s *ReconciliationService) GetBalanceBreakdown(currency string) (map[string]float64, error) {
	buckets, err := s.bucketRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get buckets: %w", err)
	}

	breakdown := make(map[string]float64)

	for _, bucket := range buckets {
		balance, err := s.balanceRepo.GetBalanceAmount(bucket.ID, currency)
		if err != nil {
			return nil, fmt.Errorf("failed to get balance for %s: %w", bucket.ID, err)
		}

		if balance != 0 {
			breakdown[bucket.ID] = balance
		}
	}

	return breakdown, nil
}

// InitializeFromBrokerage initializes virtual balances from actual brokerage state.
//
// Used on first startup or after a reset. All balances go to core.
//
// Args:
//
//	actualBalances: Map of currency -> actual balance
//
// Returns:
//
//	List of reconciliation results showing initial state
func (s *ReconciliationService) InitializeFromBrokerage(
	actualBalances map[string]float64,
) ([]*ReconciliationResult, error) {
	var results []*ReconciliationResult

	for currency, actualBalance := range actualBalances {
		// Check if we have any virtual balances
		virtualTotal, err := s.balanceRepo.GetTotalByCurrency(currency)
		if err != nil {
			return nil, fmt.Errorf("failed to get virtual total for %s: %w", currency, err)
		}

		if virtualTotal == 0 && actualBalance > 0 {
			// Initialize core with full balance
			_, err := s.balanceRepo.SetBalance("core", currency, actualBalance)
			if err != nil {
				return nil, fmt.Errorf("failed to set core balance for %s: %w", currency, err)
			}

			desc := "Initial balance from brokerage"
			tx := &BucketTransaction{
				BucketID:    "core",
				Type:        TransactionTypeDeposit,
				Amount:      actualBalance,
				Currency:    currency,
				Description: &desc,
			}

			err = s.balanceRepo.RecordTransaction(tx)
			if err != nil {
				return nil, fmt.Errorf("failed to record transaction for %s: %w", currency, err)
			}

			s.log.Info().
				Str("currency", currency).
				Float64("balance", actualBalance).
				Msg("Initialized core balance")
		}

		// Verify reconciliation
		result, err := s.CheckInvariant(currency, actualBalance)
		if err != nil {
			return nil, fmt.Errorf("failed to check invariant for %s: %w", currency, err)
		}
		results = append(results, result)
	}

	return results, nil
}

// ForceReconcileToCore forces reconciliation by adjusting core balance.
//
// WARNING: This should only be used when you're certain the
// actual brokerage balance is correct and virtual balances
// have drifted. It will overwrite core balance.
//
// Args:
//
//	currency: Currency to force reconcile
//	actualBalance: Actual brokerage balance
//
// Returns:
//
//	ReconciliationResult
func (s *ReconciliationService) ForceReconcileToCore(
	currency string,
	actualBalance float64,
) (*ReconciliationResult, error) {
	// Get sum of all non-core balances
	buckets, err := s.bucketRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get buckets: %w", err)
	}

	nonCoreTotal := 0.0

	for _, bucket := range buckets {
		if bucket.ID != "core" {
			balance, err := s.balanceRepo.GetBalanceAmount(bucket.ID, currency)
			if err != nil {
				return nil, fmt.Errorf("failed to get balance for %s: %w", bucket.ID, err)
			}
			nonCoreTotal += balance
		}
	}

	// Core should be actual minus all satellites
	coreShouldBe := actualBalance - nonCoreTotal

	// Get current core balance
	currentCore, err := s.balanceRepo.GetBalanceAmount("core", currency)
	if err != nil {
		return nil, fmt.Errorf("failed to get core balance: %w", err)
	}

	adjustment := coreShouldBe - currentCore

	adjustments := make(map[string]float64)

	if math.Abs(adjustment) > 0.01 {
		_, err := s.balanceRepo.SetBalance("core", currency, coreShouldBe)
		if err != nil {
			return nil, fmt.Errorf("failed to set core balance: %w", err)
		}

		desc := fmt.Sprintf("Force reconciliation (adjusted from %.2f)", currentCore)
		tx := &BucketTransaction{
			BucketID:    "core",
			Type:        TransactionTypeReallocation,
			Amount:      adjustment,
			Currency:    currency,
			Description: &desc,
		}

		err = s.balanceRepo.RecordTransaction(tx)
		if err != nil {
			return nil, fmt.Errorf("failed to record transaction: %w", err)
		}

		s.log.Warn().
			Str("currency", currency).
			Float64("old_balance", currentCore).
			Float64("new_balance", coreShouldBe).
			Msg("Force reconciled")

		adjustments["core"] = adjustment
	}

	return &ReconciliationResult{
		Currency:        currency,
		VirtualTotal:    actualBalance,
		ActualTotal:     actualBalance,
		Difference:      0.0,
		IsReconciled:    true,
		AdjustmentsMade: adjustments,
		Timestamp:       time.Now().Format(time.RFC3339),
	}, nil
}

// DiagnoseDiscrepancy diagnoses a balance discrepancy.
//
// Provides detailed information for debugging.
//
// Args:
//
//	currency: Currency with discrepancy
//	actualBalance: Actual brokerage balance
//
// Returns:
//
//	Map with diagnostic information
func (s *ReconciliationService) DiagnoseDiscrepancy(
	currency string,
	actualBalance float64,
) (map[string]interface{}, error) {
	// Get breakdown
	breakdown, err := s.GetBalanceBreakdown(currency)
	if err != nil {
		return nil, fmt.Errorf("failed to get breakdown: %w", err)
	}

	virtualTotal := 0.0
	for _, balance := range breakdown {
		virtualTotal += balance
	}

	// Get recent transactions
	var allTransactions []map[string]interface{}
	for bucketID := range breakdown {
		txs, err := s.balanceRepo.GetRecentTransactions(bucketID, 7)
		if err != nil {
			return nil, fmt.Errorf("failed to get transactions for %s: %w", bucketID, err)
		}

		for _, tx := range txs {
			desc := ""
			if tx.Description != nil {
				desc = *tx.Description
			}

			allTransactions = append(allTransactions, map[string]interface{}{
				"bucket_id":   tx.BucketID,
				"type":        string(tx.Type),
				"amount":      tx.Amount,
				"currency":    tx.Currency,
				"created_at":  tx.CreatedAt,
				"description": desc,
			})
		}
	}

	// Sort by time (reverse chronological)
	// Note: Simplified - proper sorting would require parsing timestamps

	// Take last 20
	if len(allTransactions) > 20 {
		allTransactions = allTransactions[:20]
	}

	return map[string]interface{}{
		"currency":            currency,
		"actual_balance":      actualBalance,
		"virtual_total":       virtualTotal,
		"difference":          virtualTotal - actualBalance,
		"breakdown":           breakdown,
		"recent_transactions": allTransactions,
		"timestamp":           time.Now().Format(time.RFC3339),
	}, nil
}
