package trading

import (
	"fmt"
	"time"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/events"
	"github.com/rs/zerolog"
)

// TradeRepositoryInterface defines the interface for trade persistence
type TradeRepositoryInterface interface {
	// Create inserts a new trade record
	Create(trade Trade) error

	// GetByOrderID retrieves a trade by order ID
	GetByOrderID(orderID string) (*Trade, error)

	// Exists checks if a trade with the given order ID exists
	Exists(orderID string) (bool, error)

	// GetHistory retrieves recent trades with optional limit
	GetHistory(limit int) ([]Trade, error)

	// GetAllInRange retrieves all trades within a date range
	// startDate and endDate are in YYYY-MM-DD format
	GetAllInRange(startDate, endDate string) ([]Trade, error)

	// GetBySymbol retrieves trades for a symbol with optional limit
	GetBySymbol(symbol string, limit int) ([]Trade, error)

	// GetByISIN retrieves trades for an ISIN with optional limit
	GetByISIN(isin string, limit int) ([]Trade, error)

	// GetByIdentifier retrieves trades by symbol or ISIN with optional limit
	GetByIdentifier(identifier string, limit int) ([]Trade, error)

	// GetRecentlyBoughtISINs returns map of ISINs bought within specified days (excludes RESEARCH trades)
	GetRecentlyBoughtISINs(days int) (map[string]bool, error)

	// GetRecentlySoldISINs returns map of ISINs sold within specified days (excludes RESEARCH trades)
	GetRecentlySoldISINs(days int) (map[string]bool, error)

	// HasRecentSellOrder checks if there was a recent sell order for a symbol within specified hours
	HasRecentSellOrder(symbol string, hours float64) (bool, error)

	// GetFirstBuyDate retrieves the first buy date for a symbol
	GetFirstBuyDate(symbol string) (*string, error)

	// GetLastBuyDate retrieves the last buy date for a symbol
	GetLastBuyDate(symbol string) (*string, error)

	// GetLastSellDate retrieves the last sell date for a symbol
	GetLastSellDate(symbol string) (*string, error)

	// GetLastTransactionDate retrieves the last transaction date for a symbol
	GetLastTransactionDate(symbol string) (*string, error)

	// GetTradeDates retrieves first buy, last buy, and last sell dates for symbols
	GetTradeDates() (map[string]map[string]*string, error)

	// GetRecentTrades retrieves recent trades for a symbol within specified days
	GetRecentTrades(symbol string, days int) ([]Trade, error)

	// GetLastTradeTimestamp retrieves the timestamp of the most recent trade
	GetLastTradeTimestamp() (*time.Time, error)

	// GetTradeCountToday returns the number of trades executed today
	GetTradeCountToday() (int, error)

	// GetTradeCountThisWeek returns the number of trades executed this week
	GetTradeCountThisWeek() (int, error)
}

// Compile-time check that TradeRepository implements TradeRepositoryInterface
var _ TradeRepositoryInterface = (*TradeRepository)(nil)

// Note: TradernetClientInterface has been moved to domain/interfaces.go
// Use domain.BrokerClient instead

// TradingService handles trade-related business logic.
//
// This is a module-specific service that encapsulates trading domain logic.
// It coordinates trade queries, safety validation, and event emission.
//
// Responsibilities:
//   - Retrieve trade history with various filters
//   - Coordinate trade safety validation
//   - Emit trade-related events
//
// Dependencies:
//   - TradeRepositoryInterface: Trade data access
//   - domain.BrokerClient: Order placement
//   - TradeSafetyService: Safety rule validation
//   - events.Manager: Event emission
//
// See internal/services/README.md for service architecture documentation.
type TradingService struct {
	log           zerolog.Logger
	tradeRepo     TradeRepositoryInterface
	brokerClient  domain.BrokerClient
	safetyService *TradeSafetyService
	eventManager  *events.Manager
}

// NewTradingService creates a new trading service
func NewTradingService(
	tradeRepo TradeRepositoryInterface,
	brokerClient domain.BrokerClient,
	safetyService *TradeSafetyService,
	eventManager *events.Manager,
	log zerolog.Logger,
) *TradingService {
	return &TradingService{
		log:           log.With().Str("service", "trading").Logger(),
		tradeRepo:     tradeRepo,
		brokerClient:  brokerClient,
		safetyService: safetyService,
		eventManager:  eventManager,
	}
}

// SyncFromTradernet synchronizes trade history from Tradernet microservice
// Returns count of newly synced trades
func (s *TradingService) SyncFromTradernet() error {
	s.log.Info().Msg("Syncing trades from Tradernet")

	// Get recent trades from Tradernet (last 100 trades)
	trades, err := s.brokerClient.GetExecutedTrades(100)
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
		// Try RFC3339 first, then try without timezone (common format from APIs)
		var executedAt time.Time
		executedAt, err = time.Parse(time.RFC3339, trade.ExecutedAt)
		if err != nil {
			// Try parsing without timezone (e.g., "2025-05-07T14:03:22.300")
			executedAt, err = time.Parse("2006-01-02T15:04:05.000", trade.ExecutedAt)
			if err != nil {
				// Try parsing without milliseconds
				executedAt, err = time.Parse("2006-01-02T15:04:05", trade.ExecutedAt)
				if err != nil {
					s.log.Error().
						Err(err).
						Str("order_id", trade.OrderID).
						Str("executed_at", trade.ExecutedAt).
						Msg("Invalid executed_at timestamp")
					continue
				}
			}
		}

		// Validate price before creating trade record
		// Skip trades with invalid prices (<= 0) to prevent database constraint violations
		if trade.Price <= 0 {
			s.log.Warn().
				Str("order_id", trade.OrderID).
				Str("symbol", trade.Symbol).
				Float64("price", trade.Price).
				Msg("Skipping trade with invalid price")
			continue
		}

		// Calculate value in EUR (quantity * price)
		// Note: This assumes price is already in EUR. If currency conversion is needed,
		// it should be handled by looking up the security's currency and exchange rate.
		valueEUR := trade.Quantity * trade.Price

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
			ValueEUR:   &valueEUR,
		}

		// Insert trade to database (idempotent - Create() checks for existing order_id)
		if err := s.tradeRepo.Create(dbTrade); err != nil {
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

	// ===== EXECUTION BOUNDARY: BROKER HANDLES CURRENCY =====
	// We pass symbol and quantity to the broker. The broker API handles:
	//   1. Determining the security's native trading currency (USD/HKD/GBP)
	//   2. Converting available EUR cash to native currency as needed
	//   3. Placing the order in the native currency on the exchange
	//
	// We don't need to specify currency - the broker knows which currency each security trades in.
	// This completes the currency conversion cycle:
	//   Input: Broker returns native currency data → Input layer converts to EUR
	//   Planning: Planner works purely in EUR
	//   Output: Broker converts EUR back to native currency for execution
	orderResult, err := s.brokerClient.PlaceOrder(req.Symbol, req.Side, float64(req.Quantity), 0.0)
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
		Mode:       "live",
	}

	if err := s.tradeRepo.Create(trade); err != nil {
		s.log.Error().
			Err(err).
			Str("order_id", orderResult.OrderID).
			Msg("Failed to record trade in database")
		// Don't fail the execution - trade was placed successfully
	} else {
		// Emit TRADE_EXECUTED event
		if s.eventManager != nil {
			s.eventManager.Emit(events.TradeExecuted, "trading", map[string]interface{}{
				"symbol":   orderResult.Symbol,
				"side":     req.Side,
				"quantity": req.Quantity,
				"price":    orderResult.Price,
				"order_id": orderResult.OrderID,
				"source":   "autonomous",
			})
		}
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
