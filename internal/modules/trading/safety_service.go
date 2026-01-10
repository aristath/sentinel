package trading

import (
	"fmt"
	"time"

	"github.com/aristath/sentinel/internal/modules/market_hours"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/settings"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// TradeSafetyService validates trades before execution
// Faithful translation from Python: app/modules/trading/services/trade_safety_service.py
type TradeSafetyService struct {
	tradeRepo          *TradeRepository
	positionRepo       *portfolio.PositionRepository
	securityRepo       *universe.SecurityRepository
	settingsService    *settings.Service
	marketHoursService *market_hours.MarketHoursService
	log                zerolog.Logger
}

// NewTradeSafetyService creates a new trade safety service
func NewTradeSafetyService(
	tradeRepo *TradeRepository,
	positionRepo *portfolio.PositionRepository,
	securityRepo *universe.SecurityRepository,
	settingsService *settings.Service,
	marketHoursService *market_hours.MarketHoursService,
	log zerolog.Logger,
) *TradeSafetyService {
	return &TradeSafetyService{
		tradeRepo:          tradeRepo,
		positionRepo:       positionRepo,
		securityRepo:       securityRepo,
		settingsService:    settingsService,
		marketHoursService: marketHoursService,
		log:                log.With().Str("service", "trade_safety").Logger(),
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

	// Layer 0: Trading mode check (CRITICAL: block ALL trades in research mode)
	if err := s.checkTradingMode(); err != nil {
		return err
	}

	// Layer 7: Security lookup (validate security exists)
	if err := s.validateSecurity(symbol); err != nil {
		return err
	}

	// Layer 1: Market hours check (if required for this trade)
	if err := s.checkMarketHours(symbol, side); err != nil {
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

// checkTradingMode validates that trading mode is "live" (not "research")
// Layer 0: Trading Mode Check (CRITICAL - must be first)
// HARD FAIL-SAFE: Block ALL trades in research mode
func (s *TradeSafetyService) checkTradingMode() error {
	// Trading mode check requires settings service
	if s.settingsService == nil {
		s.log.Warn().Msg("Settings service not available - blocking trade for safety")
		return fmt.Errorf("trading mode validation failed: settings service not available")
	}

	// Get trading mode from settings (default: "research")
	tradingMode := "research" // Safe default - block trades unless explicitly in live mode
	if val, err := s.settingsService.Get("trading_mode"); err == nil {
		if mode, ok := val.(string); ok {
			tradingMode = mode
		}
	}

	// Block ALL trades in research mode
	if tradingMode != "live" {
		s.log.Warn().
			Str("trading_mode", tradingMode).
			Msg("Trade blocked: system is in research mode")
		return fmt.Errorf("trading blocked: system is in '%s' mode (must be 'live' to execute trades)", tradingMode)
	}

	return nil
}

// validateSecurity validates that security exists
// Layer 7: Security Lookup (ISIN Validation)
func (s *TradeSafetyService) validateSecurity(symbol string) error {
	// HARD fail-safe: Security validation requires repository
	if s.securityRepo == nil {
		return fmt.Errorf("security repository not available")
	}

	security, err := s.securityRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to lookup security: %w", err)
	}

	if security == nil {
		return fmt.Errorf("security not found: %s", symbol)
	}

	return nil
}

// checkMarketHours validates that the stock's market is currently open (if required for this trade)
// Layer 1: Market Hours Check
// SOFT FAIL-SAFE: Market hours is advisory (broker allows off-hours trading except Asian markets)
// If validation unavailable, log warning and allow trade attempt. Broker will reject if truly closed.
func (s *TradeSafetyService) checkMarketHours(symbol string, side string) error {
	if s.marketHoursService == nil {
		// Market hours service not available - SOFT fail-safe (warn + allow)
		s.log.Warn().Msg("Market hours service unavailable - allowing trade attempt (broker will reject if market closed)")
		return nil
	}

	security, err := s.securityRepo.GetBySymbol(symbol)
	if err != nil {
		// SOFT fail-safe for market hours check
		s.log.Warn().Err(err).Str("symbol", symbol).Msg("Failed to lookup security for market hours check - allowing trade attempt")
		return nil
	}

	if security == nil {
		// SOFT fail-safe for market hours check
		s.log.Warn().Str("symbol", symbol).Msg("Security not found for market hours check - allowing trade attempt")
		return nil
	}

	exchange := security.FullExchangeName
	if exchange == "" {
		// SOFT fail-safe for market hours check
		s.log.Warn().Str("symbol", symbol).Msg("Security has no exchange set - allowing trade attempt")
		return nil
	}

	// Check if market hours validation is required for this trade
	if !s.marketHoursService.ShouldCheckMarketHours(exchange, side) {
		// Market hours check not required (e.g., BUY order on flexible hours market)
		return nil
	}

	// Market hours check IS required (SELL orders or BUY on strict markets)
	if !s.marketHoursService.IsMarketOpen(exchange, time.Now()) {
		s.log.Info().
			Str("symbol", symbol).
			Str("exchange", exchange).
			Msg("Market closed, blocking trade")
		return fmt.Errorf("market closed for %s", exchange)
	}

	return nil
}

// checkBuyCooldown validates buy cooldown period
// Layer 2: Buy Cooldown Check
// Faithful translation from Python: async def check_cooldown()
func (s *TradeSafetyService) checkBuyCooldown(symbol string, side string) error {
	// Only applies to BUY orders
	if side != "BUY" {
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

	// Look up security to get ISIN (Symbol is at boundary, use ISIN internally)
	security, err := s.securityRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to lookup security: %w", err) // Fail safe
	}
	if security.ISIN == "" {
		// No ISIN available, can't check cooldown
		s.log.Warn().Str("symbol", symbol).Msg("Security missing ISIN, skipping cooldown check")
		return nil
	}

	// Check if ISIN was bought recently (using ISIN internally)
	recentlyBought, err := s.tradeRepo.GetRecentlyBoughtISINs(int(cooldownDays))
	if err != nil {
		return fmt.Errorf("failed to check cooldown: %w", err) // Fail safe
	}

	// Check if ISIN is in the recently bought map
	if recentlyBought[security.ISIN] {
		return fmt.Errorf("cannot buy %s: cooldown period active (bought within %d days)", symbol, int(cooldownDays))
	}

	return nil
}

// checkPendingOrders validates no pending orders exist
// Layer 3: Pending Orders Check
// HARD FAIL-SAFE: Block trades if validation fails (prevents duplicate orders)
// Faithful translation from Python: async def check_pending_orders()
func (s *TradeSafetyService) checkPendingOrders(symbol string, side string) error {
	// For SELL orders: Check database for recent orders (last 2 hours)
	if side == "SELL" {
		// HARD fail-safe: Trade repository required for pending order check
		if s.tradeRepo == nil {
			return fmt.Errorf("trade repository not available")
		}

		hasRecent, err := s.tradeRepo.HasRecentSellOrder(symbol, 2.0)
		if err != nil {
			// HARD fail-safe - block trade if validation unavailable
			s.log.Error().Err(err).Msg("Failed to check recent sell orders - blocking trade for safety")
			return fmt.Errorf("pending orders validation failed - blocking trade for safety: %w", err)
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
// HARD FAIL-SAFE: Block trades if validation fails (prevents premature selling)
// Faithful translation from Python: async def check_minimum_hold_time()
func (s *TradeSafetyService) checkMinimumHoldTime(symbol string, side string) error {
	// Only applies to SELL orders
	if side != "SELL" {
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
		// HARD fail-safe - block sell if validation unavailable
		s.log.Error().Err(err).Msg("Failed to get last transaction date - blocking sell for safety")
		return fmt.Errorf("last transaction date lookup failed - blocking sell for safety: %w", err)
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
			// HARD fail-safe - block sell if date parsing fails
			s.log.Error().Err(err).Msg("Failed to parse last transaction date - blocking sell for safety")
			return fmt.Errorf("last transaction date parsing failed - blocking sell for safety: %w", err)
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
	if side != "SELL" {
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
