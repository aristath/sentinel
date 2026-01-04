package universe

import (
	"errors"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
)

// MockSyncService is a mock implementation of SyncService for testing
type MockSyncService struct {
	mock.Mock
}

func (m *MockSyncService) SyncAllPrices() (int, error) {
	args := m.Called()
	return args.Int(0), args.Error(1)
}

func (m *MockSyncService) SyncPricesForSymbols(symbolMap map[string]*string) (int, error) {
	args := m.Called(symbolMap)
	return args.Int(0), args.Error(1)
}

// MockSecurityRepository is a mock for testing
type MockSecurityRepository struct {
	mock.Mock
}

func (m *MockSecurityRepository) GetGroupedByExchange() (map[string][]Security, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(map[string][]Security), args.Error(1)
}

func (m *MockSecurityRepository) GetAllActive() ([]Security, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]Security), args.Error(1)
}

func (m *MockSecurityRepository) Update(symbol string, updates map[string]interface{}) error {
	args := m.Called(symbol, updates)
	return args.Error(0)
}

func TestSyncPrices_Success(t *testing.T) {
	// Setup
	mockSyncService := new(MockSyncService)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &UniverseService{
		syncService: mockSyncService,
		log:         log,
	}

	// Mock expectations
	mockSyncService.On("SyncAllPrices").Return(10, nil)

	// Execute
	err := service.SyncPrices()

	// Assert
	assert.NoError(t, err)
	mockSyncService.AssertExpectations(t)
}

func TestSyncPrices_Error(t *testing.T) {
	// Setup
	mockSyncService := new(MockSyncService)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &UniverseService{
		syncService: mockSyncService,
		log:         log,
	}

	// Mock expectations
	mockSyncService.On("SyncAllPrices").Return(0, errors.New("yahoo api error"))

	// Execute
	err := service.SyncPrices()

	// Assert
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "price sync failed")
	mockSyncService.AssertExpectations(t)
}

func TestSyncPrices_NilSyncService(t *testing.T) {
	// Setup
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &UniverseService{
		syncService: nil,
		log:         log,
	}

	// Execute
	err := service.SyncPrices()

	// Assert
	assert.NoError(t, err) // Should not error, just skip
}

func TestSyncPricesForExchanges_Success(t *testing.T) {
	// Setup
	mockSyncService := new(MockSyncService)
	mockSecurityRepo := new(MockSecurityRepository)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &UniverseService{
		syncService:  mockSyncService,
		securityRepo: mockSecurityRepo,
		log:          log,
	}

	// Mock data
	grouped := map[string][]Security{
		"NYSE": {
			{Symbol: "AAPL", YahooSymbol: "AAPL"},
			{Symbol: "MSFT", YahooSymbol: "MSFT"},
		},
		"NASDAQ": {
			{Symbol: "GOOGL", YahooSymbol: "GOOGL"},
		},
		"LSE": {
			{Symbol: "BP", YahooSymbol: "BP.L"},
		},
	}

	openExchanges := []string{"NYSE", "NASDAQ"}

	// Mock expectations
	mockSecurityRepo.On("GetGroupedByExchange").Return(grouped, nil)
	mockSyncService.On("SyncPricesForSymbols", mock.MatchedBy(func(symbolMap map[string]*string) bool {
		// Should only include NYSE and NASDAQ symbols
		return len(symbolMap) == 3 // AAPL, MSFT, GOOGL
	})).Return(3, nil)

	// Execute
	err := service.SyncPricesForExchanges(openExchanges)

	// Assert
	assert.NoError(t, err)
	mockSecurityRepo.AssertExpectations(t)
	mockSyncService.AssertExpectations(t)
}

func TestSyncPricesForExchanges_EmptyList(t *testing.T) {
	// Setup
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &UniverseService{
		log: log,
	}

	// Execute
	err := service.SyncPricesForExchanges([]string{})

	// Assert
	assert.NoError(t, err) // Should not error, just skip
}

func TestSyncPricesForExchanges_NilSyncService(t *testing.T) {
	// Setup
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &UniverseService{
		syncService: nil,
		log:         log,
	}

	// Execute
	err := service.SyncPricesForExchanges([]string{"NYSE"})

	// Assert
	assert.NoError(t, err) // Should not error, just skip
}

func TestSyncPricesForExchanges_NoOpenMarkets(t *testing.T) {
	// Setup
	mockSyncService := new(MockSyncService)
	mockSecurityRepo := new(MockSecurityRepository)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &UniverseService{
		syncService:  mockSyncService,
		securityRepo: mockSecurityRepo,
		log:          log,
	}

	// Mock data - securities exist but no markets are open
	grouped := map[string][]Security{
		"NYSE": {
			{Symbol: "AAPL", YahooSymbol: "AAPL"},
		},
	}

	mockSecurityRepo.On("GetGroupedByExchange").Return(grouped, nil)
	mockSyncService.On("SyncPricesForSymbols", mock.MatchedBy(func(symbolMap map[string]*string) bool {
		return len(symbolMap) == 0 // No symbols because no markets are open
	})).Return(0, nil)

	// Execute - pass empty list of open exchanges
	err := service.SyncPricesForExchanges([]string{})

	// Assert
	assert.NoError(t, err)
}

func TestSyncPricesForExchanges_RepositoryError(t *testing.T) {
	// Setup
	mockSyncService := new(MockSyncService)
	mockSecurityRepo := new(MockSecurityRepository)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &UniverseService{
		syncService:  mockSyncService,
		securityRepo: mockSecurityRepo,
		log:          log,
	}

	// Mock expectations
	mockSecurityRepo.On("GetGroupedByExchange").Return(nil, errors.New("database error"))

	// Execute
	err := service.SyncPricesForExchanges([]string{"NYSE"})

	// Assert
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to group securities")
	mockSecurityRepo.AssertExpectations(t)
}
