package trading

import (
	"fmt"
	"strings"
	"time"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/rs/zerolog"
)

// TradeRepositoryInterface defines the interface for trade persistence
type TradeRepositoryInterface interface {
	Create(trade Trade) error
}

// TradernetClientInterface defines the interface for Tradernet operations
type TradernetClientInterface interface {
	GetExecutedTrades(limit int) ([]tradernet.Trade, error)
	PlaceOrder(symbol, side string, quantity float64) (*tradernet.OrderResult, error)
}

// TradingService handles trade-related business logic
type TradingService struct {
	log             zerolog.Logger
	tradeRepo       TradeRepositoryInterface
	tradernetClient TradernetClientInterface
	safetyService   *TradeSafetyService
}

// NewTradingService creates a new trading service
func NewTradingService(
	tradeRepo TradeRepositoryInterface,
	tradernetClient TradernetClientInterface,
	safetyService *TradeSafetyService,
	log zerolog.Logger,
) *TradingService {
	return &TradingService{
		log:             log.With().Str("service", "trading").Logger(),
		tradeRepo:       tradeRepo,
		tradernetClient: tradernetClient,
		safetyService:   safetyService,
	}
}

// SyncFromTradernet synchronizes trade history from Tradernet microservice
// Returns count of newly synced trades
func (s *TradingService) SyncFromTradernet() error {
	s.log.Info().Msg("Syncing trades from Tradernet")

	// Get recent trades from Tradernet (last 100 trades)
	trades, err := s.tradernetClient.GetExecutedTrades(100)
	if err != nil {
		return fmt.Errorf("failed to get trades from Tradernet: %w", err)
	}

	// Sync trades to database
	syncedCount := 0
	for _, trade := range trades {
		// Parse trade side
		side, err := TradeSideFromString(trade.Side)
		if err != nil {
			s.log.Error().
				Err(err).
				Str("order_id", trade.OrderID).
				Str("side", trade.Side).
				Msg("Invalid trade side")
			continue
		}

		// Parse executed_at timestamp
		executedAt, err := time.Parse(time.RFC3339, trade.ExecutedAt)
		if err != nil {
			s.log.Error().
				Err(err).
				Str("order_id", trade.OrderID).
				Str("executed_at", trade.ExecutedAt).
				Msg("Invalid executed_at timestamp")
			continue
		}

		// Convert tradernet.Trade to trading.Trade domain model
		dbTrade := Trade{
			OrderID:    trade.OrderID,
			Symbol:     trade.Symbol,
			Side:       side,
			Quantity:   trade.Quantity,
			Price:      trade.Price,
			ExecutedAt: executedAt,
			Source:     "tradernet",
			Currency:   "EUR", // Default, should be from trade data
			BucketID:   "",    // Empty for automatic sync
		}

		// Insert trade to database (idempotent via order_id unique constraint)
		if err := s.tradeRepo.Create(dbTrade); err != nil {
			// Skip if already exists (duplicate order_id)
			if strings.Contains(err.Error(), "UNIQUE constraint") {
				continue
			}
			s.log.Error().
				Err(err).
				Str("order_id", trade.OrderID).
				Msg("Failed to insert trade")
			continue
		}

		syncedCount++
	}

	s.log.Info().
		Int("total", len(trades)).
		Int("synced", syncedCount).
		Msg("Trade sync completed")

	return nil
}

// TradeRequest represents a request to execute a trade
type TradeRequest struct {
	Symbol   string
	Side     string
	Quantity int
	Reason   string
}

// TradeResult represents the result of a trade execution attempt
type TradeResult struct {
	Success bool
	OrderID string
	Reason  string // Rejection reason if not successful
}

// ExecuteTrade executes a trade through the Tradernet microservice
// Includes all safety validations before execution
func (s *TradingService) ExecuteTrade(req TradeRequest) (*TradeResult, error) {
	s.log.Info().
		Str("symbol", req.Symbol).
		Str("side", req.Side).
		Int("quantity", req.Quantity).
		Str("reason", req.Reason).
		Msg("Executing trade")

	// Run safety validations if safety service is available
	if s.safetyService != nil {
		if err := s.safetyService.ValidateTrade(req.Symbol, req.Side, float64(req.Quantity)); err != nil {
			s.log.Warn().
				Err(err).
				Str("symbol", req.Symbol).
				Str("side", req.Side).
				Msg("Trade rejected by safety validations")
			return &TradeResult{
				Success: false,
				Reason:  fmt.Sprintf("Safety validation failed: %v", err),
			}, nil // Return nil error - validation failure is not a system error
		}
	} else {
		s.log.Warn().Msg("Safety service not available - executing trade without validations")
	}

	// Execute trade via Tradernet microservice
	orderResult, err := s.tradernetClient.PlaceOrder(req.Symbol, req.Side, float64(req.Quantity))
	if err != nil {
		return &TradeResult{
			Success: false,
			Reason:  fmt.Sprintf("Failed to place order: %v", err),
		}, nil // Return nil error since we handled it in TradeResult
	}

	// Record trade in local database
	side, err := TradeSideFromString(req.Side)
	if err != nil {
		return &TradeResult{
			Success: false,
			Reason:  fmt.Sprintf("Invalid trade side: %v", err),
		}, nil
	}

	trade := Trade{
		OrderID:    orderResult.OrderID,
		Symbol:     orderResult.Symbol,
		Side:       side,
		Quantity:   orderResult.Quantity,
		Price:      orderResult.Price,
		ExecutedAt: time.Now(),
		Source:     "autonomous",
		Currency:   "EUR",
		BucketID:   "",
		Mode:       "live",
	}

	if err := s.tradeRepo.Create(trade); err != nil {
		s.log.Error().
			Err(err).
			Str("order_id", orderResult.OrderID).
			Msg("Failed to record trade in database")
		// Don't fail the execution - trade was placed successfully
	}

	s.log.Info().
		Str("order_id", orderResult.OrderID).
		Str("symbol", orderResult.Symbol).
		Float64("price", orderResult.Price).
		Msg("Trade executed successfully")

	return &TradeResult{
		Success: true,
		OrderID: orderResult.OrderID,
		Reason:  "Trade executed successfully",
	}, nil
}
