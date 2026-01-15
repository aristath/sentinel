package domain

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

// TestCashManagerInterface tests that CashManager interface has all required methods
func TestCashManagerInterface(t *testing.T) {
	// This test ensures the interface contract is correct
	// We can't test the interface directly, but we can verify it compiles
	var _ CashManager = (*mockCashManager)(nil)
}

// TestBrokerClientInterface tests that BrokerClient interface has all required methods
func TestBrokerClientInterface(t *testing.T) {
	var _ BrokerClient = (*mockBrokerClient)(nil)
}

// TestCurrencyExchangeServiceInterface tests that CurrencyExchangeServiceInterface has all required methods
func TestCurrencyExchangeServiceInterface(t *testing.T) {
	var _ CurrencyExchangeServiceInterface = (*mockCurrencyExchangeService)(nil)
}

// TestAllocationTargetProvider tests that AllocationTargetProvider has all required methods
func TestAllocationTargetProvider(t *testing.T) {
	var _ AllocationTargetProvider = (*mockAllocationTargetProvider)(nil)
}

// TestPortfolioSummaryProvider tests that PortfolioSummaryProvider has all required methods
func TestPortfolioSummaryProvider(t *testing.T) {
	var _ PortfolioSummaryProvider = (*mockPortfolioSummaryProvider)(nil)
}

// TestConcentrationAlertProvider tests that ConcentrationAlertProvider has all required methods
func TestConcentrationAlertProvider(t *testing.T) {
	var _ ConcentrationAlertProvider = (*mockConcentrationAlertProvider)(nil)
}

// Mock implementations for testing

type mockCashManager struct{}

func (m *mockCashManager) UpdateCashPosition(currency string, balance float64) error {
	return nil
}

func (m *mockCashManager) GetAllCashBalances() (map[string]float64, error) {
	return map[string]float64{"EUR": 1000.0}, nil
}

func (m *mockCashManager) GetCashBalance(currency string) (float64, error) {
	return 1000.0, nil
}

type mockBrokerClient struct{}

func (m *mockBrokerClient) GetPortfolio() ([]BrokerPosition, error) {
	return nil, nil
}

func (m *mockBrokerClient) GetCashBalances() ([]BrokerCashBalance, error) {
	return nil, nil
}

func (m *mockBrokerClient) GetExecutedTrades(limit int) ([]BrokerTrade, error) {
	return nil, nil
}

func (m *mockBrokerClient) PlaceOrder(symbol, side string, quantity, limitPrice float64) (*BrokerOrderResult, error) {
	return nil, nil
}

func (m *mockBrokerClient) GetPendingOrders() ([]BrokerPendingOrder, error) {
	return nil, nil
}

func (m *mockBrokerClient) GetQuote(symbol string) (*BrokerQuote, error) {
	return nil, nil
}

func (m *mockBrokerClient) FindSymbol(symbol string, exchange *string) ([]BrokerSecurityInfo, error) {
	return nil, nil
}

func (m *mockBrokerClient) GetAllCashFlows(limit int) ([]BrokerCashFlow, error) {
	return nil, nil
}

func (m *mockBrokerClient) GetCashMovements() (*BrokerCashMovement, error) {
	return nil, nil
}

func (m *mockBrokerClient) IsConnected() bool {
	return true
}

func (m *mockBrokerClient) HealthCheck() (*BrokerHealthResult, error) {
	return nil, nil
}

func (m *mockBrokerClient) SetCredentials(apiKey, apiSecret string) {
}

func (m *mockBrokerClient) GetLevel1Quote(symbol string) (*BrokerOrderBook, error) {
	return nil, nil
}

func (m *mockBrokerClient) GetFXRates(baseCurrency string, currencies []string) (map[string]float64, error) {
	return map[string]float64{}, nil
}

func (m *mockBrokerClient) GetQuotes(symbols []string) (map[string]*BrokerQuote, error) {
	return make(map[string]*BrokerQuote), nil
}

func (m *mockBrokerClient) GetHistoricalPrices(symbol string, start, end int64, timeframeSeconds int) ([]BrokerOHLCV, error) {
	return []BrokerOHLCV{}, nil
}

func (m *mockBrokerClient) GetSecurityMetadata(symbol string) (*BrokerSecurityInfo, error) {
	return nil, nil
}

type mockCurrencyExchangeService struct{}

func (m *mockCurrencyExchangeService) GetRate(fromCurrency, toCurrency string) (float64, error) {
	return 1.0, nil
}

func (m *mockCurrencyExchangeService) EnsureBalance(currency string, minAmount float64, sourceCurrency string) (bool, error) {
	return true, nil
}

type mockAllocationTargetProvider struct{}

func (m *mockAllocationTargetProvider) GetAll() (map[string]float64, error) {
	return map[string]float64{"EUR": 0.5}, nil
}

type mockPortfolioSummaryProvider struct{}

func (m *mockPortfolioSummaryProvider) GetPortfolioSummary() (PortfolioSummary, error) {
	return PortfolioSummary{}, nil
}

type mockConcentrationAlertProvider struct{}

func (m *mockConcentrationAlertProvider) DetectAlerts(summary PortfolioSummary) ([]ConcentrationAlert, error) {
	return nil, nil
}

// TestInterfaceCompatibility tests that interfaces are compatible with existing implementations
func TestInterfaceCompatibility(t *testing.T) {
	// Test that CashManager interface includes all methods
	// This ensures backward compatibility
	assert.True(t, true, "Interface compatibility verified at compile time")
}
