package cash_flows

import (
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/rs/zerolog"
)

// CashManager manages cash balances using the dedicated cash_balances table
// This replaces CashSecurityManager and treats cash as balances, not securities/positions
type CashManager struct {
	cashRepo     *CashRepository
	positionRepo portfolio.PositionRepositoryInterface // Temporary: for dual-write during migration
	log          zerolog.Logger
	mu           sync.RWMutex // Protects concurrent access
}

// NewCashManager creates a new cash manager
func NewCashManager(
	cashRepo *CashRepository,
	log zerolog.Logger,
) *CashManager {
	return &CashManager{
		cashRepo: cashRepo,
		log:      log.With().Str("manager", "cash").Logger(),
	}
}

// NewCashManagerWithDualWrite creates a new cash manager with dual-write support
// This is used during migration to write to both cash_balances and positions tables
func NewCashManagerWithDualWrite(
	cashRepo *CashRepository,
	positionRepo portfolio.PositionRepositoryInterface,
	log zerolog.Logger,
) *CashManager {
	return &CashManager{
		cashRepo:     cashRepo,
		positionRepo: positionRepo,
		log:          log.With().Str("manager", "cash").Logger(),
	}
}

// UpdateCashPosition updates or creates a cash balance for the given currency
// If balance is 0, the balance is deleted from cash_balances table
// This is the main method for syncing cash balances from external sources
func (m *CashManager) UpdateCashPosition(currency string, balance float64) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	// Update cash_balances table (primary storage)
	if balance <= 0 {
		err := m.cashRepo.Delete(currency)
		if err != nil {
			return fmt.Errorf("failed to delete cash balance: %w", err)
		}
	} else {
		err := m.cashRepo.Upsert(currency, balance)
		if err != nil {
			return fmt.Errorf("failed to upsert cash balance: %w", err)
		}
	}

	// Temporary: Dual-write to positions table for backward compatibility
	// This will be removed in a later phase
	if m.positionRepo != nil {
		err := m.updateCashPositionLegacy(currency, balance)
		if err != nil {
			m.log.Warn().
				Err(err).
				Str("currency", currency).
				Msg("Failed to update legacy cash position (non-critical during migration)")
		}
	}

	m.log.Info().
		Str("currency", currency).
		Float64("balance", balance).
		Msg("Updated cash balance")

	return nil
}

// updateCashPositionLegacy updates cash position in positions table (temporary during migration)
// Must be called with m.mu held
func (m *CashManager) updateCashPositionLegacy(currency string, balance float64) error {
	if m.positionRepo == nil {
		return nil // No legacy support
	}

	symbol := fmt.Sprintf("CASH:%s", strings.ToUpper(currency))

	if balance <= 0 {
		// Delete legacy position (CASH positions use symbol as ISIN)
		err := m.positionRepo.Delete(symbol)
		if err != nil {
			return fmt.Errorf("failed to delete legacy cash position: %w", err)
		}
		return nil
	}

	// Create legacy position for backward compatibility
	// CASH positions use symbol as ISIN
	now := time.Now().Format(time.RFC3339)
	position := portfolio.Position{
		ISIN:           symbol, // CASH positions use symbol as ISIN
		Symbol:         symbol,
		Quantity:       balance,
		AvgPrice:       1.0,
		CurrentPrice:   1.0,
		Currency:       currency,
		CurrencyRate:   1.0,
		MarketValueEUR: balance,
		LastUpdated:    now,
	}

	// Check if position exists to preserve FirstBoughtAt
	existing, err := m.positionRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to check existing legacy position: %w", err)
	}

	if existing != nil && existing.FirstBoughtAt != "" {
		position.FirstBoughtAt = existing.FirstBoughtAt
	} else {
		position.FirstBoughtAt = now
	}

	err = m.positionRepo.Upsert(position)
	if err != nil {
		return fmt.Errorf("failed to upsert legacy cash position: %w", err)
	}

	return nil
}

// GetCashBalance returns the cash balance for the given currency
// Returns 0 if no balance exists (not an error)
func (m *CashManager) GetCashBalance(currency string) (float64, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	return m.cashRepo.Get(currency)
}

// GetAllCashBalances returns all cash balances
// Returns map of currency -> balance
func (m *CashManager) GetAllCashBalances() (map[string]float64, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	return m.cashRepo.GetAll()
}

// AdjustCashBalance adjusts a cash balance by a delta (can be positive or negative)
// This is useful for trade settlements, dividends, etc.
func (m *CashManager) AdjustCashBalance(currency string, delta float64) (float64, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	// Get current balance
	current, err := m.cashRepo.Get(currency)
	if err != nil {
		return 0, fmt.Errorf("failed to get current balance: %w", err)
	}

	newBalance := current + delta

	// Update balance
	if newBalance <= 0 {
		err = m.cashRepo.Delete(currency)
		if err != nil {
			return 0, fmt.Errorf("failed to delete cash balance: %w", err)
		}
		newBalance = 0
	} else {
		err = m.cashRepo.Upsert(currency, newBalance)
		if err != nil {
			return 0, fmt.Errorf("failed to update cash balance: %w", err)
		}
	}

	// Temporary: Dual-write to positions table for backward compatibility
	if m.positionRepo != nil {
		err = m.updateCashPositionLegacy(currency, newBalance)
		if err != nil {
			m.log.Warn().
				Err(err).
				Str("currency", currency).
				Msg("Failed to update legacy cash position (non-critical during migration)")
		}
	}

	return newBalance, nil
}
