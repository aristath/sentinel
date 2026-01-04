package trading

import (
	"errors"
	"testing"
	"time"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

// Mock Tradernet Client for testing

type mockTradernetClient struct {
	trades []tradernet.Trade
	err    error
}

func (m *mockTradernetClient) GetExecutedTrades(limit int) ([]tradernet.Trade, error) {
	if m.err != nil {
		return nil, m.err
	}
	return m.trades, nil
}

func (m *mockTradernetClient) PlaceOrder(symbol, side string, quantity float64) (*tradernet.OrderResult, error) {
	return &tradernet.OrderResult{
		OrderID:  "ORDER-" + symbol,
		Symbol:   symbol,
		Side:     side,
		Quantity: quantity,
		Price:    100.0,
	}, nil
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

	// Simulate UNIQUE constraint on order_id
	if m.duplicates[trade.OrderID] {
		return errors.New("UNIQUE constraint failed: trades.order_id")
	}

	m.duplicates[trade.OrderID] = true
	m.trades = append(m.trades, trade)
	return nil
}

// TestSyncFromTradernet_Success tests successful trade sync
func TestSyncFromTradernet_Success(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []tradernet.Trade{
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

	service := NewTradingService(mockRepo, mockClient, nil, log)

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
		trades: []tradernet.Trade{
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

	service := NewTradingService(mockRepo, mockClient, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)
	// Should only insert 2 trades (ORDER-1 once, ORDER-2 once)
	assert.Equal(t, 2, len(mockRepo.trades))
	// Create was called 3 times, but only 2 succeeded
	assert.Equal(t, 3, mockRepo.createCalls)
}

// TestSyncFromTradernet_InvalidSide tests handling of invalid trade side
func TestSyncFromTradernet_InvalidSide(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []tradernet.Trade{
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

	service := NewTradingService(mockRepo, mockClient, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)                   // Should not error, just skip invalid trade
	assert.Equal(t, 1, len(mockRepo.trades)) // Only ORDER-2 should be inserted
	assert.Equal(t, "ORDER-2", mockRepo.trades[0].OrderID)
}

// TestSyncFromTradernet_InvalidTimestamp tests handling of invalid timestamp
func TestSyncFromTradernet_InvalidTimestamp(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []tradernet.Trade{
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

	service := NewTradingService(mockRepo, mockClient, nil, log)

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

	service := NewTradingService(mockRepo, mockClient, nil, log)

	err := service.SyncFromTradernet()

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to get trades from Tradernet")
	assert.Equal(t, 0, len(mockRepo.trades))
}

// TestSyncFromTradernet_RepositoryError tests handling of database error
func TestSyncFromTradernet_RepositoryError(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []tradernet.Trade{
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

	service := NewTradingService(mockRepo, mockClient, nil, log)

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
		trades: []tradernet.Trade{},
	}

	mockRepo := newMockTradeRepository()

	service := NewTradingService(mockRepo, mockClient, nil, log)

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
				trades: []tradernet.Trade{
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
			service := NewTradingService(mockRepo, mockClient, nil, log)

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
				trades: []tradernet.Trade{
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
			service := NewTradingService(mockRepo, mockClient, nil, log)

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
		trades: []tradernet.Trade{
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
	service := NewTradingService(mockRepo, mockClient, nil, log)

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
		trades: []tradernet.Trade{
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
	service := NewTradingService(mockRepo, mockClient, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)
	assert.Equal(t, 1, len(mockRepo.trades))
	assert.Equal(t, "EUR", mockRepo.trades[0].Currency)
}

// TestSyncFromTradernet_SourceTracking tests that source is set to "tradernet"
func TestSyncFromTradernet_SourceTracking(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []tradernet.Trade{
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
	service := NewTradingService(mockRepo, mockClient, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)
	assert.Equal(t, 1, len(mockRepo.trades))
	assert.Equal(t, "tradernet", mockRepo.trades[0].Source)
	assert.Equal(t, "", mockRepo.trades[0].BucketID) // Empty for automatic sync
}

// TestSyncFromTradernet_LargeQuantity tests handling of large trade quantities
func TestSyncFromTradernet_LargeQuantity(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []tradernet.Trade{
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
	service := NewTradingService(mockRepo, mockClient, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)
	assert.Equal(t, 1, len(mockRepo.trades))
	assert.Equal(t, 999999.99, mockRepo.trades[0].Quantity)
}

// TestSyncFromTradernet_ZeroQuantity tests handling of zero quantity trades
func TestSyncFromTradernet_ZeroQuantity(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockClient := &mockTradernetClient{
		trades: []tradernet.Trade{
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
	service := NewTradingService(mockRepo, mockClient, nil, log)

	err := service.SyncFromTradernet()

	assert.NoError(t, err)
	// Should still insert - validation happens elsewhere
	assert.Equal(t, 1, len(mockRepo.trades))
	assert.Equal(t, 0.0, mockRepo.trades[0].Quantity)
}
