package scheduler

import (
	"errors"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/mock"
)

// MockUniverseService is a mock for testing
type MockUniverseService struct {
	mock.Mock
}

func (m *MockUniverseService) SyncPrices() error {
	args := m.Called()
	return args.Error(0)
}

func (m *MockUniverseService) SyncPricesForExchanges(exchangeNames []string) error {
	args := m.Called(exchangeNames)
	return args.Error(0)
}

// MockMarketHoursService is a mock for testing
type MockMarketHoursService struct {
	mock.Mock
}

func (m *MockMarketHoursService) GetAllMarketStatuses() []MarketStatus {
	args := m.Called()
	return args.Get(0).([]MarketStatus)
}

func (m *MockMarketHoursService) IsMarketOpen(exchangeName string) bool {
	args := m.Called(exchangeName)
	return args.Bool(0)
}

// MockBalanceService is a mock for testing
type MockBalanceService struct {
	mock.Mock
}

func (m *MockBalanceService) GetAllCurrencies() ([]string, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]string), args.Error(1)
}

func (m *MockBalanceService) GetTotalByCurrency(currency string) (float64, error) {
	args := m.Called(currency)
	return args.Get(0).(float64), args.Error(1)
}

func TestSyncPricesForOpenMarkets_AllMarketsOpen(t *testing.T) {
	// Setup
	mockUniverseService := new(MockUniverseService)
	mockMarketHours := new(MockMarketHoursService)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	job := &SyncCycleJob{
		universeService: mockUniverseService,
		marketHours:     mockMarketHours,
		log:             log,
	}

	// Mock data - all markets open
	statuses := []MarketStatus{
		{Exchange: "NYSE", IsOpen: true},
		{Exchange: "NASDAQ", IsOpen: true},
		{Exchange: "LSE", IsOpen: true},
	}

	// Mock expectations
	mockMarketHours.On("GetAllMarketStatuses").Return(statuses)
	mockUniverseService.On("SyncPricesForExchanges", []string{"NYSE", "NASDAQ", "LSE"}).Return(nil)

	// Execute
	job.syncPricesForOpenMarkets()

	// Assert
	mockMarketHours.AssertExpectations(t)
	mockUniverseService.AssertExpectations(t)
}

func TestSyncPricesForOpenMarkets_SomeMarketsClosed(t *testing.T) {
	// Setup
	mockUniverseService := new(MockUniverseService)
	mockMarketHours := new(MockMarketHoursService)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	job := &SyncCycleJob{
		universeService: mockUniverseService,
		marketHours:     mockMarketHours,
		log:             log,
	}

	// Mock data - only NYSE and NASDAQ open
	statuses := []MarketStatus{
		{Exchange: "NYSE", IsOpen: true},
		{Exchange: "NASDAQ", IsOpen: true},
		{Exchange: "LSE", IsOpen: false},
		{Exchange: "HKSE", IsOpen: false},
	}

	// Mock expectations - should only sync NYSE and NASDAQ
	mockMarketHours.On("GetAllMarketStatuses").Return(statuses)
	mockUniverseService.On("SyncPricesForExchanges", []string{"NYSE", "NASDAQ"}).Return(nil)

	// Execute
	job.syncPricesForOpenMarkets()

	// Assert
	mockMarketHours.AssertExpectations(t)
	mockUniverseService.AssertExpectations(t)
}

func TestSyncPricesForOpenMarkets_AllMarketsClosed(t *testing.T) {
	// Setup
	mockUniverseService := new(MockUniverseService)
	mockMarketHours := new(MockMarketHoursService)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	job := &SyncCycleJob{
		universeService: mockUniverseService,
		marketHours:     mockMarketHours,
		log:             log,
	}

	// Mock data - all markets closed
	statuses := []MarketStatus{
		{Exchange: "NYSE", IsOpen: false},
		{Exchange: "NASDAQ", IsOpen: false},
		{Exchange: "LSE", IsOpen: false},
	}

	// Mock expectations - should not call SyncPricesForExchanges
	mockMarketHours.On("GetAllMarketStatuses").Return(statuses)

	// Execute
	job.syncPricesForOpenMarkets()

	// Assert
	mockMarketHours.AssertExpectations(t)
	// SyncPricesForExchanges should not be called
	mockUniverseService.AssertNotCalled(t, "SyncPricesForExchanges")
}

func TestSyncPricesForOpenMarkets_NoMarketHours(t *testing.T) {
	// Setup
	mockUniverseService := new(MockUniverseService)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	job := &SyncCycleJob{
		universeService: mockUniverseService,
		marketHours:     nil, // No market hours service
		log:             log,
	}

	// Mock expectations - should fall back to syncing all prices
	mockUniverseService.On("SyncPrices").Return(nil)

	// Execute
	job.syncPricesForOpenMarkets()

	// Assert
	mockUniverseService.AssertExpectations(t)
	mockUniverseService.AssertCalled(t, "SyncPrices")
	mockUniverseService.AssertNotCalled(t, "SyncPricesForExchanges")
}

func TestSyncPricesForOpenMarkets_NoUniverseService(t *testing.T) {
	// Setup
	log := zerolog.New(nil).Level(zerolog.Disabled)

	job := &SyncCycleJob{
		universeService: nil,
		log:             log,
	}

	// Execute - should not panic, just log warning
	job.syncPricesForOpenMarkets()

	// No assertions needed - just verify it doesn't panic
}

func TestSyncPricesForOpenMarkets_SyncError(t *testing.T) {
	// Setup
	mockUniverseService := new(MockUniverseService)
	mockMarketHours := new(MockMarketHoursService)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	job := &SyncCycleJob{
		universeService: mockUniverseService,
		marketHours:     mockMarketHours,
		log:             log,
	}

	// Mock data
	statuses := []MarketStatus{
		{Exchange: "NYSE", IsOpen: true},
	}

	// Mock expectations - sync fails
	mockMarketHours.On("GetAllMarketStatuses").Return(statuses)
	mockUniverseService.On("SyncPricesForExchanges", []string{"NYSE"}).Return(errors.New("yahoo api error"))

	// Execute - should not panic, just log error
	job.syncPricesForOpenMarkets()

	// Assert
	mockMarketHours.AssertExpectations(t)
	mockUniverseService.AssertExpectations(t)
}

func TestSyncPricesForOpenMarkets_FallbackSyncError(t *testing.T) {
	// Setup
	mockUniverseService := new(MockUniverseService)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	job := &SyncCycleJob{
		universeService: mockUniverseService,
		marketHours:     nil, // No market hours - will fallback
		log:             log,
	}

	// Mock expectations - fallback sync fails
	mockUniverseService.On("SyncPrices").Return(errors.New("sync error"))

	// Execute - should not panic, just log error
	job.syncPricesForOpenMarkets()

	// Assert
	mockUniverseService.AssertExpectations(t)
}

func TestSyncPricesForOpenMarkets_EmptyStatuses(t *testing.T) {
	// Setup
	mockUniverseService := new(MockUniverseService)
	mockMarketHours := new(MockMarketHoursService)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	job := &SyncCycleJob{
		universeService: mockUniverseService,
		marketHours:     mockMarketHours,
		log:             log,
	}

	// Mock data - no market statuses
	statuses := []MarketStatus{}

	// Mock expectations
	mockMarketHours.On("GetAllMarketStatuses").Return(statuses)

	// Execute
	job.syncPricesForOpenMarkets()

	// Assert - should not call sync since no markets
	mockMarketHours.AssertExpectations(t)
	mockUniverseService.AssertNotCalled(t, "SyncPricesForExchanges")
}

func TestSyncPricesForOpenMarkets_SingleMarketOpen(t *testing.T) {
	// Setup
	mockUniverseService := new(MockUniverseService)
	mockMarketHours := new(MockMarketHoursService)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	job := &SyncCycleJob{
		universeService: mockUniverseService,
		marketHours:     mockMarketHours,
		log:             log,
	}

	// Mock data - only one market
	statuses := []MarketStatus{
		{Exchange: "NYSE", IsOpen: true},
	}

	// Mock expectations
	mockMarketHours.On("GetAllMarketStatuses").Return(statuses)
	mockUniverseService.On("SyncPricesForExchanges", []string{"NYSE"}).Return(nil)

	// Execute
	job.syncPricesForOpenMarkets()

	// Assert
	mockMarketHours.AssertExpectations(t)
	mockUniverseService.AssertExpectations(t)
}

// --- Negative Balance Tests ---

func TestCheckNegativeBalances_AllPositive(t *testing.T) {
	// Setup
	mockBalanceService := new(MockBalanceService)
	log := zerolog.New(nil).Level(zerolog.Disabled)
	emergencyCalled := false

	job := &SyncCycleJob{
		balanceService: mockBalanceService,
		emergencyRebalance: func() error {
			emergencyCalled = true
			return nil
		},
		log: log,
	}

	// Mock data - all currencies positive
	currencies := []string{"USD", "RUB", "EUR"}
	mockBalanceService.On("GetAllCurrencies").Return(currencies, nil)
	mockBalanceService.On("GetTotalByCurrency", "USD").Return(10000.0, nil)
	mockBalanceService.On("GetTotalByCurrency", "RUB").Return(500000.0, nil)
	mockBalanceService.On("GetTotalByCurrency", "EUR").Return(5000.0, nil)

	// Execute
	job.checkNegativeBalances()

	// Assert
	mockBalanceService.AssertExpectations(t)
	if emergencyCalled {
		t.Error("Emergency rebalance should not have been called for positive balances")
	}
}

func TestCheckNegativeBalances_OneNegative(t *testing.T) {
	// Setup
	mockBalanceService := new(MockBalanceService)
	log := zerolog.New(nil).Level(zerolog.Disabled)
	emergencyCalled := false

	job := &SyncCycleJob{
		balanceService: mockBalanceService,
		emergencyRebalance: func() error {
			emergencyCalled = true
			return nil
		},
		log: log,
	}

	// Mock data - USD is negative
	currencies := []string{"USD", "RUB", "EUR"}
	mockBalanceService.On("GetAllCurrencies").Return(currencies, nil)
	mockBalanceService.On("GetTotalByCurrency", "USD").Return(-100.0, nil)
	mockBalanceService.On("GetTotalByCurrency", "RUB").Return(500000.0, nil)
	mockBalanceService.On("GetTotalByCurrency", "EUR").Return(5000.0, nil)

	// Execute
	job.checkNegativeBalances()

	// Assert
	mockBalanceService.AssertExpectations(t)
	if !emergencyCalled {
		t.Error("Emergency rebalance should have been called for negative balance")
	}
}

func TestCheckNegativeBalances_MultipleNegative(t *testing.T) {
	// Setup
	mockBalanceService := new(MockBalanceService)
	log := zerolog.New(nil).Level(zerolog.Disabled)
	emergencyCallCount := 0

	job := &SyncCycleJob{
		balanceService: mockBalanceService,
		emergencyRebalance: func() error {
			emergencyCallCount++
			return nil
		},
		log: log,
	}

	// Mock data - USD and EUR are negative
	currencies := []string{"USD", "RUB", "EUR"}
	mockBalanceService.On("GetAllCurrencies").Return(currencies, nil)
	mockBalanceService.On("GetTotalByCurrency", "USD").Return(-100.0, nil)
	mockBalanceService.On("GetTotalByCurrency", "RUB").Return(500000.0, nil)
	mockBalanceService.On("GetTotalByCurrency", "EUR").Return(-50.0, nil)

	// Execute
	job.checkNegativeBalances()

	// Assert
	mockBalanceService.AssertExpectations(t)
	if emergencyCallCount != 1 {
		t.Errorf("Emergency rebalance should be called exactly once, got %d", emergencyCallCount)
	}
}

func TestCheckNegativeBalances_NoBalanceService(t *testing.T) {
	// Setup
	log := zerolog.New(nil).Level(zerolog.Disabled)
	emergencyCalled := false

	job := &SyncCycleJob{
		balanceService: nil,
		emergencyRebalance: func() error {
			emergencyCalled = true
			return nil
		},
		log: log,
	}

	// Execute - should not panic
	job.checkNegativeBalances()

	// Assert - emergency should not be called
	if emergencyCalled {
		t.Error("Emergency rebalance should not be called when balance service is nil")
	}
}

func TestCheckNegativeBalances_NoEmergencyCallback(t *testing.T) {
	// Setup
	mockBalanceService := new(MockBalanceService)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	job := &SyncCycleJob{
		balanceService:     mockBalanceService,
		emergencyRebalance: nil,
		log:                log,
	}

	// Mock data - USD is negative
	currencies := []string{"USD"}
	mockBalanceService.On("GetAllCurrencies").Return(currencies, nil)
	mockBalanceService.On("GetTotalByCurrency", "USD").Return(-100.0, nil)

	// Execute - should not panic
	job.checkNegativeBalances()

	// Assert
	mockBalanceService.AssertExpectations(t)
}

func TestCheckNegativeBalances_GetCurrenciesError(t *testing.T) {
	// Setup
	mockBalanceService := new(MockBalanceService)
	log := zerolog.New(nil).Level(zerolog.Disabled)
	emergencyCalled := false

	job := &SyncCycleJob{
		balanceService: mockBalanceService,
		emergencyRebalance: func() error {
			emergencyCalled = true
			return nil
		},
		log: log,
	}

	// Mock data - error getting currencies
	mockBalanceService.On("GetAllCurrencies").Return(nil, errors.New("database error"))

	// Execute - should not panic
	job.checkNegativeBalances()

	// Assert
	mockBalanceService.AssertExpectations(t)
	if emergencyCalled {
		t.Error("Emergency rebalance should not be called when currency fetch fails")
	}
}

func TestCheckNegativeBalances_GetTotalError(t *testing.T) {
	// Setup
	mockBalanceService := new(MockBalanceService)
	log := zerolog.New(nil).Level(zerolog.Disabled)
	emergencyCalled := false

	job := &SyncCycleJob{
		balanceService: mockBalanceService,
		emergencyRebalance: func() error {
			emergencyCalled = true
			return nil
		},
		log: log,
	}

	// Mock data - error getting total for one currency
	currencies := []string{"USD", "RUB"}
	mockBalanceService.On("GetAllCurrencies").Return(currencies, nil)
	mockBalanceService.On("GetTotalByCurrency", "USD").Return(0.0, errors.New("database error"))
	mockBalanceService.On("GetTotalByCurrency", "RUB").Return(-100.0, nil)

	// Execute - should continue checking other currencies
	job.checkNegativeBalances()

	// Assert
	mockBalanceService.AssertExpectations(t)
	if !emergencyCalled {
		t.Error("Emergency rebalance should be called even if one currency check fails")
	}
}

func TestCheckNegativeBalances_EmergencyRebalanceFails(t *testing.T) {
	// Setup
	mockBalanceService := new(MockBalanceService)
	log := zerolog.New(nil).Level(zerolog.Disabled)
	emergencyCalled := false

	job := &SyncCycleJob{
		balanceService: mockBalanceService,
		emergencyRebalance: func() error {
			emergencyCalled = true
			return errors.New("rebalance failed")
		},
		log: log,
	}

	// Mock data - negative balance
	currencies := []string{"USD"}
	mockBalanceService.On("GetAllCurrencies").Return(currencies, nil)
	mockBalanceService.On("GetTotalByCurrency", "USD").Return(-100.0, nil)

	// Execute - should not panic even if emergency rebalance fails
	job.checkNegativeBalances()

	// Assert
	mockBalanceService.AssertExpectations(t)
	if !emergencyCalled {
		t.Error("Emergency rebalance should have been attempted")
	}
}

func TestCheckNegativeBalances_ZeroBalance(t *testing.T) {
	// Setup
	mockBalanceService := new(MockBalanceService)
	log := zerolog.New(nil).Level(zerolog.Disabled)
	emergencyCalled := false

	job := &SyncCycleJob{
		balanceService: mockBalanceService,
		emergencyRebalance: func() error {
			emergencyCalled = true
			return nil
		},
		log: log,
	}

	// Mock data - zero balance (should not trigger emergency)
	currencies := []string{"USD"}
	mockBalanceService.On("GetAllCurrencies").Return(currencies, nil)
	mockBalanceService.On("GetTotalByCurrency", "USD").Return(0.0, nil)

	// Execute
	job.checkNegativeBalances()

	// Assert
	mockBalanceService.AssertExpectations(t)
	if emergencyCalled {
		t.Error("Emergency rebalance should not be called for zero balance")
	}
}

func TestCheckNegativeBalances_NoCurrencies(t *testing.T) {
	// Setup
	mockBalanceService := new(MockBalanceService)
	log := zerolog.New(nil).Level(zerolog.Disabled)
	emergencyCalled := false

	job := &SyncCycleJob{
		balanceService: mockBalanceService,
		emergencyRebalance: func() error {
			emergencyCalled = true
			return nil
		},
		log: log,
	}

	// Mock data - no currencies
	currencies := []string{}
	mockBalanceService.On("GetAllCurrencies").Return(currencies, nil)

	// Execute
	job.checkNegativeBalances()

	// Assert
	mockBalanceService.AssertExpectations(t)
	if emergencyCalled {
		t.Error("Emergency rebalance should not be called when no currencies exist")
	}
}
