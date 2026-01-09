package services

import (
	"errors"
	"testing"

	"github.com/aristath/sentinel/internal/modules/trading"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
)

// Mock CashManager
type MockCashManager struct {
	mock.Mock
}

func (m *MockCashManager) GetCashBalance(currency string) (float64, error) {
	args := m.Called(currency)
	return args.Get(0).(float64), args.Error(1)
}

func (m *MockCashManager) GetAllCashBalances() (map[string]float64, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(map[string]float64), args.Error(1)
}

func (m *MockCashManager) UpdateCashPosition(currency string, balance float64) error {
	args := m.Called(currency, balance)
	return args.Error(0)
}

// Mock Currency Exchange Service
type MockCurrencyExchangeService struct {
	mock.Mock
}

func (m *MockCurrencyExchangeService) GetRate(from, to string) (float64, error) {
	args := m.Called(from, to)
	return args.Get(0).(float64), args.Error(1)
}

func (m *MockCurrencyExchangeService) EnsureBalance(currency string, minAmount float64, sourceCurrency string) (bool, error) {
	// Not needed for failsafe tests
	return true, nil
}

// Test Market Hours Error Detection
func TestIsMarketHoursError_DetectsMarketClosedError(t *testing.T) {
	service := &TradeExecutionService{}

	testCases := []struct {
		errorMsg string
		expected bool
	}{
		{"Market is closed", true},
		{"market closed", true},
		{"MARKET CLOSED", true},
		{"trading hours have ended", true},
		{"outside trading hours", true},
		{"market not open", true},
		{"exchange closed", true},
		{"trading session closed", true},
		{"after hours trading not allowed", true},
		{"pre-market orders not accepted", true},
		{"Order rejected: invalid quantity", false},
		{"Insufficient funds", false},
		{"Network error", false},
		{"", false},
	}

	for _, tc := range testCases {
		result := service.isMarketHoursError(tc.errorMsg)
		assert.Equal(t, tc.expected, result, "Failed for error: %s", tc.errorMsg)
	}
}

// Test Retry Storage
func TestStorePendingRetry_StoresFailedTrade(t *testing.T) {
	mockTradeRepo := new(MockTradeRepo)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &TradeExecutionService{
		tradeRepo: mockTradeRepo,
		log:       log,
	}

	rec := TradeRecommendation{
		Symbol:         "AAPL",
		Side:           "BUY",
		Quantity:       10.0,
		EstimatedPrice: 150.0,
		Currency:       "USD",
		Reason:         "Portfolio rebalancing",
	}

	failureReason := "Market is closed"

	mockTradeRepo.On("CreatePendingRetry", mock.MatchedBy(func(retry trading.PendingRetry) bool {
		return retry.Symbol == "AAPL" &&
			retry.Side == "BUY" &&
			retry.Quantity == 10.0 &&
			retry.EstimatedPrice == 150.0 &&
			retry.Currency == "USD" &&
			retry.Reason == "Portfolio rebalancing" &&
			retry.FailureReason == failureReason &&
			retry.MaxAttempts == 3
	})).Return(nil)

	err := service.storePendingRetry(rec, failureReason)

	assert.NoError(t, err)
	mockTradeRepo.AssertExpectations(t)
}

func TestStorePendingRetry_ReturnsErrorWhenRepoUnavailable(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &TradeExecutionService{
		tradeRepo: nil, // Repository unavailable
		log:       log,
	}

	rec := TradeRecommendation{
		Symbol: "AAPL",
		Side:   "BUY",
	}

	err := service.storePendingRetry(rec, "Market closed")

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "trade repository not available")
}

// Mock TradeRepository for retry tests
type MockTradeRepo struct {
	mock.Mock
}

func (m *MockTradeRepo) Create(trade trading.Trade) error {
	args := m.Called(trade)
	return args.Error(0)
}

func (m *MockTradeRepo) CreatePendingRetry(retry trading.PendingRetry) error {
	args := m.Called(retry)
	return args.Error(0)
}

func (m *MockTradeRepo) GetPendingRetries() ([]trading.PendingRetry, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]trading.PendingRetry), args.Error(1)
}

func (m *MockTradeRepo) UpdateRetryStatus(id int64, status string) error {
	args := m.Called(id, status)
	return args.Error(0)
}

func (m *MockTradeRepo) IncrementRetryAttempt(id int64) error {
	args := m.Called(id)
	return args.Error(0)
}

// Test Commission Calculation
func TestCalculateCommission_EURCurrency(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &TradeExecutionService{
		log: log,
	}

	// Trade value: 1000 EUR
	// Fixed: 2 EUR
	// Variable: 1000 * 0.002 = 2 EUR
	// Total: 4 EUR
	commission, err := service.calculateCommission(1000.0, "EUR")

	assert.NoError(t, err)
	assert.Equal(t, 4.0, commission)
}

func TestCalculateCommission_USDCurrency(t *testing.T) {
	mockExchangeService := new(MockCurrencyExchangeService)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &TradeExecutionService{
		exchangeService: mockExchangeService,
		log:             log,
	}

	// EUR to USD rate: 1.1
	mockExchangeService.On("GetRate", "EUR", "USD").Return(1.1, nil)

	// Trade value: 1000 USD
	// Fixed: 2 EUR * 1.1 = 2.2 USD
	// Variable: 1000 * 0.002 = 2 USD
	// Total: 4.2 USD
	commission, err := service.calculateCommission(1000.0, "USD")

	assert.NoError(t, err)
	assert.Equal(t, 4.2, commission)
	mockExchangeService.AssertExpectations(t)
}

func TestCalculateCommission_FallbackOnExchangeError(t *testing.T) {
	mockExchangeService := new(MockCurrencyExchangeService)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &TradeExecutionService{
		exchangeService: mockExchangeService,
		log:             log,
	}

	// Exchange service fails
	mockExchangeService.On("GetRate", "EUR", "GBP").Return(0.0, errors.New("exchange error"))

	// Trade value: 1000 GBP
	// Fixed: 2 EUR (fallback, no conversion)
	// Variable: 1000 * 0.002 = 2 GBP
	// Total: 4 GBP (approximately, with unconverted EUR fee)
	commission, err := service.calculateCommission(1000.0, "GBP")

	assert.NoError(t, err)
	assert.Equal(t, 4.0, commission) // 2 (fixed, unconverted) + 2 (variable)
	mockExchangeService.AssertExpectations(t)
}
