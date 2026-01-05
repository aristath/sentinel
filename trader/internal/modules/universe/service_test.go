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

func (m *MockSecurityRepository) GetAllActive() ([]Security, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]Security), args.Error(1)
}

func (m *MockSecurityRepository) GetByISIN(isin string) (*Security, error) {
	args := m.Called(isin)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*Security), args.Error(1)
}

func (m *MockSecurityRepository) GetBySymbol(symbol string) (*Security, error) {
	args := m.Called(symbol)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*Security), args.Error(1)
}

func (m *MockSecurityRepository) Update(isin string, updates map[string]interface{}) error {
	args := m.Called(isin, updates)
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
