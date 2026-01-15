package universe

import (
	"database/sql"
	"errors"
	"sync"
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
)

// syncTestBrokerClient is a minimal broker client mock for sync service tests
type syncTestBrokerClient struct {
	mu     sync.RWMutex
	quotes map[string]*domain.BrokerQuote
	err    error
}

func newSyncTestBrokerClient() *syncTestBrokerClient {
	return &syncTestBrokerClient{
		quotes: make(map[string]*domain.BrokerQuote),
	}
}

func (m *syncTestBrokerClient) setQuotes(quotes map[string]*domain.BrokerQuote) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.quotes = quotes
}

func (m *syncTestBrokerClient) setError(err error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.err = err
}

// BrokerClient interface implementation - only methods used by SyncPricesForSymbols
func (m *syncTestBrokerClient) GetQuotes(symbols []string) (map[string]*domain.BrokerQuote, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	if m.err != nil {
		return nil, m.err
	}
	return m.quotes, nil
}

// Stub implementations for other required methods
func (m *syncTestBrokerClient) GetPortfolio() ([]domain.BrokerPosition, error)       { return nil, nil }
func (m *syncTestBrokerClient) GetCashBalances() ([]domain.BrokerCashBalance, error) { return nil, nil }
func (m *syncTestBrokerClient) PlaceOrder(symbol, side string, quantity, limitPrice float64) (*domain.BrokerOrderResult, error) {
	return nil, nil
}
func (m *syncTestBrokerClient) GetExecutedTrades(limit int) ([]domain.BrokerTrade, error) {
	return nil, nil
}
func (m *syncTestBrokerClient) GetPendingOrders() ([]domain.BrokerPendingOrder, error) {
	return nil, nil
}
func (m *syncTestBrokerClient) GetQuote(symbol string) (*domain.BrokerQuote, error) { return nil, nil }
func (m *syncTestBrokerClient) GetLevel1Quote(symbol string) (*domain.BrokerOrderBook, error) {
	return nil, nil
}
func (m *syncTestBrokerClient) GetHistoricalPrices(symbol string, start, end int64, timeframeSeconds int) ([]domain.BrokerOHLCV, error) {
	return nil, nil
}
func (m *syncTestBrokerClient) FindSymbol(symbol string, exchange *string) ([]domain.BrokerSecurityInfo, error) {
	return nil, nil
}
func (m *syncTestBrokerClient) GetFXRates(baseCurrency string, currencies []string) (map[string]float64, error) {
	return nil, nil
}
func (m *syncTestBrokerClient) GetAllCashFlows(limit int) ([]domain.BrokerCashFlow, error) {
	return nil, nil
}
func (m *syncTestBrokerClient) GetCashMovements() (*domain.BrokerCashMovement, error) {
	return nil, nil
}
func (m *syncTestBrokerClient) IsConnected() bool                                { return true }
func (m *syncTestBrokerClient) HealthCheck() (*domain.BrokerHealthResult, error) { return nil, nil }
func (m *syncTestBrokerClient) SetCredentials(apiKey, apiSecret string)          {}
func (m *syncTestBrokerClient) GetSecurityMetadata(symbol string) (*domain.BrokerSecurityInfo, error) {
	return nil, nil
}

// MockDB is a mock database for testing
type MockDB struct {
	mock.Mock
}

func (m *MockDB) Exec(query string, args ...interface{}) (sql.Result, error) {
	callArgs := m.Called(query, args)
	if callArgs.Get(0) == nil {
		return nil, callArgs.Error(1)
	}
	return callArgs.Get(0).(sql.Result), callArgs.Error(1)
}

// MockResult implements sql.Result for testing
type MockResult struct {
	rowsAffected int64
}

func (m *MockResult) LastInsertId() (int64, error) {
	return 0, nil
}

func (m *MockResult) RowsAffected() (int64, error) {
	return m.rowsAffected, nil
}

func TestSyncPricesForSymbols_Success(t *testing.T) {
	// Setup
	mockBrokerClient := newSyncTestBrokerClient()
	mockDB := new(MockDB)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Set up quotes
	mockBrokerClient.setQuotes(map[string]*domain.BrokerQuote{
		"AAPL": {Price: 100.0},
		"MSFT": {Price: 200.0},
	})

	service := &SyncService{
		brokerClient: mockBrokerClient,
		securityRepo: nil, // Optional - code handles nil gracefully
		db:           mockDB,
		log:          log,
	}

	// Mock data
	aapl := "AAPL"
	msft := "MSFT"
	symbolMap := map[string]*string{
		"AAPL": &aapl,
		"MSFT": &msft,
	}

	// Mock expectations
	mockDB.On("Exec", mock.Anything, mock.Anything).Return(&MockResult{rowsAffected: 1}, nil)

	// Execute
	updated, err := service.SyncPricesForSymbols(symbolMap)

	// Assert
	assert.NoError(t, err)
	assert.Equal(t, 2, updated)
	mockDB.AssertNumberOfCalls(t, "Exec", 2) // Called once per symbol
}

func TestSyncPricesForSymbols_EmptyMap(t *testing.T) {
	// Setup
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &SyncService{
		log: log,
	}

	// Execute
	updated, err := service.SyncPricesForSymbols(map[string]*string{})

	// Assert
	assert.NoError(t, err)
	assert.Equal(t, 0, updated)
}

func TestSyncPricesForSymbols_BrokerError(t *testing.T) {
	// Setup
	mockBrokerClient := newSyncTestBrokerClient()
	mockBrokerClient.setError(errors.New("broker api error"))
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &SyncService{
		brokerClient: mockBrokerClient,
		log:          log,
	}

	// Mock data
	aapl := "AAPL"
	symbolMap := map[string]*string{
		"AAPL": &aapl,
	}

	// Execute
	updated, err := service.SyncPricesForSymbols(symbolMap)

	// Assert
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to fetch quotes from Tradernet")
	assert.Equal(t, 0, updated)
}

func TestSyncPricesForSymbols_NilPrice(t *testing.T) {
	// Setup
	mockBrokerClient := newSyncTestBrokerClient()
	mockDB := new(MockDB)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Set up quotes with one nil
	mockBrokerClient.setQuotes(map[string]*domain.BrokerQuote{
		"AAPL": {Price: 100.0},
		"MSFT": nil, // No price data for MSFT
	})

	service := &SyncService{
		brokerClient: mockBrokerClient,
		securityRepo: nil, // Optional - code handles nil gracefully
		db:           mockDB,
		log:          log,
	}

	// Mock data
	aapl := "AAPL"
	msft := "MSFT"
	symbolMap := map[string]*string{
		"AAPL": &aapl,
		"MSFT": &msft,
	}

	// Mock expectations
	mockDB.On("Exec", mock.Anything, mock.Anything).Return(&MockResult{rowsAffected: 1}, nil)

	// Execute
	updated, err := service.SyncPricesForSymbols(symbolMap)

	// Assert
	assert.NoError(t, err)
	assert.Equal(t, 1, updated)              // Only AAPL updated, MSFT skipped
	mockDB.AssertNumberOfCalls(t, "Exec", 1) // Called only for AAPL
}

func TestSyncPricesForSymbols_DatabaseError(t *testing.T) {
	// Setup
	mockBrokerClient := newSyncTestBrokerClient()
	mockDB := new(MockDB)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Set up quotes
	mockBrokerClient.setQuotes(map[string]*domain.BrokerQuote{
		"AAPL": {Price: 100.0},
	})

	service := &SyncService{
		brokerClient: mockBrokerClient,
		securityRepo: nil, // Optional - code handles nil gracefully
		db:           mockDB,
		log:          log,
	}

	// Mock data
	aapl := "AAPL"
	symbolMap := map[string]*string{
		"AAPL": &aapl,
	}

	// Mock expectations
	mockDB.On("Exec", mock.Anything, mock.Anything).Return(nil, errors.New("database error"))

	// Execute
	updated, err := service.SyncPricesForSymbols(symbolMap)

	// Assert
	assert.NoError(t, err) // Does not return error, just logs and continues
	assert.Equal(t, 0, updated)
	mockDB.AssertExpectations(t)
}

func TestSyncPricesForSymbols_NoRowsAffected(t *testing.T) {
	// Setup
	mockBrokerClient := newSyncTestBrokerClient()
	mockDB := new(MockDB)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Set up quotes
	mockBrokerClient.setQuotes(map[string]*domain.BrokerQuote{
		"AAPL": {Price: 100.0},
	})

	service := &SyncService{
		brokerClient: mockBrokerClient,
		securityRepo: nil, // Optional - code handles nil gracefully
		db:           mockDB,
		log:          log,
	}

	// Mock data
	aapl := "AAPL"
	symbolMap := map[string]*string{
		"AAPL": &aapl,
	}

	// Mock expectations - position doesn't exist in DB
	mockDB.On("Exec", mock.Anything, mock.Anything).Return(&MockResult{rowsAffected: 0}, nil)

	// Execute
	updated, err := service.SyncPricesForSymbols(symbolMap)

	// Assert
	assert.NoError(t, err)
	assert.Equal(t, 0, updated) // No rows affected means position doesn't exist
	mockDB.AssertExpectations(t)
}

func TestSyncPricesForSymbols_NoBrokerClient(t *testing.T) {
	// Setup
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &SyncService{
		brokerClient: nil,
		log:          log,
	}

	// Mock data
	aapl := "AAPL"
	symbolMap := map[string]*string{
		"AAPL": &aapl,
	}

	// Execute
	updated, err := service.SyncPricesForSymbols(symbolMap)

	// Assert
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "broker client not available")
	assert.Equal(t, 0, updated)
}
