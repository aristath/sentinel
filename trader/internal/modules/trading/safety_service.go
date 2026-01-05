package trading

import (
	"fmt"
	"strings"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/settings"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/rs/zerolog"
)

// TradeSafetyService validates trades before execution
// Faithful translation from Python: app/modules/trading/services/trade_safety_service.py
type TradeSafetyService struct {
	tradeRepo       *TradeRepository
	positionRepo    *portfolio.PositionRepository
	securityRepo    *universe.SecurityRepository
	settingsService *settings.Service
	log             zerolog.Logger
}

// NewTradeSafetyService creates a new trade safety service
func NewTradeSafetyService(
	tradeRepo *TradeRepository,
	positionRepo *portfolio.PositionRepository,
	securityRepo *universe.SecurityRepository,
	settingsService *settings.Service,
	log zerolog.Logger,
) *TradeSafetyService {
	return &TradeSafetyService{
		tradeRepo:       tradeRepo,
		positionRepo:    positionRepo,
		securityRepo:    securityRepo,
		settingsService: settingsService,
		log:             log.With().Str("service", "trade_safety").Logger(),
	}
}

// ValidateTrade runs all validation layers and returns error if any check fails
// Faithful translation from Python: async def validate_trade()
func (s *TradeSafetyService) ValidateTrade(
	symbol string,
	side string,
	quantity float64,
) error {
	s.log.Info().
		Str("symbol", symbol).
		Str("side", side).
		Float64("quantity", quantity).
		Msg("Validating trade")

	// Layer 7: Security lookup (validate security exists)
	if err := s.validateSecurity(symbol); err != nil {
		return err
	}

	// Layer 2: Buy cooldown check
	if err := s.checkBuyCooldown(symbol, side); err != nil {
		return err
	}

	// Layer 3: Pending orders check
	if err := s.checkPendingOrders(symbol, side); err != nil {
		return err
	}

	// Layer 4: Minimum hold time check (SELL only)
	if err := s.checkMinimumHoldTime(symbol, side); err != nil {
		return err
	}

	// Layer 5: Position validation (SELL only)
	if err := s.validateSellPosition(symbol, quantity, side); err != nil {
		return err
	}

	s.log.Info().Str("symbol", symbol).Msg("Trade validation passed")
	return nil
}

// validateSecurity validates that security exists
// Layer 7: Security Lookup (ISIN Validation)
func (s *TradeSafetyService) validateSecurity(symbol string) error {
	security, err := s.securityRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to lookup security: %w", err)
	}

	if security == nil {
		return fmt.Errorf("security not found: %s", symbol)
	}

	return nil
}

// checkMarketHours removed - market hours functionality removed

// checkBuyCooldown validates buy cooldown period
// Layer 2: Buy Cooldown Check
// Faithful translation from Python: async def check_cooldown()
func (s *TradeSafetyService) checkBuyCooldown(symbol string, side string) error {
	// Only applies to BUY orders
	if strings.ToUpper(side) != "BUY" {
		return nil
	}

	// Get cooldown period from settings (default 30 days)
	cooldownDays := 30.0
	if s.settingsService != nil {
		if val, err := s.settingsService.Get("buy_cooldown_days"); err == nil {
			if days, ok := val.(float64); ok {
				cooldownDays = days
			}
		}
	}

	// Check if symbol was bought recently
	recentlyBought, err := s.tradeRepo.GetRecentlyBoughtSymbols(int(cooldownDays))
	if err != nil {
		return fmt.Errorf("failed to check cooldown: %w", err) // Fail safe
	}

	// Check if symbol is in the recently bought map
	if recentlyBought[strings.ToUpper(symbol)] {
		return fmt.Errorf("cannot buy %s: cooldown period active (bought within %d days)", symbol, int(cooldownDays))
	}

	return nil
}

// checkPendingOrders validates no pending orders exist
// Layer 3: Pending Orders Check
// Faithful translation from Python: async def check_pending_orders()
func (s *TradeSafetyService) checkPendingOrders(symbol string, side string) error {
	// For SELL orders: Check database for recent orders (last 2 hours)
	if strings.ToUpper(side) == "SELL" {
		hasRecent, err := s.tradeRepo.HasRecentSellOrder(symbol, 2.0)
		if err != nil {
			s.log.Warn().Err(err).Msg("Failed to check recent sell orders - allowing trade")
			return nil // Fail open
		}

		if hasRecent {
			return fmt.Errorf("recent SELL order exists for %s (within 2 hours)", symbol)
		}
	}

	// Note: Checking broker API for pending orders is not implemented here
	// as it requires TradernetClient integration which would create circular dependency
	// The database check above catches most cases

	return nil
}

// checkMinimumHoldTime validates minimum hold period before selling
// Layer 4: Minimum Hold Time Check
// Faithful translation from Python: async def check_minimum_hold_time()
func (s *TradeSafetyService) checkMinimumHoldTime(symbol string, side string) error {
	// Only applies to SELL orders
	if strings.ToUpper(side) != "SELL" {
		return nil
	}

	// Get minimum hold days from settings (default 90)
	minHoldDays := 90.0
	if s.settingsService != nil {
		if val, err := s.settingsService.Get("min_hold_days"); err == nil {
			if days, ok := val.(float64); ok {
				minHoldDays = days
			}
		}
	}

	// Get last transaction date
	lastTransactionDateStr, err := s.tradeRepo.GetLastTransactionDate(symbol)
	if err != nil {
		s.log.Warn().Err(err).Msg("Failed to get last transaction date - allowing sell")
		return nil // Fail open
	}

	if lastTransactionDateStr == nil {
		return nil // No transaction - allow
	}

	// Parse the date string
	lastTransactionDate, err := time.Parse(time.RFC3339, *lastTransactionDateStr)
	if err != nil {
		// Try alternative format
		lastTransactionDate, err = time.Parse("2006-01-02 15:04:05", *lastTransactionDateStr)
		if err != nil {
			s.log.Warn().Err(err).Msg("Failed to parse last transaction date - allowing sell")
			return nil // Fail open
		}
	}

	// Calculate days held
	daysHeld := time.Since(lastTransactionDate).Hours() / 24
	if daysHeld < minHoldDays {
		return fmt.Errorf("cannot sell %s: last transaction %.0f days ago (minimum %.0f days required)",
			symbol, daysHeld, minHoldDays)
	}

	return nil
}

// validateSellPosition validates sufficient position for sell
// Layer 5: Position Quantity Validation
// Faithful translation from Python: async def validate_sell_position()
func (s *TradeSafetyService) validateSellPosition(symbol string, quantity float64, side string) error {
	// Only applies to SELL orders
	if strings.ToUpper(side) != "SELL" {
		return nil
	}

	if s.positionRepo == nil {
		return nil // No position repo available - allow
	}

	// Get current position
	position, err := s.positionRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to get position: %w", err) // Fail safe
	}

	if position == nil {
		return fmt.Errorf("no position found for %s", symbol)
	}

	// Verify quantity doesn't exceed position
	if quantity > position.Quantity {
		return fmt.Errorf("SELL quantity (%.2f) exceeds position (%.2f)", quantity, position.Quantity)
	}

	return nil
}
