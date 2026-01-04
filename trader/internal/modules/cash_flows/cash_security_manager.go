package cash_flows

import (
	"database/sql"
	"fmt"
	"sync"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/cash_utils"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/rs/zerolog"
)

// CashSecurityManager manages cash as synthetic securities and positions
// This is the core component for treating cash balances as positions in the portfolio
type CashSecurityManager struct {
	securityRepo *universe.SecurityRepository
	positionRepo portfolio.PositionRepositoryInterface
	universeDB   *sql.DB
	portfolioDB  *sql.DB
	log          zerolog.Logger
	mu           sync.RWMutex // Protects concurrent access
}

// NewCashSecurityManager creates a new cash security manager
func NewCashSecurityManager(
	securityRepo *universe.SecurityRepository,
	positionRepo portfolio.PositionRepositoryInterface,
	universeDB *sql.DB,
	portfolioDB *sql.DB,
	log zerolog.Logger,
) *CashSecurityManager {
	return &CashSecurityManager{
		securityRepo: securityRepo,
		positionRepo: positionRepo,
		universeDB:   universeDB,
		portfolioDB:  portfolioDB,
		log:          log.With().Str("manager", "cash_security").Logger(),
	}
}

// EnsureCashSecurity ensures a cash security exists for the given currency
// Creates the security if it doesn't exist, otherwise does nothing
// Returns error if creation fails
func (m *CashSecurityManager) EnsureCashSecurity(currency string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	symbol := cash_utils.MakeCashSymbol(currency)

	// Check if security already exists
	existing, err := m.securityRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to check if cash security exists: %w", err)
	}

	if existing != nil {
		// Security already exists
		m.log.Debug().
			Str("symbol", symbol).
			Str("currency", currency).
			Msg("Cash security already exists")
		return nil
	}

	// Create new cash security
	security := universe.Security{
		Symbol:             symbol,
		Name:               cash_utils.GetCashSecurityName(currency),
		ProductType:        string(universe.ProductTypeCash),
		Currency:           currency,
		Active:             true,
		AllowBuy:           false, // Can't buy cash as a security
		AllowSell:          false, // Can't sell cash as a security
		PriorityMultiplier: 1.0,
		MinLot:             1,
		LastSynced:         time.Now().Format(time.RFC3339),
	}

	err = m.securityRepo.Create(security)
	if err != nil {
		return fmt.Errorf("failed to create cash security: %w", err)
	}

	m.log.Info().
		Str("symbol", symbol).
		Str("currency", currency).
		Str("name", security.Name).
		Msg("Created cash security")

	return nil
}

// UpdateCashPosition updates or creates a cash position for the given currency
// If balance is 0, the position is deleted
// This is the main method for syncing cash balances from external sources
func (m *CashSecurityManager) UpdateCashPosition(currency string, balance float64) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	symbol := cash_utils.MakeCashSymbol(currency)

	// If balance is zero or negative, delete the position
	if balance <= 0 {
		return m.deleteCashPositionLocked(symbol, currency, balance)
	}

	// Ensure the cash security exists
	if err := m.ensureCashSecurityLocked(currency); err != nil {
		return fmt.Errorf("failed to ensure cash security: %w", err)
	}

	// Create or update position
	now := time.Now().Format(time.RFC3339)

	position := portfolio.Position{
		Symbol:         symbol,
		Quantity:       balance,
		AvgPrice:       1.0,
		CurrentPrice:   1.0,
		Currency:       currency,
		CurrencyRate:   1.0,     // TODO: Handle currency conversion rates properly
		MarketValueEUR: balance, // Simplified - assumes EUR or 1:1 rate
		LastUpdated:    now,
	}

	// Check if position exists to set FirstBoughtAt appropriately
	existing, err := m.positionRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to check existing position: %w", err)
	}

	if existing != nil && existing.FirstBoughtAt != "" {
		position.FirstBoughtAt = existing.FirstBoughtAt
	} else {
		position.FirstBoughtAt = now
	}

	err = m.positionRepo.Upsert(position)
	if err != nil {
		return fmt.Errorf("failed to upsert cash position: %w", err)
	}

	m.log.Info().
		Str("symbol", symbol).
		Str("currency", currency).
		Float64("balance", balance).
		Msg("Updated cash position")

	return nil
}

// ensureCashSecurityLocked is the locked version of EnsureCashSecurity
// Must be called with m.mu held
func (m *CashSecurityManager) ensureCashSecurityLocked(currency string) error {
	symbol := cash_utils.MakeCashSymbol(currency)

	// Check if security already exists
	existing, err := m.securityRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to check if cash security exists: %w", err)
	}

	if existing != nil {
		return nil
	}

	// Create new cash security
	security := universe.Security{
		Symbol:             symbol,
		Name:               cash_utils.GetCashSecurityName(currency),
		ProductType:        string(universe.ProductTypeCash),
		Currency:           currency,
		Active:             true,
		AllowBuy:           false,
		AllowSell:          false,
		PriorityMultiplier: 1.0,
		MinLot:             1,
		LastSynced:         time.Now().Format(time.RFC3339),
	}

	err = m.securityRepo.Create(security)
	if err != nil {
		return fmt.Errorf("failed to create cash security: %w", err)
	}

	m.log.Info().
		Str("symbol", symbol).
		Str("currency", currency).
		Msg("Created cash security")

	return nil
}

// deleteCashPositionLocked deletes a cash position
// Must be called with m.mu held
func (m *CashSecurityManager) deleteCashPositionLocked(symbol string, currency string, balance float64) error {
	// Check if position exists
	existing, err := m.positionRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to check existing position: %w", err)
	}

	if existing == nil {
		// Position doesn't exist, nothing to delete
		m.log.Debug().
			Str("symbol", symbol).
			Float64("balance", balance).
			Msg("Cash position doesn't exist, nothing to delete")
		return nil
	}

	// Delete the position
	err = m.positionRepo.Delete(symbol)
	if err != nil {
		return fmt.Errorf("failed to delete cash position: %w", err)
	}

	m.log.Info().
		Str("symbol", symbol).
		Str("currency", currency).
		Float64("balance", balance).
		Msg("Deleted cash position (zero balance)")

	return nil
}

// GetCashBalance returns the cash balance for the given currency
// Returns 0 if no position exists (not an error)
func (m *CashSecurityManager) GetCashBalance(currency string) (float64, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	symbol := cash_utils.MakeCashSymbol(currency)

	position, err := m.positionRepo.GetBySymbol(symbol)
	if err != nil {
		return 0, fmt.Errorf("failed to get cash position: %w", err)
	}

	if position == nil {
		return 0, nil // No position = zero balance
	}

	return position.Quantity, nil
}

// GetAllCashBalances returns all cash balances
// Returns map of currency -> balance
func (m *CashSecurityManager) GetAllCashBalances() (map[string]float64, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	// Get all positions
	allPositions, err := m.positionRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get all positions: %w", err)
	}

	balances := make(map[string]float64)

	for _, pos := range allPositions {
		// Check if this is a cash position
		if !cash_utils.IsCashSymbol(pos.Symbol) {
			continue
		}

		currency, err := cash_utils.ParseCashSymbol(pos.Symbol)
		if err != nil {
			m.log.Warn().
				Err(err).
				Str("symbol", pos.Symbol).
				Msg("Failed to parse cash symbol, skipping")
			continue
		}

		balances[currency] = pos.Quantity
	}

	return balances, nil
}

// GetTotalByCurrency returns the total cash balance for a currency
// This sums up cash positions for the same currency
func (m *CashSecurityManager) GetTotalByCurrency(currency string) (float64, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	// Get all positions
	allPositions, err := m.positionRepo.GetAll()
	if err != nil {
		return 0, fmt.Errorf("failed to get all positions: %w", err)
	}

	total := 0.0

	for _, pos := range allPositions {
		// Check if this is a cash position
		if !cash_utils.IsCashSymbol(pos.Symbol) {
			continue
		}

		posCurrency, err := cash_utils.ParseCashSymbol(pos.Symbol)
		if err != nil {
			m.log.Warn().
				Err(err).
				Str("symbol", pos.Symbol).
				Msg("Failed to parse cash symbol, skipping")
			continue
		}

		if posCurrency == currency {
			total += pos.Quantity
		}
	}

	return total, nil
}

// GetAllCashPositions returns all cash positions
// Returns a map of symbol -> position
func (m *CashSecurityManager) GetAllCashPositions() (map[string]portfolio.Position, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	allPositions, err := m.positionRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get all positions: %w", err)
	}

	cashPositions := make(map[string]portfolio.Position)

	for _, pos := range allPositions {
		if cash_utils.IsCashSymbol(pos.Symbol) {
			cashPositions[pos.Symbol] = pos
		}
	}

	return cashPositions, nil
}

// GetAllCashSymbols returns all cash position symbols
// This is a lighter-weight alternative to GetAllCashPositions when you only need symbols
func (m *CashSecurityManager) GetAllCashSymbols() ([]string, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	allPositions, err := m.positionRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get all positions: %w", err)
	}

	var symbols []string
	for _, pos := range allPositions {
		if cash_utils.IsCashSymbol(pos.Symbol) {
			symbols = append(symbols, pos.Symbol)
		}
	}

	return symbols, nil
}

// AdjustCashBalance adjusts a cash balance by a delta (can be positive or negative)
// This is useful for trade settlements, dividends, etc.
func (m *CashSecurityManager) AdjustCashBalance(currency string, delta float64) (float64, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	// Get current balance
	current, err := m.getCashBalanceLocked(currency)
	if err != nil {
		return 0, fmt.Errorf("failed to get current balance: %w", err)
	}

	newBalance := current + delta

	// Use the locked version of UpdateCashPosition
	err = m.updateCashPositionLocked(currency, newBalance)
	if err != nil {
		return 0, fmt.Errorf("failed to update cash position: %w", err)
	}

	return newBalance, nil
}

// getCashBalanceLocked is the locked version of GetCashBalance
// Must be called with m.mu held (read or write lock)
func (m *CashSecurityManager) getCashBalanceLocked(currency string) (float64, error) {
	symbol := cash_utils.MakeCashSymbol(currency)

	position, err := m.positionRepo.GetBySymbol(symbol)
	if err != nil {
		return 0, fmt.Errorf("failed to get cash position: %w", err)
	}

	if position == nil {
		return 0, nil
	}

	return position.Quantity, nil
}

// updateCashPositionLocked is the locked version of UpdateCashPosition
// Must be called with m.mu held (write lock)
func (m *CashSecurityManager) updateCashPositionLocked(currency string, balance float64) error {
	symbol := cash_utils.MakeCashSymbol(currency)

	// If balance is zero or negative, delete the position
	if balance <= 0 {
		return m.deleteCashPositionLocked(symbol, currency, balance)
	}

	// Ensure the cash security exists
	if err := m.ensureCashSecurityLocked(currency); err != nil {
		return fmt.Errorf("failed to ensure cash security: %w", err)
	}

	// Create or update position
	now := time.Now().Format(time.RFC3339)

	position := portfolio.Position{
		Symbol:         symbol,
		Quantity:       balance,
		AvgPrice:       1.0,
		CurrentPrice:   1.0,
		Currency:       currency,
		CurrencyRate:   1.0,
		MarketValueEUR: balance,
		LastUpdated:    now,
	}

	// Check if position exists to set FirstBoughtAt
	existing, err := m.positionRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to check existing position: %w", err)
	}

	if existing != nil && existing.FirstBoughtAt != "" {
		position.FirstBoughtAt = existing.FirstBoughtAt
	} else {
		position.FirstBoughtAt = now
	}

	err = m.positionRepo.Upsert(position)
	if err != nil {
		return fmt.Errorf("failed to upsert cash position: %w", err)
	}

	return nil
}
