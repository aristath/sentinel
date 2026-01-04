package optimization

import (
	"errors"
	"testing"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/mock"
)

// MockTradernetClient is a mock Tradernet client for testing
type MockTradernetClient struct {
	mock.Mock
}

func (m *MockTradernetClient) GetCashBalances() ([]tradernet.CashBalance, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]tradernet.CashBalance), args.Error(1)
}

// MockCurrencyExchangeService is a mock currency exchange service for testing
type MockCurrencyExchangeService struct {
	mock.Mock
}

func (m *MockCurrencyExchangeService) GetRate(fromCurrency, toCurrency string) (float64, error) {
	args := m.Called(fromCurrency, toCurrency)
	return args.Get(0).(float64), args.Error(1)
}

func TestGetCashBalance_AllEUR(t *testing.T) {
	// Setup
	mockTradernetClient := new(MockTradernetClient)
	mockExchangeService := new(MockCurrencyExchangeService)

	cashBalances := []tradernet.CashBalance{
		{Currency: "EUR", Amount: 1000.0},
		{Currency: "EUR", Amount: 500.0},
	}
	mockTradernetClient.On("GetCashBalances").Return(cashBalances, nil)

	logger := zerolog.Nop()
	handler := &Handler{
		tradernetClient:         mockTradernetClient,
		currencyExchangeService: mockExchangeService,
		log:                     logger,
	}

	// Execute
	totalEUR, err := handler.getCashBalance()

	// Assert
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
	expected := 1500.0
	if totalEUR != expected {
		t.Errorf("Expected total EUR to be %f, got %f", expected, totalEUR)
	}
	mockTradernetClient.AssertExpectations(t)
}

func TestGetCashBalance_MixedCurrencies(t *testing.T) {
	// Setup
	mockTradernetClient := new(MockTradernetClient)
	mockExchangeService := new(MockCurrencyExchangeService)

	cashBalances := []tradernet.CashBalance{
		{Currency: "EUR", Amount: 1000.0},
		{Currency: "USD", Amount: 500.0},
		{Currency: "GBP", Amount: 200.0},
	}
	mockTradernetClient.On("GetCashBalances").Return(cashBalances, nil)
	mockExchangeService.On("GetRate", "USD", "EUR").Return(0.92, nil)
	mockExchangeService.On("GetRate", "GBP", "EUR").Return(1.17, nil)

	logger := zerolog.Nop()
	handler := &Handler{
		tradernetClient:         mockTradernetClient,
		currencyExchangeService: mockExchangeService,
		log:                     logger,
	}

	// Execute
	totalEUR, err := handler.getCashBalance()

	// Assert
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
	// 1000 EUR + (500 * 0.92) EUR + (200 * 1.17) EUR = 1000 + 460 + 234 = 1694
	expected := 1694.0
	if totalEUR != expected {
		t.Errorf("Expected total EUR to be %f, got %f", expected, totalEUR)
	}
	mockTradernetClient.AssertExpectations(t)
	mockExchangeService.AssertExpectations(t)
}

func TestGetCashBalance_FallbackRates(t *testing.T) {
	// Setup
	mockTradernetClient := new(MockTradernetClient)
	mockExchangeService := new(MockCurrencyExchangeService)

	cashBalances := []tradernet.CashBalance{
		{Currency: "EUR", Amount: 1000.0},
		{Currency: "USD", Amount: 500.0},
		{Currency: "GBP", Amount: 200.0},
		{Currency: "HKD", Amount: 1000.0},
	}
	mockTradernetClient.On("GetCashBalances").Return(cashBalances, nil)
	// Exchange service fails, should use fallback rates
	mockExchangeService.On("GetRate", "USD", "EUR").Return(0.0, errors.New("exchange service unavailable"))
	mockExchangeService.On("GetRate", "GBP", "EUR").Return(0.0, errors.New("exchange service unavailable"))
	mockExchangeService.On("GetRate", "HKD", "EUR").Return(0.0, errors.New("exchange service unavailable"))

	logger := zerolog.Nop()
	handler := &Handler{
		tradernetClient:         mockTradernetClient,
		currencyExchangeService: mockExchangeService,
		log:                     logger,
	}

	// Execute
	totalEUR, err := handler.getCashBalance()

	// Assert
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
	// 1000 EUR + (500 * 0.9) EUR + (200 * 1.2) EUR + (1000 * 0.11) EUR
	// = 1000 + 450 + 240 + 110 = 1800
	expected := 1800.0
	if totalEUR != expected {
		t.Errorf("Expected total EUR to be %f, got %f", expected, totalEUR)
	}
	mockTradernetClient.AssertExpectations(t)
	mockExchangeService.AssertExpectations(t)
}

func TestGetCashBalance_TradernetFailure(t *testing.T) {
	// Setup
	mockTradernetClient := new(MockTradernetClient)
	mockExchangeService := new(MockCurrencyExchangeService)

	mockTradernetClient.On("GetCashBalances").Return(nil, errors.New("tradernet connection failed"))

	logger := zerolog.Nop()
	handler := &Handler{
		tradernetClient:         mockTradernetClient,
		currencyExchangeService: mockExchangeService,
		log:                     logger,
	}

	// Execute
	totalEUR, err := handler.getCashBalance()

	// Assert
	if err != nil {
		t.Errorf("Expected no error (graceful degradation), got %v", err)
	}
	// Should return 0 on Tradernet failure
	expected := 0.0
	if totalEUR != expected {
		t.Errorf("Expected total EUR to be %f, got %f", expected, totalEUR)
	}
	mockTradernetClient.AssertExpectations(t)
}

func TestGetCashBalance_PartialFallback(t *testing.T) {
	// Setup - one currency succeeds, one falls back
	mockTradernetClient := new(MockTradernetClient)
	mockExchangeService := new(MockCurrencyExchangeService)

	cashBalances := []tradernet.CashBalance{
		{Currency: "EUR", Amount: 1000.0},
		{Currency: "USD", Amount: 500.0},
		{Currency: "GBP", Amount: 200.0},
	}
	mockTradernetClient.On("GetCashBalances").Return(cashBalances, nil)
	// USD rate available, GBP fails
	mockExchangeService.On("GetRate", "USD", "EUR").Return(0.92, nil)
	mockExchangeService.On("GetRate", "GBP", "EUR").Return(0.0, errors.New("rate not found"))

	logger := zerolog.Nop()
	handler := &Handler{
		tradernetClient:         mockTradernetClient,
		currencyExchangeService: mockExchangeService,
		log:                     logger,
	}

	// Execute
	totalEUR, err := handler.getCashBalance()

	// Assert
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
	// 1000 EUR + (500 * 0.92) EUR + (200 * 1.2) EUR [fallback]
	// = 1000 + 460 + 240 = 1700
	expected := 1700.0
	if totalEUR != expected {
		t.Errorf("Expected total EUR to be %f, got %f", expected, totalEUR)
	}
	mockTradernetClient.AssertExpectations(t)
	mockExchangeService.AssertExpectations(t)
}

func TestGetCashBalance_UnknownCurrency(t *testing.T) {
	// Setup
	mockTradernetClient := new(MockTradernetClient)
	mockExchangeService := new(MockCurrencyExchangeService)

	cashBalances := []tradernet.CashBalance{
		{Currency: "EUR", Amount: 1000.0},
		{Currency: "JPY", Amount: 10000.0}, // Unknown currency
	}
	mockTradernetClient.On("GetCashBalances").Return(cashBalances, nil)
	// Exchange service fails for JPY
	mockExchangeService.On("GetRate", "JPY", "EUR").Return(0.0, errors.New("exchange service unavailable"))

	logger := zerolog.Nop()
	handler := &Handler{
		tradernetClient:         mockTradernetClient,
		currencyExchangeService: mockExchangeService,
		log:                     logger,
	}

	// Execute
	totalEUR, err := handler.getCashBalance()

	// Assert
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
	// 1000 EUR + 10000 JPY (assumed 1:1 as fallback for unknown) = 11000
	expected := 11000.0
	if totalEUR != expected {
		t.Errorf("Expected total EUR to be %f, got %f", expected, totalEUR)
	}
	mockTradernetClient.AssertExpectations(t)
	mockExchangeService.AssertExpectations(t)
}
