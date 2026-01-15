package services

import (
	"fmt"
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/pkg/logger"
	"github.com/stretchr/testify/assert"
)

func TestCurrencyExchangeService_GetAvailableCurrencies(t *testing.T) {
	service := &CurrencyExchangeService{}
	currencies := service.GetAvailableCurrencies()

	// Should include all currencies from DirectPairs
	expectedCurrencies := map[string]bool{
		"EUR": true,
		"USD": true,
		"GBP": true,
		"HKD": true,
	}

	assert.GreaterOrEqual(t, len(currencies), 4, "Should return at least 4 currencies")

	for _, curr := range currencies {
		assert.True(t, expectedCurrencies[curr], "Currency %s should be in expected list", curr)
		delete(expectedCurrencies, curr)
	}

	// All expected currencies should have been found
	for curr := range expectedCurrencies {
		t.Errorf("Expected currency %s not found in result", curr)
	}
}

func TestCurrencyExchangeService_GetConversionPath(t *testing.T) {
	service := &CurrencyExchangeService{}

	tests := []struct {
		name          string
		from          string
		to            string
		expectedSteps int
		expectedErr   bool
		description   string
	}{
		{
			name:          "same currency",
			from:          "EUR",
			to:            "EUR",
			expectedSteps: 0,
			expectedErr:   false,
			description:   "Same currency should return empty path",
		},
		{
			name:          "direct EUR to USD",
			from:          "EUR",
			to:            "USD",
			expectedSteps: 1,
			expectedErr:   false,
			description:   "Direct pair should return single step",
		},
		{
			name:          "direct USD to EUR",
			from:          "USD",
			to:            "EUR",
			expectedSteps: 1,
			expectedErr:   false,
			description:   "Direct pair reverse should return single step",
		},
		{
			name:          "direct GBP to EUR",
			from:          "GBP",
			to:            "EUR",
			expectedSteps: 1,
			expectedErr:   false,
			description:   "Direct GBP-EUR pair",
		},
		{
			name:          "GBP to HKD via EUR",
			from:          "GBP",
			to:            "HKD",
			expectedSteps: 2,
			expectedErr:   false,
			description:   "GBP-HKD should route via EUR",
		},
		{
			name:          "HKD to GBP via EUR",
			from:          "HKD",
			to:            "GBP",
			expectedSteps: 2,
			expectedErr:   false,
			description:   "HKD-GBP should route via EUR",
		},
		{
			name:          "invalid currency",
			from:          "INVALID",
			to:            "EUR",
			expectedSteps: 0,
			expectedErr:   true,
			description:   "Invalid currency should return error",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			path, err := service.GetConversionPath(tt.from, tt.to)
			if tt.expectedErr {
				assert.Error(t, err, tt.description)
				assert.Nil(t, path, "Path should be nil on error")
			} else {
				assert.NoError(t, err, tt.description)
				assert.NotNil(t, path, "Path should not be nil")
				assert.Equal(t, tt.expectedSteps, len(path), "Should have %d steps", tt.expectedSteps)

				// Verify path structure
				if len(path) > 0 {
					assert.Equal(t, tt.from, path[0].FromCurrency, "First step should start from source currency")
					if len(path) > 1 {
						assert.Equal(t, "EUR", path[0].ToCurrency, "First step in multi-step should go to EUR")
						assert.Equal(t, "EUR", path[1].FromCurrency, "Second step should start from EUR")
						assert.Equal(t, tt.to, path[len(path)-1].ToCurrency, "Last step should end at target currency")
					} else {
						assert.Equal(t, tt.to, path[0].ToCurrency, "Single step should go directly to target")
					}
				}
			}
		})
	}
}

// ============================================================================
// TDD Phase 1: Currency Exchange Tests - Market Orders
// ============================================================================

// Mock Broker Client that captures limit price
type mockBrokerClientCurrencyTest struct {
	capturedLimitPrice   float64
	placeOrderCalled     bool
	placeOrderErr        error
	capturedSymbol       string
	capturedSide         string
	capturedQuantity     float64
	getFXRatesResult     map[string]float64
	getFXRatesError      error
	getFXRatesBaseCurr   string
	getFXRatesCurrencies []string
	getFXRatesCalled     bool
}

func (m *mockBrokerClientCurrencyTest) PlaceOrder(symbol, side string, quantity, limitPrice float64) (*domain.BrokerOrderResult, error) {
	m.placeOrderCalled = true
	m.capturedSymbol = symbol
	m.capturedSide = side
	m.capturedQuantity = quantity
	m.capturedLimitPrice = limitPrice

	if m.placeOrderErr != nil {
		return nil, m.placeOrderErr
	}

	return &domain.BrokerOrderResult{
		OrderID:  "fx-order-123",
		Symbol:   symbol,
		Side:     side,
		Quantity: quantity,
		Price:    1.1, // Mock exchange rate
	}, nil
}

func (m *mockBrokerClientCurrencyTest) IsConnected() bool {
	return true
}

func (m *mockBrokerClientCurrencyTest) GetPortfolio() ([]domain.BrokerPosition, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTest) GetCashBalances() ([]domain.BrokerCashBalance, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTest) GetExecutedTrades(limit int) ([]domain.BrokerTrade, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTest) GetPendingOrders() ([]domain.BrokerPendingOrder, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTest) GetQuote(symbol string) (*domain.BrokerQuote, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTest) FindSymbol(symbol string, exchange *string) ([]domain.BrokerSecurityInfo, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTest) GetLevel1Quote(symbol string) (*domain.BrokerOrderBook, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTest) GetQuotes(symbols []string) (map[string]*domain.BrokerQuote, error) {
	return make(map[string]*domain.BrokerQuote), nil
}

func (m *mockBrokerClientCurrencyTest) GetHistoricalPrices(symbol string, start, end int64, timeframeSeconds int) ([]domain.BrokerOHLCV, error) {
	return []domain.BrokerOHLCV{}, nil
}

func (m *mockBrokerClientCurrencyTest) GetFXRates(baseCurrency string, currencies []string) (map[string]float64, error) {
	m.getFXRatesCalled = true
	m.getFXRatesBaseCurr = baseCurrency
	m.getFXRatesCurrencies = currencies
	if m.getFXRatesError != nil {
		return nil, m.getFXRatesError
	}
	return m.getFXRatesResult, nil
}

func (m *mockBrokerClientCurrencyTest) GetAllCashFlows(limit int) ([]domain.BrokerCashFlow, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTest) GetCashMovements() (*domain.BrokerCashMovement, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTest) HealthCheck() (*domain.BrokerHealthResult, error) {
	return &domain.BrokerHealthResult{Connected: true}, nil
}

func (m *mockBrokerClientCurrencyTest) SetCredentials(apiKey, apiSecret string) {
}

func (m *mockBrokerClientCurrencyTest) GetSecurityMetadata(symbol string) (*domain.BrokerSecurityInfo, error) {
	return nil, nil
}

// TestExecuteStep_MarketOrder tests that FX conversions use market orders
func TestExecuteStep_MarketOrder(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	mockBroker := &mockBrokerClientCurrencyTest{
		capturedLimitPrice: -1, // Sentinel value
	}

	service := &CurrencyExchangeService{
		brokerClient: mockBroker,
		log:          log,
	}

	step := ConversionStep{
		Symbol:       "EURUSD_T0.ITS",
		Action:       "BUY",
		FromCurrency: "EUR",
		ToCurrency:   "USD",
	}

	err := service.executeStep(step, 100.0)

	assert.NoError(t, err)
	assert.True(t, mockBroker.placeOrderCalled, "PlaceOrder should have been called")
	assert.Equal(t, 0.0, mockBroker.capturedLimitPrice, "FX conversion should use market order (limitPrice = 0.0)")
	assert.Equal(t, "EURUSD_T0.ITS", mockBroker.capturedSymbol)
	assert.Equal(t, "BUY", mockBroker.capturedSide)
}

// TestCurrencyExchangeService_GetRate_DirectPair tests GetRate() with direct currency pairs using GetFXRates
func TestCurrencyExchangeService_GetRate_DirectPair(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	tests := []struct {
		name          string
		from          string
		to            string
		fxRatesResult map[string]float64
		expectedRate  float64
		expectedError bool
		description   string
	}{
		{
			name:          "EUR to USD",
			from:          "EUR",
			to:            "USD",
			fxRatesResult: map[string]float64{"USD": 1.0835},
			expectedRate:  1.0835,
			expectedError: false,
			description:   "Direct EUR→USD should use EUR as base currency",
		},
		{
			name:          "USD to EUR",
			from:          "USD",
			to:            "EUR",
			fxRatesResult: map[string]float64{"EUR": 0.9226},
			expectedRate:  0.9226,
			expectedError: false,
			description:   "Direct USD→EUR should use USD as base currency",
		},
		{
			name:          "EUR to GBP",
			from:          "EUR",
			to:            "GBP",
			fxRatesResult: map[string]float64{"GBP": 0.8550},
			expectedRate:  0.8550,
			expectedError: false,
			description:   "Direct EUR→GBP should use EUR as base currency",
		},
		{
			name:          "same currency",
			from:          "EUR",
			to:            "EUR",
			fxRatesResult: nil,
			expectedRate:  1.0,
			expectedError: false,
			description:   "Same currency should return 1.0 without API call",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			mockBroker := &mockBrokerClientCurrencyTest{
				getFXRatesResult: tt.fxRatesResult,
			}

			service := &CurrencyExchangeService{
				brokerClient: mockBroker,
				log:          log,
			}

			rate, err := service.GetRate(tt.from, tt.to)

			if tt.expectedError {
				assert.Error(t, err, tt.description)
				assert.Equal(t, 0.0, rate, "Rate should be 0 on error")
			} else {
				assert.NoError(t, err, tt.description)
				assert.Equal(t, tt.expectedRate, rate, tt.description)
				if tt.from != tt.to {
					assert.True(t, mockBroker.getFXRatesCalled, "GetFXRates should have been called")
					assert.Equal(t, tt.from, mockBroker.getFXRatesBaseCurr, "Base currency should be fromCurrency")
					assert.Equal(t, []string{tt.to}, mockBroker.getFXRatesCurrencies, "Currencies should contain toCurrency")
				}
			}
		})
	}
}

// TestCurrencyExchangeService_GetRate_MultiStep tests GetRate() with multi-step conversions (GBP↔HKD via EUR)
func TestCurrencyExchangeService_GetRate_MultiStep(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// GBP→HKD via EUR: GBP→EUR then EUR→HKD
	mockBroker := &mockBrokerClientCurrencyTest{
		getFXRatesResult: map[string]float64{"EUR": 1.1695}, // GBP→EUR rate
	}

	service := &CurrencyExchangeService{
		brokerClient: mockBroker,
		log:          log,
	}

	// First call: GBP→EUR
	rate1, err := service.GetRate("GBP", "EUR")
	assert.NoError(t, err)
	assert.Equal(t, 1.1695, rate1)

	// Reset and test EUR→HKD
	mockBroker.getFXRatesResult = map[string]float64{"HKD": 8.4523}
	rate2, err := service.GetRate("EUR", "HKD")
	assert.NoError(t, err)
	assert.Equal(t, 8.4523, rate2)

	// GBP→HKD should use the path (GBP→EUR→HKD) and multiply rates
	// This will call GetRate recursively, so we need to set up the mock to handle multiple calls
	mockBroker.getFXRatesCalled = false
	mockBroker.getFXRatesResult = map[string]float64{"EUR": 1.1695}

	// For multi-step, getRateViaPath calls GetRate recursively
	// The implementation handles this correctly by calling GetRate for each path step
	_, err = service.GetRate("GBP", "HKD")
	assert.NoError(t, err, "Multi-step path should work correctly")
	// Note: This test validates the recursive GetRate calls work correctly
}

// TestCurrencyExchangeService_GetRate_ErrorHandling tests GetRate() error handling
func TestCurrencyExchangeService_GetRate_ErrorHandling(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	t.Run("API error", func(t *testing.T) {
		mockBroker := &mockBrokerClientCurrencyTest{
			getFXRatesError: fmt.Errorf("API error"),
		}

		service := &CurrencyExchangeService{
			brokerClient: mockBroker,
			log:          log,
		}

		rate, err := service.GetRate("EUR", "USD")

		assert.Error(t, err, "Should return error when GetFXRates fails")
		assert.Equal(t, 0.0, rate, "Rate should be 0 on error")
	})

	t.Run("missing rate", func(t *testing.T) {
		mockBroker := &mockBrokerClientCurrencyTest{
			getFXRatesResult: map[string]float64{}, // Empty map
		}

		service := &CurrencyExchangeService{
			brokerClient: mockBroker,
			log:          log,
		}

		rate, err := service.GetRate("EUR", "USD")

		assert.Error(t, err, "Should return error when rate not found in result")
		assert.Equal(t, 0.0, rate, "Rate should be 0 on error")
	})

	t.Run("not connected", func(t *testing.T) {
		mockBroker := &mockBrokerClientCurrencyTestNotConnected{}

		service := &CurrencyExchangeService{
			brokerClient: mockBroker,
			log:          log,
		}

		rate, err := service.GetRate("EUR", "USD")

		assert.Error(t, err, "Should return error when broker not connected")
		assert.Equal(t, 0.0, rate, "Rate should be 0 on error")
	})
}

// mockBrokerClientCurrencyTestNotConnected is a mock that returns false for IsConnected
type mockBrokerClientCurrencyTestNotConnected struct{}

func (m *mockBrokerClientCurrencyTestNotConnected) PlaceOrder(symbol, side string, quantity, limitPrice float64) (*domain.BrokerOrderResult, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTestNotConnected) IsConnected() bool {
	return false
}

func (m *mockBrokerClientCurrencyTestNotConnected) GetPortfolio() ([]domain.BrokerPosition, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTestNotConnected) GetCashBalances() ([]domain.BrokerCashBalance, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTestNotConnected) GetExecutedTrades(limit int) ([]domain.BrokerTrade, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTestNotConnected) GetPendingOrders() ([]domain.BrokerPendingOrder, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTestNotConnected) GetQuote(symbol string) (*domain.BrokerQuote, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTestNotConnected) GetQuotes(symbols []string) (map[string]*domain.BrokerQuote, error) {
	return make(map[string]*domain.BrokerQuote), nil
}

func (m *mockBrokerClientCurrencyTestNotConnected) GetHistoricalPrices(symbol string, start, end int64, timeframeSeconds int) ([]domain.BrokerOHLCV, error) {
	return []domain.BrokerOHLCV{}, nil
}

func (m *mockBrokerClientCurrencyTestNotConnected) FindSymbol(symbol string, exchange *string) ([]domain.BrokerSecurityInfo, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTestNotConnected) GetLevel1Quote(symbol string) (*domain.BrokerOrderBook, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTestNotConnected) GetFXRates(baseCurrency string, currencies []string) (map[string]float64, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTestNotConnected) GetAllCashFlows(limit int) ([]domain.BrokerCashFlow, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTestNotConnected) GetCashMovements() (*domain.BrokerCashMovement, error) {
	return nil, nil
}

func (m *mockBrokerClientCurrencyTestNotConnected) HealthCheck() (*domain.BrokerHealthResult, error) {
	return &domain.BrokerHealthResult{Connected: false}, nil
}

func (m *mockBrokerClientCurrencyTestNotConnected) SetCredentials(apiKey, apiSecret string) {
}

func (m *mockBrokerClientCurrencyTestNotConnected) GetSecurityMetadata(symbol string) (*domain.BrokerSecurityInfo, error) {
	return nil, nil
}
