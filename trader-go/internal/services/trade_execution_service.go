package services

import (
	"fmt"
	"time"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/trading"
	"github.com/rs/zerolog"
)

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
// - Currency balance validation
// - Duplicate order prevention
//
// Faithful translation from Python: app/modules/trading/services/trade_execution_service.py
type TradeExecutionService struct {
	tradernetClient *tradernet.Client
	tradeRepo       *trading.TradeRepository
	positionRepo    *portfolio.PositionRepository
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
	tradernetClient *tradernet.Client,
	tradeRepo *trading.TradeRepository,
	positionRepo *portfolio.PositionRepository,
	log zerolog.Logger,
) *TradeExecutionService {
	return &TradeExecutionService{
		tradernetClient: tradernetClient,
		tradeRepo:       tradeRepo,
		positionRepo:    positionRepo,
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
		BucketID:   "core", // Default to core bucket
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
