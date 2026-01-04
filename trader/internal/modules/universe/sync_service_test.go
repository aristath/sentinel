package universe

import (
	"database/sql"
	"errors"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
)

// MockYahooClient is a mock Yahoo Finance client for testing
type MockYahooClient struct {
	mock.Mock
}

func (m *MockYahooClient) GetBatchQuotes(symbolMap map[string]*string) (map[string]*float64, error) {
	args := m.Called(symbolMap)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(map[string]*float64), args.Error(1)
}

func (m *MockYahooClient) GetSecurityIndustry(symbol string, yahooSymbolOverride *string) (*string, error) {
	args := m.Called(symbol, yahooSymbolOverride)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*string), args.Error(1)
}

func (m *MockYahooClient) GetSecurityCountryAndExchange(symbol string, yahooSymbolOverride *string) (*string, *string, error) {
	args := m.Called(symbol, yahooSymbolOverride)
	return args.Get(0).(*string), args.Get(1).(*string), args.Error(2)
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
	mockYahooClient := new(MockYahooClient)
	mockDB := new(MockDB)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &SyncService{
		yahooClient: mockYahooClient,
		db:          mockDB,
		log:         log,
	}

	// Mock data
	aapl := "AAPL"
	msft := "MSFT"
	symbolMap := map[string]*string{
		"AAPL": &aapl,
		"MSFT": &msft,
	}

	price100 := 100.0
	price200 := 200.0
	quotes := map[string]*float64{
		"AAPL": &price100,
		"MSFT": &price200,
	}

	// Mock expectations
	mockYahooClient.On("GetBatchQuotes", symbolMap).Return(quotes, nil)
	mockDB.On("Exec", mock.Anything, mock.Anything).Return(&MockResult{rowsAffected: 1}, nil)

	// Execute
	updated, err := service.SyncPricesForSymbols(symbolMap)

	// Assert
	assert.NoError(t, err)
	assert.Equal(t, 2, updated)
	mockYahooClient.AssertExpectations(t)
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

func TestSyncPricesForSymbols_YahooError(t *testing.T) {
	// Setup
	mockYahooClient := new(MockYahooClient)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &SyncService{
		yahooClient: mockYahooClient,
		log:         log,
	}

	// Mock data
	aapl := "AAPL"
	symbolMap := map[string]*string{
		"AAPL": &aapl,
	}

	// Mock expectations - Yahoo API error
	mockYahooClient.On("GetBatchQuotes", symbolMap).Return(nil, errors.New("yahoo api error"))

	// Execute
	updated, err := service.SyncPricesForSymbols(symbolMap)

	// Assert
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to fetch batch quotes")
	assert.Equal(t, 0, updated)
	mockYahooClient.AssertExpectations(t)
}

func TestSyncPricesForSymbols_NilPrice(t *testing.T) {
	// Setup
	mockYahooClient := new(MockYahooClient)
	mockDB := new(MockDB)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &SyncService{
		yahooClient: mockYahooClient,
		db:          mockDB,
		log:         log,
	}

	// Mock data
	aapl := "AAPL"
	msft := "MSFT"
	symbolMap := map[string]*string{
		"AAPL": &aapl,
		"MSFT": &msft,
	}

	price100 := 100.0
	quotes := map[string]*float64{
		"AAPL": &price100,
		"MSFT": nil, // No price data for MSFT
	}

	// Mock expectations
	mockYahooClient.On("GetBatchQuotes", symbolMap).Return(quotes, nil)
	mockDB.On("Exec", mock.Anything, mock.Anything).Return(&MockResult{rowsAffected: 1}, nil)

	// Execute
	updated, err := service.SyncPricesForSymbols(symbolMap)

	// Assert
	assert.NoError(t, err)
	assert.Equal(t, 1, updated) // Only AAPL updated, MSFT skipped
	mockYahooClient.AssertExpectations(t)
	mockDB.AssertNumberOfCalls(t, "Exec", 1) // Called only for AAPL
}

func TestSyncPricesForSymbols_DatabaseError(t *testing.T) {
	// Setup
	mockYahooClient := new(MockYahooClient)
	mockDB := new(MockDB)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &SyncService{
		yahooClient: mockYahooClient,
		db:          mockDB,
		log:         log,
	}

	// Mock data
	aapl := "AAPL"
	symbolMap := map[string]*string{
		"AAPL": &aapl,
	}

	price100 := 100.0
	quotes := map[string]*float64{
		"AAPL": &price100,
	}

	// Mock expectations
	mockYahooClient.On("GetBatchQuotes", symbolMap).Return(quotes, nil)
	mockDB.On("Exec", mock.Anything, mock.Anything).Return(nil, errors.New("database error"))

	// Execute
	updated, err := service.SyncPricesForSymbols(symbolMap)

	// Assert
	assert.NoError(t, err) // Does not return error, just logs and continues
	assert.Equal(t, 0, updated)
	mockYahooClient.AssertExpectations(t)
	mockDB.AssertExpectations(t)
}

func TestSyncPricesForSymbols_NoRowsAffected(t *testing.T) {
	// Setup
	mockYahooClient := new(MockYahooClient)
	mockDB := new(MockDB)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &SyncService{
		yahooClient: mockYahooClient,
		db:          mockDB,
		log:         log,
	}

	// Mock data
	aapl := "AAPL"
	symbolMap := map[string]*string{
		"AAPL": &aapl,
	}

	price100 := 100.0
	quotes := map[string]*float64{
		"AAPL": &price100,
	}

	// Mock expectations - position doesn't exist in DB
	mockYahooClient.On("GetBatchQuotes", symbolMap).Return(quotes, nil)
	mockDB.On("Exec", mock.Anything, mock.Anything).Return(&MockResult{rowsAffected: 0}, nil)

	// Execute
	updated, err := service.SyncPricesForSymbols(symbolMap)

	// Assert
	assert.NoError(t, err)
	assert.Equal(t, 0, updated) // No rows affected means position doesn't exist
	mockYahooClient.AssertExpectations(t)
	mockDB.AssertExpectations(t)
}
