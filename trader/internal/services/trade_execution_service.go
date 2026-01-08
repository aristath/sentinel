// Package services provides core business services shared across multiple modules.
//
// This package contains TradeExecutionService which orchestrates trade execution
// across multiple modules (portfolio, trading, cash flows).
//
// See services/README.md for architecture documentation and usage patterns.
package services

import (
	"fmt"
	"time"

	"github.com/aristath/sentinel/internal/clients/tradernet"
	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/events"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/trading"
	"github.com/rs/zerolog"
)

// Note: CashManagerInterface, CurrencyExchangeServiceInterface, and TradernetClientInterface
// have been moved to domain/interfaces.go. Use domain.CashManager, domain.CurrencyExchangeServiceInterface,
// and domain.TradernetClientInterface instead.

// TradeRepositoryInterface defines the interface for trade persistence
type TradeRepositoryInterface interface {
	Create(trade trading.Trade) error
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
// Cash balance validation: IMPLEMENTED (see validateBuyCashBalance)
//
// Faithful translation from Python: app/modules/trading/services/trade_execution_service.py
type TradeExecutionService struct {
	tradernetClient domain.TradernetClientInterface
	tradeRepo       TradeRepositoryInterface
	positionRepo    *portfolio.PositionRepository
	cashManager     domain.CashManager
	exchangeService domain.CurrencyExchangeServiceInterface
	eventManager    *events.Manager
	log             zerolog.Logger
}

// ExecuteResult represents the result of executing a trade
type ExecuteResult struct {
	Symbol string  `json:"symbol"`
	Status string  `json:"status"` // "success", "blocked", "error"
	Error  *string `json:"error,omitempty"`
}

// NewTradeExecutionService creates a new trade execution service
func NewTradeExecutionService(
	tradernetClient domain.TradernetClientInterface,
	tradeRepo TradeRepositoryInterface,
	positionRepo *portfolio.PositionRepository,
	cashManager domain.CashManager,
	exchangeService domain.CurrencyExchangeServiceInterface,
	eventManager *events.Manager,
	log zerolog.Logger,
) *TradeExecutionService {
	return &TradeExecutionService{
		tradernetClient: tradernetClient,
		tradeRepo:       tradeRepo,
		positionRepo:    positionRepo,
		cashManager:     cashManager,
		exchangeService: exchangeService,
		eventManager:    eventManager,
		log:             log.With().Str("service", "trade_execution").Logger(),
	}
}

// ExecuteTrades executes a list of trade recommendations
//
// Simplified version for emergency rebalancing. Bypasses most validations.
// Returns list of execution results.
func (s *TradeExecutionService) ExecuteTrades(recommendations []TradeRecommendation) []ExecuteResult {
	results := make([]ExecuteResult, 0, len(recommendations))

	if !s.tradernetClient.IsConnected() {
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

	// Pre-trade validation for BUY orders
	if rec.Side == "BUY" {
		if validationErr := s.validateBuyCashBalance(rec); validationErr != nil {
			s.log.Warn().
				Str("symbol", rec.Symbol).
				Str("error", *validationErr.Error).
				Msg("Trade blocked by cash validation")
			return *validationErr
		}
	}

	// Place order via Tradernet
	orderResult, err := s.tradernetClient.PlaceOrder(
		rec.Symbol,
		rec.Side, // "BUY" or "SELL"
		rec.Quantity,
	)

	if err != nil {
		s.log.Error().
			Err(err).
			Str("symbol", rec.Symbol).
			Msg("Failed to place order")
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
func (s *TradeExecutionService) recordTrade(orderResult *tradernet.OrderResult, rec TradeRecommendation) error {
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
	const fixedCommissionEUR = 2.0
	const variableCommissionRate = 0.002 // 0.2%

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

// validateBuyCashBalance validates cash balance before executing BUY order.
//
// Two-level validation:
// 1. Block if balance is already negative (status: "blocked")
// 2. Block if balance < (trade_value + commission) (status: "blocked")
//
// Faithful translation from Python:
// app/modules/trading/services/trade_execution_service.py:152-217
func (s *TradeExecutionService) validateBuyCashBalance(rec TradeRecommendation) *ExecuteResult {
	// Get current balance for the trade currency
	// Use CashSecurityManager directly
	if s.cashManager == nil {
		s.log.Warn().Msg("CashSecurityManager not available, skipping cash validation")
		return nil // Allow trade to proceed if cash manager unavailable
	}

	balance, err := s.cashManager.GetCashBalance(rec.Currency)
	if err != nil {
		s.log.Error().
			Err(err).
			Str("currency", rec.Currency).
			Msg("Failed to get cash balance")
		errMsg := fmt.Sprintf("Failed to get cash balance: %v", err)
		return &ExecuteResult{
			Symbol: rec.Symbol,
			Status: "error",
			Error:  &errMsg,
		}
	}

	// Check 1: Block if balance is already negative
	if balance < 0 {
		s.log.Warn().
			Str("symbol", rec.Symbol).
			Str("currency", rec.Currency).
			Float64("balance", balance).
			Msg("Blocking BUY: negative balance")
		errMsg := fmt.Sprintf("Negative %s balance (%.2f %s)", rec.Currency, balance, rec.Currency)
		return &ExecuteResult{
			Symbol: rec.Symbol,
			Status: "blocked",
			Error:  &errMsg,
		}
	}

	// Calculate trade value
	tradeValue := rec.Quantity * rec.EstimatedPrice

	// Calculate commission
	commission, err := s.calculateCommission(tradeValue, rec.Currency)
	if err != nil {
		s.log.Warn().
			Err(err).
			Str("symbol", rec.Symbol).
			Msg("Failed to calculate commission, proceeding without commission check")
		commission = 0
	}

	// Calculate total required (trade value + commission)
	required := tradeValue + commission

	// Check 2: Block if insufficient balance
	if balance < required {
		s.log.Warn().
			Str("symbol", rec.Symbol).
			Str("currency", rec.Currency).
			Float64("need", required).
			Float64("have", balance).
			Float64("trade_value", tradeValue).
			Float64("commission", commission).
			Msgf("Skipping %s: insufficient %s balance (need %.2f %s: %.2f trade + %.2f commission, have %.2f)",
				rec.Symbol, rec.Currency, required, rec.Currency, tradeValue, commission, balance)
		errMsg := fmt.Sprintf("Insufficient %s balance (need %.2f, have %.2f)", rec.Currency, required, balance)
		return &ExecuteResult{
			Symbol: rec.Symbol,
			Status: "blocked",
			Error:  &errMsg,
		}
	}

	// All checks passed
	return nil
}
