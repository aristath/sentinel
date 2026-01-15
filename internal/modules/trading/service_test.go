package trading

import (
	"errors"
	"testing"
	"time"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

// Mock Broker Client for testing

type mockTradernetClient struct {
	trades []domain.BrokerTrade
	err    error
}

func (m *mockTradernetClient) GetExecutedTrades(limit int) ([]domain.BrokerTrade, error) {
	if m.err != nil {
		return nil, m.err
	}
	return m.trades, nil
}

func (m *mockTradernetClient) PlaceOrder(symbol, side string, quantity, limitPrice float64) (*domain.BrokerOrderResult, error) {
	return &domain.BrokerOrderResult{
		OrderID:  "ORDER-" + symbol,
		Symbol:   symbol,
		Side:     side,
		Quantity: quantity,
		Price:    100.0,
	}, nil
}

func (m *mockTradernetClient) GetPortfolio() ([]domain.BrokerPosition, error) {
	return nil, nil
}

func (m *mockTradernetClient) GetCashBalances() ([]domain.BrokerCashBalance, error) {
	return nil, nil
}

func (m *mockTradernetClient) GetPendingOrders() ([]domain.BrokerPendingOrder, error) {
	return nil, nil
}

func (m *mockTradernetClient) GetQuote(symbol string) (*domain.BrokerQuote, error) {
	return nil, nil
}

func (m *mockTradernetClient) FindSymbol(symbol string, exchange *string) ([]domain.BrokerSecurityInfo, error) {
	return nil, nil
}

func (m *mockTradernetClient) GetLevel1Quote(symbol string) (*domain.BrokerOrderBook, error) {
	return nil, nil
}

func (m *mockTradernetClient) GetFXRates(baseCurrency string, currencies []string) (map[string]float64, error) {
	return map[string]float64{}, nil
}

func (m *mockTradernetClient) GetAllCashFlows(limit int) ([]domain.BrokerCashFlow, error) {
	return nil, nil
}

func (m *mockTradernetClient) GetCashMovements() (*domain.BrokerCashMovement, error) {
	return nil, nil
}

func (m *mockTradernetClient) IsConnected() bool {
	return true
}

func (m *mockTradernetClient) HealthCheck() (*domain.BrokerHealthResult, error) {
	return &domain.BrokerHealthResult{Connected: true}, nil
}

func (m *mockTradernetClient) SetCredentials(apiKey, apiSecret string) {
}

func (m *mockTradernetClient) GetQuotes(symbols []string) (map[string]*domain.BrokerQuote, error) {
	return make(map[string]*domain.BrokerQuote), nil
}

func (m *mockTradernetClient) GetHistoricalPrices(symbol string, start, end int64, timeframeSeconds int) ([]domain.BrokerOHLCV, error) {
	return []domain.BrokerOHLCV{}, nil
}

func (m *mockTradernetClient) GetSecurityMetadata(symbol string) (*domain.BrokerSecurityInfo, error) {
	return nil, nil
}

// Mock Trade Repository for testing

type mockTradeRepository struct {
	trades      []Trade
	createErr   error
	duplicates  map[string]bool
	createCalls int
}

func newMockTradeRepository() *mockTradeRepository {
	return &mockTradeRepository{
		trades:     make([]Trade, 0),
		duplicates: make(map[string]bool),
	}
}

func (m *mockTradeRepository) Create(trade Trade) error {
	m.createCalls++
	if m.createErr != nil {
		return m.createErr
	}

	// Simulate duplicate detection (matches real implementation)
	// Real implementation checks Exists() and returns nil for duplicates
	if m.duplicates[trade.OrderID] {
		// Return nil (no error) for duplicates, matching real behavior
		return nil
	}

	m.duplicates[trade.OrderID] = true
	m.trades = append(m.trades, trade)
	return nil
}

// Additional methods required by TradeRepositoryInterface (stub implementations for tests)

func (m *mockTradeRepository) GetByOrderID(orderID string) (*Trade, error) {
	for _, trade := range m.trades {
		if trade.OrderID == orderID {
			return &trade, nil
		}
	}
	return nil, nil
}

func (m *mockTradeRepository) Exists(orderID string) (bool, error) {
	return m.duplicates[orderID], nil
}

func (m *mockTradeRepository) GetHistory(limit int) ([]Trade, error) {
	if limit > 0 && limit < len(m.trades) {
		return m.trades[:limit], nil
	}
	return m.trades, nil
}

func (m *mockTradeRepository) GetAllInRange(startDate, endDate string) ([]Trade, error) {
	return m.trades, nil
}

func (m *mockTradeRepository) GetBySymbol(symbol string, limit int) ([]Trade, error) {
	var result []Trade
	for _, trade := range m.trades {
		if trade.Symbol == symbol {
			result = append(result, trade)
			if limit > 0 && len(result) >= limit {
				break
			}
		}
	}
	return result, nil
}

func (m *mockTradeRepository) GetByISIN(isin string, limit int) ([]Trade, error) {
	var result []Trade
	for _, trade := range m.trades {
		if trade.ISIN == isin {
			result = append(result, trade)
			if limit > 0 && len(result) >= limit {
				break
			}
		}
	}
	return result, nil
}

func (m *mockTradeRepository) GetByIdentifier(identifier string, limit int) ([]Trade, error) {
	// Try ISIN first, then symbol
	if len(identifier) == 12 {
		return m.GetByISIN(identifier, limit)
	}
	return m.GetBySymbol(identifier, limit)
}

func (m *mockTradeRepository) GetRecentlyBoughtISINs(days int) (map[string]bool, error) {
	result := make(map[string]bool)
	for _, trade := range m.trades {
		if trade.Side == TradeSideBuy && trade.ISIN != "" {
			result[trade.ISIN] = true
		}
	}
	return result, nil
}

func (m *mockTradeRepository) GetRecentlySoldISINs(days int) (map[string]bool, error) {
	result := make(map[string]bool)
	for _, trade := range m.trades {
		if trade.Side == TradeSideSell && trade.ISIN != "" {
			result[trade.ISIN] = true
		}
	}
	return result, nil
}

func (m *mockTradeRepository) HasRecentSellOrder(symbol string, hours float64) (bool, error) {
	for _, trade := range m.trades {
		if trade.Symbol == symbol && trade.Side == TradeSideSell {
			return true, nil
		}
	}
	return false, nil
}

func (m *mockTradeRepository) GetFirstBuyDate(symbol string) (*string, error) {
	var firstDate *string
	for _, trade := range m.trades {
		if trade.Symbol == symbol && trade.Side == TradeSideBuy {
			dateStr := trade.ExecutedAt.Format("2006-01-02")
			if firstDate == nil || *firstDate > dateStr {
				firstDate = &dateStr
			}
		}
	}
	return firstDate, nil
}

func (m *mockTradeRepository) GetLastBuyDate(symbol string) (*string, error) {
	var lastDate *string
	for _, trade := range m.trades {
		if trade.Symbol == symbol && trade.Side == TradeSideBuy {
			dateStr := trade.ExecutedAt.Format("2006-01-02")
			if lastDate == nil || *lastDate < dateStr {
				lastDate = &dateStr
			}
		}
	}
	return lastDate, nil
}

func (m *mockTradeRepository) GetLastSellDate(symbol string) (*string, error) {
	var lastDate *string
	for _, trade := range m.trades {
		if trade.Symbol == symbol && trade.Side == TradeSideSell {
			dateStr := trade.ExecutedAt.Format("2006-01-02")
			if lastDate == nil || *lastDate < dateStr {
				lastDate = &dateStr
			}
		}
	}
	return lastDate, nil
}

func (m *mockTradeRepository) GetLastTransactionDate(symbol string) (*string, error) {
	var lastDate *string
	for _, trade := range m.trades {
		if trade.Symbol == symbol {
			dateStr := trade.ExecutedAt.Format("2006-01-02")
			if lastDate == nil || *lastDate < dateStr {
				lastDate = &dateStr
			}
		}
	}
	return lastDate, nil
}

func (m *mockTradeRepository) GetTradeDates() (map[string]map[string]*string, error) {
	result := make(map[string]map[string]*string)
	for _, trade := range m.trades {
		if result[trade.Symbol] == nil {
			result[trade.Symbol] = make(map[string]*string)
		}
		dateStr := trade.ExecutedAt.Format("2006-01-02")
		if trade.Side == TradeSideBuy {
			result[trade.Symbol]["last_buy"] = &dateStr
		} else if trade.Side == TradeSideSell {
			result[trade.Symbol]["last_sell"] = &dateStr
		}
	}
	return result, nil
}

func (m *mockTradeRepository) GetRecentTrades(symbol string, days int) ([]Trade, error) {
	return m.GetBySymbol(symbol, 0)
}

func (m *mockTradeRepository) GetLastTradeTimestamp() (*time.Time, error) {
	if len(m.trades) == 0 {
		return nil, nil
	}
	var latest *time.Time
	for _, trade := range m.trades {
		if latest == nil || trade.ExecutedAt.After(*latest) {
			latest = &trade.ExecutedAt
		}
	}
	return latest, nil
}

func (m *mockTradeRepository) GetTradeCountToday() (int, error) {
	now := time.Now()
	today := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())
	count := 0
	for _, trade := range m.trades {
		if trade.ExecutedAt.After(today) {
			count++
		}
	}
	return count, nil
}

func (m *mockTradeRepository) GetTradeCountThisWeek() (int, error) {
	now := time.Now()
	weekStart := now.AddDate(0, 0, -int(now.Weekday()))
	weekStart = time.Date(weekStart.Year(), weekStart.Month(), weekStart.Day(), 0, 0, 0, 0, weekStart.Location())
	count := 0
	for _, trade := range m.trades {
		if trade.ExecutedAt.After(weekStart) {
			count++
		}
	}
	return count, nil
}

// TestSyncFromTradernet_Success tests successful trade sync
func TestSyncFromTradernet_Success(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []domain.BrokerTrade{
			{
				OrderID:    "ORDER-1",
				Symbol:     "AAPL",
				Side:       "BUY",
				Quantity:   10,
				Price:      150.0,
				ExecutedAt: "2024-01-15T10:30:00Z",
			},
			{
				OrderID:    "ORDER-2",
				Symbol:     "MSFT",
				Side:       "SELL",
				Quantity:   5,
				Price:      300.0,
				ExecutedAt: "2024-01-15T11:00:00Z",
			},
		},
	}

	mockRepo := newMockTradeRepository()

	service := NewTradingService(mockRepo, mockClient, nil, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)
	assert.Equal(t, 2, len(mockRepo.trades))
	assert.Equal(t, "ORDER-1", mockRepo.trades[0].OrderID)
	assert.Equal(t, "AAPL", mockRepo.trades[0].Symbol)
	assert.Equal(t, TradeSideBuy, mockRepo.trades[0].Side)
	assert.Equal(t, 10.0, mockRepo.trades[0].Quantity)
	assert.Equal(t, 150.0, mockRepo.trades[0].Price)
	assert.Equal(t, "tradernet", mockRepo.trades[0].Source)
}

// TestSyncFromTradernet_DuplicateOrderID tests idempotent sync (duplicate detection)
func TestSyncFromTradernet_DuplicateOrderID(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []domain.BrokerTrade{
			{
				OrderID:    "ORDER-1",
				Symbol:     "AAPL",
				Side:       "BUY",
				Quantity:   10,
				Price:      150.0,
				ExecutedAt: "2024-01-15T10:30:00Z",
			},
			{
				OrderID:    "ORDER-1", // Duplicate
				Symbol:     "AAPL",
				Side:       "BUY",
				Quantity:   10,
				Price:      150.0,
				ExecutedAt: "2024-01-15T10:30:00Z",
			},
			{
				OrderID:    "ORDER-2",
				Symbol:     "MSFT",
				Side:       "SELL",
				Quantity:   5,
				Price:      300.0,
				ExecutedAt: "2024-01-15T11:00:00Z",
			},
		},
	}

	mockRepo := newMockTradeRepository()

	service := NewTradingService(mockRepo, mockClient, nil, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)
	// Should only insert 2 trades (ORDER-1 once, ORDER-2 once)
	assert.Equal(t, 2, len(mockRepo.trades))
	// Create was called 3 times (ORDER-1, ORDER-1 duplicate, ORDER-2)
	// Duplicate returns nil (no error) but doesn't insert, matching real behavior
	assert.Equal(t, 3, mockRepo.createCalls)
}

// TestSyncFromTradernet_InvalidSide tests handling of invalid trade side
func TestSyncFromTradernet_InvalidSide(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []domain.BrokerTrade{
			{
				OrderID:    "ORDER-1",
				Symbol:     "AAPL",
				Side:       "INVALID", // Invalid side
				Quantity:   10,
				Price:      150.0,
				ExecutedAt: "2024-01-15T10:30:00Z",
			},
			{
				OrderID:    "ORDER-2",
				Symbol:     "MSFT",
				Side:       "BUY", // Valid
				Quantity:   5,
				Price:      300.0,
				ExecutedAt: "2024-01-15T11:00:00Z",
			},
		},
	}

	mockRepo := newMockTradeRepository()

	service := NewTradingService(mockRepo, mockClient, nil, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)                   // Should not error, just skip invalid trade
	assert.Equal(t, 1, len(mockRepo.trades)) // Only ORDER-2 should be inserted
	assert.Equal(t, "ORDER-2", mockRepo.trades[0].OrderID)
}

// TestSyncFromTradernet_InvalidTimestamp tests handling of invalid timestamp
func TestSyncFromTradernet_InvalidTimestamp(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []domain.BrokerTrade{
			{
				OrderID:    "ORDER-1",
				Symbol:     "AAPL",
				Side:       "BUY",
				Quantity:   10,
				Price:      150.0,
				ExecutedAt: "invalid-timestamp",
			},
			{
				OrderID:    "ORDER-2",
				Symbol:     "MSFT",
				Side:       "SELL",
				Quantity:   5,
				Price:      300.0,
				ExecutedAt: "2024-01-15T11:00:00Z",
			},
		},
	}

	mockRepo := newMockTradeRepository()

	service := NewTradingService(mockRepo, mockClient, nil, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)                   // Should not error, just skip invalid trade
	assert.Equal(t, 1, len(mockRepo.trades)) // Only ORDER-2 should be inserted
	assert.Equal(t, "ORDER-2", mockRepo.trades[0].OrderID)
}

// TestSyncFromTradernet_TradernetError tests handling of Tradernet API error
func TestSyncFromTradernet_TradernetError(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		err: errors.New("API timeout"),
	}

	mockRepo := newMockTradeRepository()

	service := NewTradingService(mockRepo, mockClient, nil, nil, log)

	err := service.SyncFromTradernet()

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to get trades from Tradernet")
	assert.Equal(t, 0, len(mockRepo.trades))
}

// TestSyncFromTradernet_RepositoryError tests handling of database error
func TestSyncFromTradernet_RepositoryError(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []domain.BrokerTrade{
			{
				OrderID:    "ORDER-1",
				Symbol:     "AAPL",
				Side:       "BUY",
				Quantity:   10,
				Price:      150.0,
				ExecutedAt: "2024-01-15T10:30:00Z",
			},
			{
				OrderID:    "ORDER-2",
				Symbol:     "MSFT",
				Side:       "SELL",
				Quantity:   5,
				Price:      300.0,
				ExecutedAt: "2024-01-15T11:00:00Z",
			},
		},
	}

	mockRepo := newMockTradeRepository()
	mockRepo.createErr = errors.New("database connection lost")

	service := NewTradingService(mockRepo, mockClient, nil, nil, log)

	err := service.SyncFromTradernet()

	// Should not fail - logs errors but continues
	assert.NoError(t, err)
	// No trades inserted due to repo error
	assert.Equal(t, 0, len(mockRepo.trades))
}

// TestSyncFromTradernet_EmptyResponse tests handling of empty trade list
func TestSyncFromTradernet_EmptyResponse(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []domain.BrokerTrade{},
	}

	mockRepo := newMockTradeRepository()

	service := NewTradingService(mockRepo, mockClient, nil, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)
	assert.Equal(t, 0, len(mockRepo.trades))
}

// TestSyncFromTradernet_TimestampParsing tests RFC3339 timestamp parsing
func TestSyncFromTradernet_TimestampParsing(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	testCases := []struct {
		name        string
		executedAt  string
		shouldParse bool
	}{
		{
			name:        "RFC3339 with Z",
			executedAt:  "2024-01-15T10:30:00Z",
			shouldParse: true,
		},
		{
			name:        "RFC3339 with timezone",
			executedAt:  "2024-01-15T10:30:00+02:00",
			shouldParse: true,
		},
		{
			name:        "Invalid format",
			executedAt:  "2024-01-15 10:30:00",
			shouldParse: false,
		},
		{
			name:        "Empty string",
			executedAt:  "",
			shouldParse: false,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			mockClient := &mockTradernetClient{
				trades: []domain.BrokerTrade{
					{
						OrderID:    "ORDER-1",
						Symbol:     "AAPL",
						Side:       "BUY",
						Quantity:   10,
						Price:      150.0,
						ExecutedAt: tc.executedAt,
					},
				},
			}

			mockRepo := newMockTradeRepository()
			service := NewTradingService(mockRepo, mockClient, nil, nil, log)

			err := service.SyncFromTradernet()

			assert.NoError(t, err) // Service should not error

			if tc.shouldParse {
				assert.Equal(t, 1, len(mockRepo.trades))
				// Verify timestamp was parsed correctly
				expectedTime, _ := time.Parse(time.RFC3339, tc.executedAt)
				assert.Equal(t, expectedTime, mockRepo.trades[0].ExecutedAt)
			} else {
				assert.Equal(t, 0, len(mockRepo.trades))
			}
		})
	}
}

// TestSyncFromTradernet_TradeSideParsing tests BUY/SELL parsing
func TestSyncFromTradernet_TradeSideParsing(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	testCases := []struct {
		name         string
		side         string
		expectedSide TradeSide
		shouldParse  bool
	}{
		{
			name:         "BUY uppercase",
			side:         "BUY",
			expectedSide: TradeSideBuy,
			shouldParse:  true,
		},
		{
			name:         "SELL uppercase",
			side:         "SELL",
			expectedSide: TradeSideSell,
			shouldParse:  true,
		},
		{
			name:         "buy lowercase",
			side:         "buy",
			expectedSide: TradeSideBuy,
			shouldParse:  true,
		},
		{
			name:         "sell lowercase",
			side:         "sell",
			expectedSide: TradeSideSell,
			shouldParse:  true,
		},
		{
			name:        "Invalid side",
			side:        "HOLD",
			shouldParse: false,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			mockClient := &mockTradernetClient{
				trades: []domain.BrokerTrade{
					{
						OrderID:    "ORDER-1",
						Symbol:     "AAPL",
						Side:       tc.side,
						Quantity:   10,
						Price:      150.0,
						ExecutedAt: "2024-01-15T10:30:00Z",
					},
				},
			}

			mockRepo := newMockTradeRepository()
			service := NewTradingService(mockRepo, mockClient, nil, nil, log)

			err := service.SyncFromTradernet()
			assert.NoError(t, err)

			if tc.shouldParse {
				assert.Equal(t, 1, len(mockRepo.trades))
				assert.Equal(t, tc.expectedSide, mockRepo.trades[0].Side)
			} else {
				assert.Equal(t, 0, len(mockRepo.trades))
			}
		})
	}
}

// TestSyncFromTradernet_PartialSuccess tests mixed valid/invalid trades
func TestSyncFromTradernet_PartialSuccess(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []domain.BrokerTrade{
			{
				OrderID:    "ORDER-1",
				Symbol:     "AAPL",
				Side:       "BUY",
				Quantity:   10,
				Price:      150.0,
				ExecutedAt: "2024-01-15T10:30:00Z",
			},
			{
				OrderID:    "ORDER-2",
				Symbol:     "MSFT",
				Side:       "INVALID", // Invalid side
				Quantity:   5,
				Price:      300.0,
				ExecutedAt: "2024-01-15T11:00:00Z",
			},
			{
				OrderID:    "ORDER-3",
				Symbol:     "GOOGL",
				Side:       "SELL",
				Quantity:   3,
				Price:      2800.0,
				ExecutedAt: "invalid-timestamp", // Invalid timestamp
			},
			{
				OrderID:    "ORDER-4",
				Symbol:     "TSLA",
				Side:       "BUY",
				Quantity:   15,
				Price:      250.0,
				ExecutedAt: "2024-01-15T12:00:00Z",
			},
		},
	}

	mockRepo := newMockTradeRepository()
	service := NewTradingService(mockRepo, mockClient, nil, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)
	// Should insert 2 valid trades (ORDER-1, ORDER-4)
	assert.Equal(t, 2, len(mockRepo.trades))
	assert.Equal(t, "ORDER-1", mockRepo.trades[0].OrderID)
	assert.Equal(t, "ORDER-4", mockRepo.trades[1].OrderID)
}

// TestSyncFromTradernet_CurrencyDefault tests that currency defaults to EUR
func TestSyncFromTradernet_CurrencyDefault(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []domain.BrokerTrade{
			{
				OrderID:    "ORDER-1",
				Symbol:     "AAPL",
				Side:       "BUY",
				Quantity:   10,
				Price:      150.0,
				ExecutedAt: "2024-01-15T10:30:00Z",
			},
		},
	}

	mockRepo := newMockTradeRepository()
	service := NewTradingService(mockRepo, mockClient, nil, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)
	assert.Equal(t, 1, len(mockRepo.trades))
	assert.Equal(t, "EUR", mockRepo.trades[0].Currency)
}

// TestSyncFromTradernet_SourceTracking tests that source is set to "tradernet"
func TestSyncFromTradernet_SourceTracking(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []domain.BrokerTrade{
			{
				OrderID:    "ORDER-1",
				Symbol:     "AAPL",
				Side:       "BUY",
				Quantity:   10,
				Price:      150.0,
				ExecutedAt: "2024-01-15T10:30:00Z",
			},
		},
	}

	mockRepo := newMockTradeRepository()
	service := NewTradingService(mockRepo, mockClient, nil, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)
	assert.Equal(t, 1, len(mockRepo.trades))
	assert.Equal(t, "tradernet", mockRepo.trades[0].Source)
}

// TestSyncFromTradernet_LargeQuantity tests handling of large trade quantities
func TestSyncFromTradernet_LargeQuantity(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []domain.BrokerTrade{
			{
				OrderID:    "ORDER-1",
				Symbol:     "AAPL",
				Side:       "BUY",
				Quantity:   999999.99,
				Price:      150.0,
				ExecutedAt: "2024-01-15T10:30:00Z",
			},
		},
	}

	mockRepo := newMockTradeRepository()
	service := NewTradingService(mockRepo, mockClient, nil, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)
	assert.Equal(t, 1, len(mockRepo.trades))
	assert.Equal(t, 999999.99, mockRepo.trades[0].Quantity)
}

// TestSyncFromTradernet_ZeroQuantity tests handling of zero quantity trades
func TestSyncFromTradernet_ZeroQuantity(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []domain.BrokerTrade{
			{
				OrderID:    "ORDER-1",
				Symbol:     "AAPL",
				Side:       "BUY",
				Quantity:   0, // Zero quantity
				Price:      150.0,
				ExecutedAt: "2024-01-15T10:30:00Z",
			},
		},
	}

	mockRepo := newMockTradeRepository()
	service := NewTradingService(mockRepo, mockClient, nil, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)
	// Should still insert - validation happens elsewhere
	assert.Equal(t, 1, len(mockRepo.trades))
	assert.Equal(t, 0.0, mockRepo.trades[0].Quantity)
}

// TestSyncFromTradernet_SkipsInvalidPrice tests that trades with invalid prices are skipped
func TestSyncFromTradernet_SkipsInvalidPrice(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []domain.BrokerTrade{
			{
				OrderID:    "ORDER-1",
				Symbol:     "AAPL",
				Side:       "BUY",
				Quantity:   10,
				Price:      0.0, // Invalid - should skip
				ExecutedAt: "2024-01-15T10:30:00Z",
			},
			{
				OrderID:    "ORDER-2",
				Symbol:     "MSFT",
				Side:       "SELL",
				Quantity:   5,
				Price:      -10.0, // Invalid - should skip
				ExecutedAt: "2024-01-15T11:00:00Z",
			},
			{
				OrderID:    "ORDER-3",
				Symbol:     "GOOGL",
				Side:       "BUY",
				Quantity:   3,
				Price:      100.0, // Valid - should insert
				ExecutedAt: "2024-01-15T12:00:00Z",
			},
		},
	}

	mockRepo := newMockTradeRepository()
	service := NewTradingService(mockRepo, mockClient, nil, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)
	// Only valid trade should be inserted
	assert.Equal(t, 1, len(mockRepo.trades))
	assert.Equal(t, "ORDER-3", mockRepo.trades[0].OrderID)
	assert.Equal(t, 100.0, mockRepo.trades[0].Price)
}
