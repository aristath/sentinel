package work

import (
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
)

// MockPortfolioSyncService mocks the portfolio sync service
type MockPortfolioSyncService struct {
	mock.Mock
}

func (m *MockPortfolioSyncService) SyncPortfolio() error {
	args := m.Called()
	return args.Error(0)
}

// MockTradesSyncService mocks the trades sync service
type MockTradesSyncService struct {
	mock.Mock
}

func (m *MockTradesSyncService) SyncTrades() error {
	args := m.Called()
	return args.Error(0)
}

// MockCashFlowsSyncService mocks the cash flows sync service
type MockCashFlowsSyncService struct {
	mock.Mock
}

func (m *MockCashFlowsSyncService) SyncCashFlows() error {
	args := m.Called()
	return args.Error(0)
}

// MockPricesSyncService mocks the prices sync service
type MockPricesSyncService struct {
	mock.Mock
}

func (m *MockPricesSyncService) SyncPrices() error {
	args := m.Called()
	return args.Error(0)
}

// MockExchangeRateSyncService mocks the exchange rate sync service
type MockExchangeRateSyncService struct {
	mock.Mock
}

func (m *MockExchangeRateSyncService) SyncExchangeRates() error {
	args := m.Called()
	return args.Error(0)
}

// MockDisplayUpdateService mocks the display update service
type MockDisplayUpdateService struct {
	mock.Mock
}

func (m *MockDisplayUpdateService) UpdateDisplay() error {
	args := m.Called()
	return args.Error(0)
}

// MockNegativeBalanceService mocks the negative balance check service
type MockNegativeBalanceService struct {
	mock.Mock
}

func (m *MockNegativeBalanceService) CheckNegativeBalances() error {
	args := m.Called()
	return args.Error(0)
}

// MockSyncEventManager mocks the event manager for sync
type MockSyncEventManager struct {
	mock.Mock
}

func (m *MockSyncEventManager) Emit(event string, data any) {
	m.Called(event, data)
}

func TestRegisterSyncWorkTypes(t *testing.T) {
	registry := NewRegistry()

	deps := &SyncDeps{
		PortfolioService:       &MockPortfolioSyncService{},
		TradesService:          &MockTradesSyncService{},
		CashFlowsService:       &MockCashFlowsSyncService{},
		PricesService:          &MockPricesSyncService{},
		ExchangeRateService:    &MockExchangeRateSyncService{},
		DisplayService:         &MockDisplayUpdateService{},
		NegativeBalanceService: &MockNegativeBalanceService{},
		EventManager:           &MockSyncEventManager{},
	}

	RegisterSyncWorkTypes(registry, deps)

	// Verify all 7 sync work types are registered
	assert.True(t, registry.Has("sync:portfolio"))
	assert.True(t, registry.Has("sync:trades"))
	assert.True(t, registry.Has("sync:cashflows"))
	assert.True(t, registry.Has("sync:prices"))
	assert.True(t, registry.Has("sync:rates"))
	assert.True(t, registry.Has("sync:display"))
	assert.True(t, registry.Has("sync:negative-balances"))
}

func TestSyncWorkTypes_Dependencies(t *testing.T) {
	registry := NewRegistry()
	deps := &SyncDeps{
		PortfolioService:       &MockPortfolioSyncService{},
		TradesService:          &MockTradesSyncService{},
		CashFlowsService:       &MockCashFlowsSyncService{},
		PricesService:          &MockPricesSyncService{},
		ExchangeRateService:    &MockExchangeRateSyncService{},
		DisplayService:         &MockDisplayUpdateService{},
		NegativeBalanceService: &MockNegativeBalanceService{},
		EventManager:           &MockSyncEventManager{},
	}

	RegisterSyncWorkTypes(registry, deps)

	// Check dependency chain
	// sync:portfolio has no dependencies (root)
	portfolioWt := registry.Get("sync:portfolio")
	require.NotNil(t, portfolioWt)
	assert.Empty(t, portfolioWt.DependsOn)

	// sync:trades depends on sync:portfolio
	tradesWt := registry.Get("sync:trades")
	require.NotNil(t, tradesWt)
	assert.Contains(t, tradesWt.DependsOn, "sync:portfolio")

	// sync:cashflows depends on sync:portfolio
	cashflowsWt := registry.Get("sync:cashflows")
	require.NotNil(t, cashflowsWt)
	assert.Contains(t, cashflowsWt.DependsOn, "sync:portfolio")

	// sync:prices depends on sync:portfolio
	pricesWt := registry.Get("sync:prices")
	require.NotNil(t, pricesWt)
	assert.Contains(t, pricesWt.DependsOn, "sync:portfolio")

	// sync:display depends on sync:prices
	displayWt := registry.Get("sync:display")
	require.NotNil(t, displayWt)
	assert.Contains(t, displayWt.DependsOn, "sync:prices")

	// sync:negative-balances depends on sync:portfolio
	negBalWt := registry.Get("sync:negative-balances")
	require.NotNil(t, negBalWt)
	assert.Contains(t, negBalWt.DependsOn, "sync:portfolio")

	// sync:rates has no dependencies (independent)
	ratesWt := registry.Get("sync:rates")
	require.NotNil(t, ratesWt)
	assert.Empty(t, ratesWt.DependsOn)
}

func TestSyncPortfolio_Execute(t *testing.T) {
	registry := NewRegistry()

	portfolioService := &MockPortfolioSyncService{}
	portfolioService.On("SyncPortfolio").Return(nil)

	eventManager := &MockSyncEventManager{}
	eventManager.On("Emit", "PortfolioSynced", mock.Anything).Return()

	deps := &SyncDeps{
		PortfolioService:       portfolioService,
		TradesService:          &MockTradesSyncService{},
		CashFlowsService:       &MockCashFlowsSyncService{},
		PricesService:          &MockPricesSyncService{},
		ExchangeRateService:    &MockExchangeRateSyncService{},
		DisplayService:         &MockDisplayUpdateService{},
		NegativeBalanceService: &MockNegativeBalanceService{},
		EventManager:           eventManager,
	}

	RegisterSyncWorkTypes(registry, deps)

	wt := registry.Get("sync:portfolio")
	require.NotNil(t, wt)

	err := wt.Execute(context.Background(), "", nil)
	require.NoError(t, err)

	portfolioService.AssertExpectations(t)
	eventManager.AssertExpectations(t)
}

func TestSyncTrades_Execute(t *testing.T) {
	registry := NewRegistry()

	tradesService := &MockTradesSyncService{}
	tradesService.On("SyncTrades").Return(nil)

	deps := &SyncDeps{
		PortfolioService:       &MockPortfolioSyncService{},
		TradesService:          tradesService,
		CashFlowsService:       &MockCashFlowsSyncService{},
		PricesService:          &MockPricesSyncService{},
		ExchangeRateService:    &MockExchangeRateSyncService{},
		DisplayService:         &MockDisplayUpdateService{},
		NegativeBalanceService: &MockNegativeBalanceService{},
		EventManager:           &MockSyncEventManager{},
	}

	RegisterSyncWorkTypes(registry, deps)

	wt := registry.Get("sync:trades")
	require.NotNil(t, wt)

	err := wt.Execute(context.Background(), "", nil)
	require.NoError(t, err)

	tradesService.AssertExpectations(t)
}

func TestSyncRates_Execute(t *testing.T) {
	registry := NewRegistry()

	ratesService := &MockExchangeRateSyncService{}
	ratesService.On("SyncExchangeRates").Return(nil)

	deps := &SyncDeps{
		PortfolioService:       &MockPortfolioSyncService{},
		TradesService:          &MockTradesSyncService{},
		CashFlowsService:       &MockCashFlowsSyncService{},
		PricesService:          &MockPricesSyncService{},
		ExchangeRateService:    ratesService,
		DisplayService:         &MockDisplayUpdateService{},
		NegativeBalanceService: &MockNegativeBalanceService{},
		EventManager:           &MockSyncEventManager{},
	}

	RegisterSyncWorkTypes(registry, deps)

	wt := registry.Get("sync:rates")
	require.NotNil(t, wt)

	err := wt.Execute(context.Background(), "", nil)
	require.NoError(t, err)

	ratesService.AssertExpectations(t)
}

func TestSyncWorkTypes_MarketTiming(t *testing.T) {
	registry := NewRegistry()
	deps := &SyncDeps{
		PortfolioService:       &MockPortfolioSyncService{},
		TradesService:          &MockTradesSyncService{},
		CashFlowsService:       &MockCashFlowsSyncService{},
		PricesService:          &MockPricesSyncService{},
		ExchangeRateService:    &MockExchangeRateSyncService{},
		DisplayService:         &MockDisplayUpdateService{},
		NegativeBalanceService: &MockNegativeBalanceService{},
		EventManager:           &MockSyncEventManager{},
	}

	RegisterSyncWorkTypes(registry, deps)

	// Most sync work should run during market open
	duringMarketOpenTypes := []string{"sync:portfolio", "sync:trades", "sync:cashflows", "sync:prices"}
	for _, id := range duringMarketOpenTypes {
		wt := registry.Get(id)
		require.NotNil(t, wt, "work type %s should exist", id)
		assert.Equal(t, DuringMarketOpen, wt.MarketTiming, "work type %s should be DuringMarketOpen", id)
	}

	// sync:rates should be AnyTime
	ratesWt := registry.Get("sync:rates")
	require.NotNil(t, ratesWt)
	assert.Equal(t, AnyTime, ratesWt.MarketTiming)

	// sync:display should be AnyTime (updates after prices)
	displayWt := registry.Get("sync:display")
	require.NotNil(t, displayWt)
	assert.Equal(t, AnyTime, displayWt.MarketTiming)
}

func TestSyncWorkTypes_Priority(t *testing.T) {
	registry := NewRegistry()
	deps := &SyncDeps{
		PortfolioService:       &MockPortfolioSyncService{},
		TradesService:          &MockTradesSyncService{},
		CashFlowsService:       &MockCashFlowsSyncService{},
		PricesService:          &MockPricesSyncService{},
		ExchangeRateService:    &MockExchangeRateSyncService{},
		DisplayService:         &MockDisplayUpdateService{},
		NegativeBalanceService: &MockNegativeBalanceService{},
		EventManager:           &MockSyncEventManager{},
	}

	RegisterSyncWorkTypes(registry, deps)

	// sync:portfolio should be High priority
	portfolioWt := registry.Get("sync:portfolio")
	require.NotNil(t, portfolioWt)
	assert.Equal(t, PriorityHigh, portfolioWt.Priority)

	// Other sync types should be Medium priority
	mediumTypes := []string{"sync:prices", "sync:rates"}
	for _, id := range mediumTypes {
		wt := registry.Get(id)
		require.NotNil(t, wt)
		assert.Equal(t, PriorityMedium, wt.Priority, "work type %s should be medium priority", id)
	}
}
