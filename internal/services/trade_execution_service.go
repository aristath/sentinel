// Package services provides core business services shared across multiple modules.
//
// This package contains TradeExecutionService which orchestrates trade execution
// across multiple modules (portfolio, trading, cash flows).
//
// See services/README.md for architecture documentation and usage patterns.
package services

import (
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/aristath/sentinel/internal/clients/yahoo"
	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/events"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/trading"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// Note: CashManagerInterface, CurrencyExchangeServiceInterface, and TradernetClientInterface
// have been moved to domain/interfaces.go. Use domain.CashManager, domain.CurrencyExchangeServiceInterface,
// and domain.BrokerClient instead.

// TradeRepositoryInterface defines the interface for trade persistence
type TradeRepositoryInterface interface {
	Create(trade trading.Trade) error
	CreatePendingRetry(retry trading.PendingRetry) error
	GetPendingRetries() ([]trading.PendingRetry, error)
	UpdateRetryStatus(id int64, status string) error
	IncrementRetryAttempt(id int64) error
}

// OrderBookServiceInterface defines the interface for order book analysis
type OrderBookServiceInterface interface {
	// IsEnabled checks if order book analysis is enabled
	IsEnabled() bool
	// CalculateOptimalLimit calculates optimal limit price using order book + Yahoo validation
	CalculateOptimalLimit(symbol, side string, buffer float64) (float64, error)
	// ValidateLiquidity checks if sufficient liquidity exists for the trade
	ValidateLiquidity(symbol, side string, quantity float64) error
}

// PlannerConfigRepoInterface defines the interface for planner configuration
type PlannerConfigRepoInterface interface {
	GetDefaultConfig() (*planningdomain.PlannerConfiguration, error)
}

// TradeRecommendation represents a simplified trade recommendation for execution
// Minimal implementation for emergency rebalancing
type TradeRecommendation struct {
	Symbol         string
	Side           string // "BUY" or "SELL"
	Quantity       float64
	EstimatedPrice float64
	Currency       string
	Reason         string
}

// TradeExecutionService executes trade recommendations
//
// This is a simplified version focused on emergency rebalancing.
// TODO: Full 7-layer validation from Python can be added later as P2 work:
// - Trade frequency limits
// - Market hours checking
// - Buy cooldown
// - Minimum hold time
// - Pending order detection
// - Duplicate order prevention
//
// Cash balance validation: IMPLEMENTED (see executeSingleTrade - uses CurrencyExchangeService.EnsureBalance)
//
// Faithful translation from Python: app/modules/trading/services/trade_execution_service.py
type TradeExecutionService struct {
	brokerClient      domain.BrokerClient
	tradeRepo         TradeRepositoryInterface
	positionRepo      *portfolio.PositionRepository
	cashManager       domain.CashManager
	exchangeService   domain.CurrencyExchangeServiceInterface
	eventManager      *events.Manager
	settingsService   SettingsServiceInterface      // For configuration (fees, price age, etc.)
	plannerConfigRepo PlannerConfigRepoInterface    // For transaction costs from planner config
	orderBookService  OrderBookServiceInterface     // For order book analysis (liquidity validation, optimal limit pricing)
	yahooClient       yahoo.FullClientInterface     // For fetching fresh prices
	historyDB         *sql.DB                       // For storing updated prices
	securityRepo      *universe.SecurityRepository  // For ISIN lookup
	log               zerolog.Logger
}

// ExecuteResult represents the result of executing a trade
type ExecuteResult struct {
	Symbol string  `json:"symbol"`
	Status string  `json:"status"` // "success", "blocked", "error"
	Error  *string `json:"error,omitempty"`
}

// NewTradeExecutionService creates a new trade execution service
func NewTradeExecutionService(
	brokerClient domain.BrokerClient,
	tradeRepo TradeRepositoryInterface,
	positionRepo *portfolio.PositionRepository,
	cashManager domain.CashManager,
	exchangeService domain.CurrencyExchangeServiceInterface,
	eventManager *events.Manager,
	settingsService SettingsServiceInterface,
	plannerConfigRepo PlannerConfigRepoInterface,
	orderBookService OrderBookServiceInterface,
	yahooClient yahoo.FullClientInterface,
	historyDB *sql.DB,
	securityRepo *universe.SecurityRepository,
	log zerolog.Logger,
) *TradeExecutionService {
	return &TradeExecutionService{
		brokerClient:      brokerClient,
		tradeRepo:         tradeRepo,
		positionRepo:      positionRepo,
		cashManager:       cashManager,
		exchangeService:   exchangeService,
		eventManager:      eventManager,
		settingsService:   settingsService,
		plannerConfigRepo: plannerConfigRepo,
		orderBookService:  orderBookService,
		yahooClient:       yahooClient,
		historyDB:         historyDB,
		securityRepo:      securityRepo,
		log:               log.With().Str("service", "trade_execution").Logger(),
	}
}

// ExecuteTrades executes a list of trade recommendations
//
// Simplified version for emergency rebalancing. Bypasses most validations.
// Returns list of execution results.
func (s *TradeExecutionService) ExecuteTrades(recommendations []TradeRecommendation) []ExecuteResult {
	results := make([]ExecuteResult, 0, len(recommendations))

	if !s.brokerClient.IsConnected() {
		s.log.Error().Msg("Tradernet not connected")
		// Return error for all trades
		for _, rec := range recommendations {
			errMsg := "Tradernet not connected"
			results = append(results, ExecuteResult{
				Symbol: rec.Symbol,
				Status: "error",
				Error:  &errMsg,
			})
		}
		return results
	}

	for _, rec := range recommendations {
		result := s.executeSingleTrade(rec)
		results = append(results, result)
	}

	return results
}

// executeSingleTrade executes a single trade recommendation
func (s *TradeExecutionService) executeSingleTrade(rec TradeRecommendation) ExecuteResult {
	s.log.Info().
		Str("symbol", rec.Symbol).
		Str("side", rec.Side).
		Float64("quantity", rec.Quantity).
		Float64("estimated_price", rec.EstimatedPrice).
		Str("reason", rec.Reason).
		Msg("Executing trade")

	// Basic input validation - prevent catastrophic errors
	if rec.Symbol == "" {
		errMsg := "Symbol cannot be empty"
		return ExecuteResult{Symbol: rec.Symbol, Status: "error", Error: &errMsg}
	}
	if rec.Quantity <= 0 {
		errMsg := fmt.Sprintf("Invalid quantity: %.4f (must be positive)", rec.Quantity)
		return ExecuteResult{Symbol: rec.Symbol, Status: "error", Error: &errMsg}
	}
	if rec.EstimatedPrice <= 0 {
		errMsg := fmt.Sprintf("Invalid price: %.2f (must be positive)", rec.EstimatedPrice)
		return ExecuteResult{Symbol: rec.Symbol, Status: "error", Error: &errMsg}
	}
	if rec.Side != "BUY" && rec.Side != "SELL" {
		errMsg := fmt.Sprintf("Invalid side: %s (must be BUY or SELL)", rec.Side)
		return ExecuteResult{Symbol: rec.Symbol, Status: "error", Error: &errMsg}
	}

	// Price staleness validation (with auto-refresh if stale)
	if validationErr := s.validatePriceFreshness(rec); validationErr != nil {
		s.log.Warn().
			Str("symbol", rec.Symbol).
			Str("error", *validationErr.Error).
			Msg("Trade blocked by price staleness check")
		return *validationErr
	}

	// Price validation and limit calculation
	limitPrice, err := s.validatePriceAndCalculateLimit(rec)
	if err != nil {
		s.log.Error().
			Err(err).
			Str("symbol", rec.Symbol).
			Msg("Trade blocked by price validation failure")
		errMsg := err.Error()
		return ExecuteResult{
			Symbol: rec.Symbol,
			Status: "blocked",
			Error:  &errMsg,
		}
	}

	// Pre-trade validation for BUY orders - ensure sufficient balance (with auto-conversion if needed)
	if rec.Side == "BUY" {
		// Calculate total needed: trade value + commission + 1% safety margin
		tradeValue := rec.Quantity * rec.EstimatedPrice

		// Calculate commission
		commission, err := s.calculateCommission(tradeValue, rec.Currency)
		if err != nil {
			s.log.Warn().
				Err(err).
				Str("symbol", rec.Symbol).
				Msg("Failed to calculate commission, using 2% buffer")
			commission = tradeValue * 0.02 // Fallback: assume ~2% commission
		}

		// Add 1% safety margin to prevent rounding issues
		totalNeeded := (tradeValue + commission) * 1.01

		s.log.Info().
			Str("symbol", rec.Symbol).
			Str("currency", rec.Currency).
			Float64("trade_value", tradeValue).
			Float64("commission", commission).
			Float64("total_needed", totalNeeded).
			Msg("Ensuring sufficient balance before trade")

		// EnsureBalance handles all currencies (EUR and foreign):
		// 1. Check current balance in rec.Currency
		// 2. If insufficient AND rec.Currency != EUR, convert from EUR automatically
		// 3. If rec.Currency == EUR, just validates we have enough EUR
		// 4. Returns false if insufficient funds in any scenario
		success, err := s.exchangeService.EnsureBalance(rec.Currency, totalNeeded, "EUR")
		if err != nil || !success {
			s.log.Error().
				Err(err).
				Str("symbol", rec.Symbol).
				Str("currency", rec.Currency).
				Float64("needed", totalNeeded).
				Msg("Failed to ensure sufficient currency balance - blocking trade for safety")
			errMsg := fmt.Sprintf("Insufficient funds for trade (need %.2f %s): %v",
				totalNeeded, rec.Currency, err)
			return ExecuteResult{
				Symbol: rec.Symbol,
				Status: "blocked",
				Error:  &errMsg,
			}
		}

		s.log.Info().
			Str("symbol", rec.Symbol).
			Str("currency", rec.Currency).
			Float64("ensured_amount", totalNeeded).
			Msg("Successfully ensured currency balance")
	}

	// Place LIMIT order via Tradernet
	orderResult, err := s.brokerClient.PlaceOrder(
		rec.Symbol,
		rec.Side, // "BUY" or "SELL"
		rec.Quantity,
		limitPrice, // Pass calculated limit price
	)

	if err != nil {
		s.log.Error().
			Err(err).
			Str("symbol", rec.Symbol).
			Msg("Failed to place order")

		// Check if error is market-hours related (should retry after 7 hours)
		errorMsg := err.Error()
		if s.isMarketHoursError(errorMsg) {
			s.log.Info().
				Str("symbol", rec.Symbol).
				Str("error", errorMsg).
				Msg("Market hours error detected - storing for retry in 7 hours")

			// Store for retry
			if retryErr := s.storePendingRetry(rec, errorMsg); retryErr != nil {
				s.log.Error().
					Err(retryErr).
					Str("symbol", rec.Symbol).
					Msg("Failed to store pending retry")
			}
		}

		errMsg := err.Error()
		return ExecuteResult{
			Symbol: rec.Symbol,
			Status: "error",
			Error:  &errMsg,
		}
	}

	// Record trade in database
	if err := s.recordTrade(orderResult, rec); err != nil {
		s.log.Warn().
			Err(err).
			Str("symbol", rec.Symbol).
			Msg("Trade executed but failed to record")
		// Still return success - the trade went through
	} else {
		// Emit TRADE_EXECUTED event
		if s.eventManager != nil {
			s.eventManager.Emit(events.TradeExecuted, "trade_execution", map[string]interface{}{
				"symbol":   orderResult.Symbol,
				"side":     rec.Side,
				"quantity": rec.Quantity,
				"price":    orderResult.Price,
				"order_id": orderResult.OrderID,
				"source":   "emergency_rebalancing",
			})
		}
	}

	s.log.Info().
		Str("symbol", rec.Symbol).
		Str("order_id", orderResult.OrderID).
		Msg("Trade executed successfully")

	return ExecuteResult{
		Symbol: rec.Symbol,
		Status: "success",
		Error:  nil,
	}
}

// recordTrade records a trade in the database
func (s *TradeExecutionService) recordTrade(orderResult *domain.BrokerOrderResult, rec TradeRecommendation) error {
	// Convert side string to TradeSide
	side, err := trading.TradeSideFromString(orderResult.Side)
	if err != nil {
		return fmt.Errorf("invalid trade side: %w", err)
	}

	trade := trading.Trade{
		Symbol:     orderResult.Symbol,
		Side:       side,
		Quantity:   orderResult.Quantity,
		Price:      orderResult.Price,
		Currency:   rec.Currency,
		Source:     "emergency_rebalancing",
		Mode:       "live",
		ExecutedAt: time.Now(),
		OrderID:    orderResult.OrderID,
	}

	if err := s.tradeRepo.Create(trade); err != nil {
		return fmt.Errorf("failed to create trade: %w", err)
	}

	// Position updates will be handled by the regular sync cycle
	// For emergency trades, the critical part is execution and recording
	// TODO: Consider updating position immediately for better consistency

	return nil
}

// calculateCommission calculates total commission in trade currency.
//
// Commission structure:
// - Fixed EUR 2.0 fee (converted to trade currency if needed)
// - Variable 0.2% of trade value
//
// Faithful translation from Python:
// app/modules/trading/services/trade_execution_service.py:42-95
func (s *TradeExecutionService) calculateCommission(
	tradeValue float64,
	tradeCurrency string,
) (float64, error) {
	// Get commission settings from planner configuration (with fallback to defaults)
	fixedCommissionEUR := 2.0       // Default: 2 EUR
	variableCommissionRate := 0.002 // Default: 0.2% as decimal

	if s.plannerConfigRepo != nil {
		// Read transaction costs from planner config
		config, err := s.plannerConfigRepo.GetDefaultConfig()
		if err == nil {
			fixedCommissionEUR = config.TransactionCostFixed
			variableCommissionRate = config.TransactionCostPercent
		} else {
			s.log.Warn().Err(err).Msg("Failed to get planner config for transaction costs, using defaults")
		}
	}

	// Calculate variable commission (percentage of trade value)
	variableCommission := tradeValue * variableCommissionRate

	// Convert fixed EUR commission to trade currency if needed
	var fixedCommission float64
	if tradeCurrency == "EUR" {
		fixedCommission = fixedCommissionEUR
	} else {
		// Get exchange rate to convert EUR to trade currency
		rate, err := s.exchangeService.GetRate("EUR", tradeCurrency)
		if err != nil || rate <= 0 {
			s.log.Warn().
				Err(err).
				Str("currency", tradeCurrency).
				Msg("Failed to convert commission to trade currency, using EUR amount")
			fixedCommission = fixedCommissionEUR
		} else {
			fixedCommission = fixedCommissionEUR * rate
		}
	}

	totalCommission := fixedCommission + variableCommission
	return totalCommission, nil
}

// validatePriceFreshness validates that price data is fresh, attempts auto-refresh if stale.
//
// Three-stage process:
// 1. Check if price is stale (older than max_price_age_hours from settings, default 48h)
// 2. If stale: Attempt to fetch fresh price from Yahoo Finance
// 3. If fetch succeeds: Store in history.db and proceed. If fetch fails: Block trade
//
// Returns *ExecuteResult if validation fails (stale and refresh failed), nil if OK to proceed
func (s *TradeExecutionService) validatePriceFreshness(rec TradeRecommendation) *ExecuteResult {
	// Get max price age from settings (default 48 hours)
	maxAgeHours := 48.0
	if s.settingsService != nil {
		if val, err := s.settingsService.Get("max_price_age_hours"); err == nil {
			if age, ok := val.(float64); ok {
				maxAgeHours = age
			}
		}
	}

	// Skip staleness check if required dependencies unavailable (degrade gracefully)
	if s.securityRepo == nil || s.historyDB == nil {
		s.log.Warn().Msg("Price staleness check skipped: dependencies unavailable")
		return nil
	}

	// Get ISIN for symbol
	security, err := s.securityRepo.GetBySymbol(rec.Symbol)
	if err != nil {
		s.log.Warn().
			Err(err).
			Str("symbol", rec.Symbol).
			Msg("Failed to lookup security for staleness check, allowing trade")
		return nil
	}

	if security == nil || security.ISIN == "" {
		s.log.Warn().
			Str("symbol", rec.Symbol).
			Msg("No ISIN found for symbol, skipping staleness check")
		return nil
	}

	// Create history repository for this ISIN
	historyRepo := portfolio.NewHistoryRepository(security.ISIN, s.historyDB, s.log)

	// Check price staleness
	_, err = historyRepo.GetLatestPriceWithStalenessCheck(maxAgeHours)
	if err == nil {
		// Price is fresh, proceed with trade
		return nil
	}

	// Price is stale, attempt to refresh
	s.log.Warn().
		Err(err).
		Str("symbol", rec.Symbol).
		Str("isin", security.ISIN).
		Msg("Price data is stale, attempting to refresh from Yahoo Finance")

	// Fetch fresh price from Yahoo Finance
	if s.yahooClient == nil {
		s.log.Error().Msg("Yahoo client unavailable, cannot refresh stale price")
		errMsg := "Price data is stale and refresh unavailable (Yahoo client not configured)"
		return &ExecuteResult{
			Symbol: rec.Symbol,
			Status: "blocked",
			Error:  &errMsg,
		}
	}

	// Get current price from Yahoo
	var yahooSymbolPtr *string
	if security.YahooSymbol != "" {
		yahooSymbolPtr = &security.YahooSymbol
	}
	currentPrice, err := s.yahooClient.GetCurrentPrice(rec.Symbol, yahooSymbolPtr, 3)
	if err != nil || currentPrice == nil {
		s.log.Error().
			Err(err).
			Str("symbol", rec.Symbol).
			Msg("Failed to fetch fresh price from Yahoo Finance")
		errMsg := fmt.Sprintf("Price data is stale (older than %.0f hours) and refresh failed", maxAgeHours)
		return &ExecuteResult{
			Symbol: rec.Symbol,
			Status: "blocked",
			Error:  &errMsg,
		}
	}

	// Store fresh price in history.db
	now := time.Now()
	todayStr := now.Format("2006-01-02")

	// Insert or update today's price
	insertQuery := `
		INSERT OR REPLACE INTO daily_prices (isin, date, close, open, high, low, volume)
		VALUES (?, ?, ?, ?, ?, ?, 0)
	`

	dateUnix := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, time.UTC).Unix()
	_, err = s.historyDB.Exec(insertQuery, security.ISIN, dateUnix, *currentPrice, *currentPrice, *currentPrice, *currentPrice)
	if err != nil {
		s.log.Warn().
			Err(err).
			Str("symbol", rec.Symbol).
			Float64("price", *currentPrice).
			Msg("Failed to store refreshed price in history.db, but proceeding with trade")
		// Don't block trade if storage fails - we have the fresh price
	} else {
		s.log.Info().
			Str("symbol", rec.Symbol).
			Str("date", todayStr).
			Float64("price", *currentPrice).
			Msg("Successfully refreshed stale price from Yahoo Finance")
	}

	// Fresh price obtained, allow trade to proceed
	return nil
}

// validatePriceAndCalculateLimit fetches trusted price from Yahoo Finance and calculates limit price.
//
// For BUY orders: limit = yahooPrice × (1 + buffer)  // Allow buying slightly above
// For SELL orders: limit = yahooPrice × (1 - buffer) // Allow selling slightly below
//
// Returns limit price and nil error if successful.
// Returns 0 and error if Yahoo unavailable (blocks trade for safety).
func (s *TradeExecutionService) validatePriceAndCalculateLimit(rec TradeRecommendation) (float64, error) {
	// Get buffer from settings (existing logic)
	buffer := s.getBuffer()

	// Check if order book module available and enabled
	if s.orderBookService != nil && s.orderBookService.IsEnabled() {
		// Use order book module (handles everything internally):
		// - Fetches order book (primary source)
		// - Fetches Yahoo (validation source)
		// - Cross-validates with asymmetric validation (blocks if discrepancy >= 50%)
		// - Calculates limit with buffer
		limitPrice, err := s.orderBookService.CalculateOptimalLimit(rec.Symbol, rec.Side, buffer)
		if err != nil {
			// Order book module failed (liquidity issue or API bug detected)
			// BLOCK trade - return error
			return 0, fmt.Errorf("order book analysis failed: %w", err)
		}

		return limitPrice, nil
	}

	// Fallback to Yahoo-only (existing behavior)
	s.log.Debug().
		Str("symbol", rec.Symbol).
		Msg("Order book analysis disabled or unavailable - using Yahoo-only fallback")
	return s.calculateLegacyLimit(rec, buffer)
}

// getBuffer extracts buffer from settings (existing logic)
func (s *TradeExecutionService) getBuffer() float64 {
	buffer := 0.05 // default 5%
	if s.settingsService != nil {
		if val, err := s.settingsService.Get("limit_order_buffer_percent"); err == nil {
			if bufferVal, ok := val.(float64); ok && bufferVal >= 0.001 && bufferVal <= 0.20 {
				buffer = bufferVal
			}
		}
	}
	return buffer
}

// calculateLegacyLimit is the old Yahoo-only logic (fallback)
func (s *TradeExecutionService) calculateLegacyLimit(rec TradeRecommendation, buffer float64) (float64, error) {
	// Check if Yahoo client is available
	if s.yahooClient == nil {
		return 0, fmt.Errorf("yahoo Finance client unavailable and order book disabled")
	}

	// Get security for Yahoo symbol override
	var yahooSymbolPtr *string
	if s.securityRepo != nil {
		security, err := s.securityRepo.GetBySymbol(rec.Symbol)
		if err == nil && security != nil && security.YahooSymbol != "" {
			yahooSymbolPtr = &security.YahooSymbol
		}
	}

	// Fetch current price from Yahoo Finance (3 retries)
	yahooPrice, err := s.yahooClient.GetCurrentPrice(rec.Symbol, yahooSymbolPtr, 3)
	if err != nil || yahooPrice == nil {
		return 0, fmt.Errorf("failed to fetch Yahoo price for %s: %w", rec.Symbol, err)
	}

	// Validate price is reasonable
	if *yahooPrice <= 0 {
		return 0, fmt.Errorf("invalid Yahoo price for %s: %.2f (must be positive)", rec.Symbol, *yahooPrice)
	}

	// Calculate limit price with buffer
	var limitPrice float64
	if rec.Side == "BUY" {
		limitPrice = *yahooPrice * (1 + buffer)
	} else {
		limitPrice = *yahooPrice * (1 - buffer)
	}

	s.log.Info().
		Str("symbol", rec.Symbol).
		Str("side", rec.Side).
		Float64("yahoo_price", *yahooPrice).
		Float64("limit_price", limitPrice).
		Float64("buffer_pct", buffer*100).
		Msg("Calculated limit price from Yahoo Finance (legacy mode)")

	return limitPrice, nil
}

// isMarketHoursError checks if an error message indicates a market hours issue
func (s *TradeExecutionService) isMarketHoursError(errorMsg string) bool {
	// Common market hours error patterns
	marketHoursPatterns := []string{
		"market closed",
		"market is closed",
		"trading hours",
		"outside trading hours",
		"market not open",
		"exchange closed",
		"trading session closed",
		"after hours",
		"pre-market",
	}

	errorLower := strings.ToLower(errorMsg)
	for _, pattern := range marketHoursPatterns {
		if strings.Contains(errorLower, pattern) {
			return true
		}
	}

	return false
}

// storePendingRetry stores a failed trade for retry (7-hour interval, max 3 attempts)
func (s *TradeExecutionService) storePendingRetry(rec TradeRecommendation, failureReason string) error {
	if s.tradeRepo == nil {
		return fmt.Errorf("trade repository not available")
	}

	retry := trading.PendingRetry{
		Symbol:         rec.Symbol,
		Side:           rec.Side,
		Quantity:       rec.Quantity,
		EstimatedPrice: rec.EstimatedPrice,
		Currency:       rec.Currency,
		Reason:         rec.Reason,
		FailureReason:  failureReason,
		MaxAttempts:    3, // Default max attempts
	}

	return s.tradeRepo.CreatePendingRetry(retry)
}
