package services

import (
	"fmt"
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/trading"
	"github.com/aristath/sentinel/pkg/logger"
	"github.com/stretchr/testify/assert"
)

// Note: Yahoo-based price validation tests have been removed as Yahoo client is no longer used.
// Price validation is now done using Tradernet broker prices only.

// Mock implementations for testing

type mockCashManager struct {
	balances map[string]float64 // currency -> balance
}

func newMockCashManager(balances map[string]float64) *mockCashManager {
	return &mockCashManager{
		balances: balances,
	}
}

func (m *mockCashManager) UpdateCashPosition(currency string, balance float64) error {
	if m.balances == nil {
		m.balances = make(map[string]float64)
	}
	m.balances[currency] = balance
	return nil
}

func (m *mockCashManager) GetCashBalance(currency string) (float64, error) {
	if balance, ok := m.balances[currency]; ok {
		return balance, nil
	}
	return 0.0, nil
}

func (m *mockCashManager) GetAllCashBalances() (map[string]float64, error) {
	return m.balances, nil
}

type mockCurrencyExchangeService struct {
	rates map[string]float64 // "FROM:TO" -> rate
}

func newMockCurrencyExchangeService(rates map[string]float64) *mockCurrencyExchangeService {
	return &mockCurrencyExchangeService{
		rates: rates,
	}
}

func (m *mockCurrencyExchangeService) GetRate(fromCurrency, toCurrency string) (float64, error) {
	if fromCurrency == toCurrency {
		return 1.0, nil
	}
	key := fromCurrency + ":" + toCurrency
	if rate, ok := m.rates[key]; ok {
		return rate, nil
	}
	return 0, nil
}

func (m *mockCurrencyExchangeService) EnsureBalance(currency string, minAmount float64, sourceCurrency string) (bool, error) {
	// Stub for tests that don't need currency conversion logic
	return true, nil
}

// mockCurrencyExchangeServiceWithEnsureBalance is a more complete mock that tracks balance operations
type mockCurrencyExchangeServiceWithEnsureBalance struct {
	rates                 map[string]float64 // "FROM:TO" -> rate
	cashManager           *mockCashManager
	ensureBalanceCalled   bool
	ensureBalanceCurrency string
	ensureBalanceAmount   float64
	ensureBalanceSource   string
}

func newMockCurrencyExchangeServiceWithEnsureBalance(rates map[string]float64, cashManager *mockCashManager) *mockCurrencyExchangeServiceWithEnsureBalance {
	return &mockCurrencyExchangeServiceWithEnsureBalance{
		rates:       rates,
		cashManager: cashManager,
	}
}

func (m *mockCurrencyExchangeServiceWithEnsureBalance) GetRate(fromCurrency, toCurrency string) (float64, error) {
	if fromCurrency == toCurrency {
		return 1.0, nil
	}
	key := fromCurrency + ":" + toCurrency
	if rate, ok := m.rates[key]; ok {
		return rate, nil
	}
	return 0, nil
}

func (m *mockCurrencyExchangeServiceWithEnsureBalance) EnsureBalance(currency string, minAmount float64, sourceCurrency string) (bool, error) {
	m.ensureBalanceCalled = true
	m.ensureBalanceCurrency = currency
	m.ensureBalanceAmount = minAmount
	m.ensureBalanceSource = sourceCurrency

	// Check if we have enough in the target currency
	currentBalance, _ := m.cashManager.GetCashBalance(currency)
	if currentBalance >= minAmount {
		return true, nil
	}

	// If insufficient and currency == sourceCurrency (e.g., both EUR), can't convert
	if currency == sourceCurrency {
		return false, fmt.Errorf("insufficient %s: need %.2f, have %.2f", currency, minAmount, currentBalance)
	}

	// Check if we have enough in source currency to convert
	sourceBalance, _ := m.cashManager.GetCashBalance(sourceCurrency)

	// Get conversion rate
	rate, err := m.GetRate(sourceCurrency, currency)
	if err != nil || rate <= 0 {
		return false, fmt.Errorf("cannot get exchange rate from %s to %s", sourceCurrency, currency)
	}

	// Calculate how much source currency we need
	sourceNeeded := minAmount / rate

	// Add 2% buffer for conversion fees
	sourceNeeded = sourceNeeded * 1.02

	if sourceBalance < sourceNeeded {
		return false, fmt.Errorf("insufficient %s for conversion: need %.2f, have %.2f", sourceCurrency, sourceNeeded, sourceBalance)
	}

	// Simulate the conversion by updating balances
	m.cashManager.UpdateCashPosition(sourceCurrency, sourceBalance-sourceNeeded)
	m.cashManager.UpdateCashPosition(currency, currentBalance+minAmount)

	return true, nil
}

// Test calculateCommission

func TestCalculateCommission_EUR(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		exchangeService: exchangeService,
		log:             log,
	}

	// Trade value: 1000 EUR
	// Expected commission:
	// - Fixed: 2.0 EUR
	// - Variable: 1000 * 0.002 = 2.0 EUR
	// - Total: 4.0 EUR
	commission, err := service.calculateCommission(1000.0, "EUR")
	if err != nil {
		t.Fatalf("Expected no error, got: %v", err)
	}

	expected := 4.0
	if commission != expected {
		t.Errorf("Expected commission %.2f, got %.2f", expected, commission)
	}
}

func TestCalculateCommission_USD(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// EUR:USD rate = 1.1 (1 EUR = 1.1 USD)
	exchangeService := newMockCurrencyExchangeService(map[string]float64{
		"EUR:USD": 1.1,
	})

	service := &TradeExecutionService{
		exchangeService: exchangeService,
		log:             log,
	}

	// Trade value: 1000 USD
	// Expected commission:
	// - Fixed: 2.0 EUR * 1.1 = 2.2 USD
	// - Variable: 1000 * 0.002 = 2.0 USD
	// - Total: 4.2 USD
	commission, err := service.calculateCommission(1000.0, "USD")
	if err != nil {
		t.Fatalf("Expected no error, got: %v", err)
	}

	expected := 4.2
	if commission != expected {
		t.Errorf("Expected commission %.2f, got %.2f", expected, commission)
	}
}

// Mock Tradernet Client for testing

type mockTradernetClient struct {
	connected      bool
	placeOrderErr  error
	placeOrderResp *domain.BrokerOrderResult
	quotes         map[string]*domain.BrokerQuote // configurable quotes for GetQuotes
}

func newMockTradernetClient(connected bool) *mockTradernetClient {
	return &mockTradernetClient{
		connected: connected,
	}
}

func (m *mockTradernetClient) IsConnected() bool {
	return m.connected
}

func (m *mockTradernetClient) GetPortfolio() ([]domain.BrokerPosition, error) {
	return nil, nil
}

func (m *mockTradernetClient) GetCashBalances() ([]domain.BrokerCashBalance, error) {
	return nil, nil
}

func (m *mockTradernetClient) GetExecutedTrades(limit int) ([]domain.BrokerTrade, error) {
	return nil, nil
}

func (m *mockTradernetClient) GetPendingOrders() ([]domain.BrokerPendingOrder, error) {
	return nil, nil
}

func (m *mockTradernetClient) GetQuote(symbol string) (*domain.BrokerQuote, error) {
	return nil, nil
}

func (m *mockTradernetClient) FindSymbol(symbol string, exchange *string) ([]domain.BrokerSecurityInfo, error) {
	return nil, nil
}

func (m *mockTradernetClient) GetLevel1Quote(symbol string) (*domain.BrokerOrderBook, error) {
	return nil, nil
}

func (m *mockTradernetClient) GetQuotes(symbols []string) (map[string]*domain.BrokerQuote, error) {
	result := make(map[string]*domain.BrokerQuote)
	for _, symbol := range symbols {
		// If quotes map is explicitly set (even if empty), use it exclusively
		if m.quotes != nil {
			if quote, ok := m.quotes[symbol]; ok {
				result[symbol] = quote
			}
			// If quotes map exists but symbol not found, don't return default
			continue
		}
		// Default (when quotes is nil): return a reasonable quote
		result[symbol] = &domain.BrokerQuote{
			Symbol: symbol,
			Price:  150.0, // Default price matching test expectations
		}
	}
	return result, nil
}

func (m *mockTradernetClient) GetHistoricalPrices(symbol string, start, end int64, timeframeSeconds int) ([]domain.BrokerOHLCV, error) {
	return []domain.BrokerOHLCV{}, nil
}

func (m *mockTradernetClient) GetFXRates(baseCurrency string, currencies []string) (map[string]float64, error) {
	return nil, nil
}

func (m *mockTradernetClient) GetAllCashFlows(limit int) ([]domain.BrokerCashFlow, error) {
	return nil, nil
}

func (m *mockTradernetClient) GetCashMovements() (*domain.BrokerCashMovement, error) {
	return nil, nil
}

func (m *mockTradernetClient) HealthCheck() (*domain.BrokerHealthResult, error) {
	return &domain.BrokerHealthResult{Connected: m.connected}, nil
}

func (m *mockTradernetClient) SetCredentials(apiKey, apiSecret string) {
}

func (m *mockTradernetClient) PlaceOrder(symbol, side string, quantity, limitPrice float64) (*domain.BrokerOrderResult, error) {
	if m.placeOrderErr != nil {
		return nil, m.placeOrderErr
	}
	if m.placeOrderResp != nil {
		return m.placeOrderResp, nil
	}
	// Default successful response
	return &domain.BrokerOrderResult{
		OrderID:  "ORDER-" + symbol,
		Symbol:   symbol,
		Side:     side,
		Quantity: quantity,
		Price:    100.0, // Default price
	}, nil
}

func (m *mockTradernetClient) GetSecurityMetadata(symbol string) (*domain.BrokerSecurityInfo, error) {
	return nil, nil
}

// Mock Trade Repository for testing

type mockTradeRepository struct {
	createErr error
	trades    []trading.Trade
}

func newMockTradeRepository() *mockTradeRepository {
	return &mockTradeRepository{
		trades: make([]trading.Trade, 0),
	}
}

func (m *mockTradeRepository) Create(trade trading.Trade) error {
	if m.createErr != nil {
		return m.createErr
	}
	m.trades = append(m.trades, trade)
	return nil
}

func (m *mockTradeRepository) CreatePendingRetry(retry trading.PendingRetry) error {
	return nil
}

func (m *mockTradeRepository) GetPendingRetries() ([]trading.PendingRetry, error) {
	return nil, nil
}

func (m *mockTradeRepository) UpdateRetryStatus(id int64, status string) error {
	return nil
}

func (m *mockTradeRepository) IncrementRetryAttempt(id int64) error {
	return nil
}

// Mock Planner Config Repository for testing
type mockPlannerConfigRepo struct {
	config *planningdomain.PlannerConfiguration
	err    error
}

func newMockPlannerConfigRepo(fixedCost, percentCost float64) *mockPlannerConfigRepo {
	return &mockPlannerConfigRepo{
		config: &planningdomain.PlannerConfiguration{
			TransactionCostFixed:   fixedCost,
			TransactionCostPercent: percentCost,
		},
	}
}

func (m *mockPlannerConfigRepo) GetDefaultConfig() (*planningdomain.PlannerConfiguration, error) {
	if m.err != nil {
		return nil, m.err
	}
	return m.config, nil
}

// Test ExecuteTrades orchestration

func TestExecuteTrades_TradernetNotConnected(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	mockClient := newMockTradernetClient(false) // Not connected

	service := &TradeExecutionService{
		brokerClient: mockClient,
		log:          log,
	}

	recommendations := []TradeRecommendation{
		{
			Symbol:         "AAPL",
			Side:           "BUY",
			Quantity:       10,
			EstimatedPrice: 150.0,
			Currency:       "EUR",
		},
		{
			Symbol:         "MSFT",
			Side:           "BUY",
			Quantity:       5,
			EstimatedPrice: 300.0,
			Currency:       "EUR",
		},
	}

	results := service.ExecuteTrades(recommendations)

	// Both trades should have error status
	if len(results) != 2 {
		t.Fatalf("Expected 2 results, got %d", len(results))
	}

	for _, result := range results {
		if result.Status != "error" {
			t.Errorf("Expected status 'error', got '%s'", result.Status)
		}
		if result.Error == nil {
			t.Error("Expected error message, got nil")
		} else if *result.Error != "Tradernet not connected" {
			t.Errorf("Expected 'Tradernet not connected', got '%s'", *result.Error)
		}
	}
}

func TestExecuteTrades_SingleBuySuccess(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	mockClient := newMockTradernetClient(true)
	mockTradeRepo := newMockTradeRepository()
	cashManager := newMockCashManager(map[string]float64{"EUR": 2000.0})
	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		brokerClient:    mockClient,
		tradeRepo:       mockTradeRepo,
		cashManager:     cashManager,
		exchangeService: exchangeService,
		log:             log,
	}

	recommendations := []TradeRecommendation{
		{
			Symbol:         "AAPL",
			Side:           "BUY",
			Quantity:       10,
			EstimatedPrice: 150.0,
			Currency:       "EUR",
			Reason:         "test purchase",
		},
	}

	results := service.ExecuteTrades(recommendations)

	if len(results) != 1 {
		t.Fatalf("Expected 1 result, got %d", len(results))
	}

	result := results[0]
	if result.Status != "success" {
		t.Errorf("Expected status 'success', got '%s'", result.Status)
	}
	if result.Symbol != "AAPL" {
		t.Errorf("Expected symbol 'AAPL', got '%s'", result.Symbol)
	}
	if result.Error != nil {
		t.Errorf("Expected no error, got: %v", *result.Error)
	}

	// Verify trade was recorded
	if len(mockTradeRepo.trades) != 1 {
		t.Errorf("Expected 1 trade to be recorded, got %d", len(mockTradeRepo.trades))
	}
}

func TestExecuteTrades_SingleSellSuccess(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	mockClient := newMockTradernetClient(true)
	mockTradeRepo := newMockTradeRepository()

	service := &TradeExecutionService{
		brokerClient: mockClient,
		tradeRepo:    mockTradeRepo,
		log:          log,
	}

	recommendations := []TradeRecommendation{
		{
			Symbol:         "AAPL",
			Side:           "SELL",
			Quantity:       10,
			EstimatedPrice: 150.0,
			Currency:       "EUR",
			Reason:         "test sale",
		},
	}

	results := service.ExecuteTrades(recommendations)

	if len(results) != 1 {
		t.Fatalf("Expected 1 result, got %d", len(results))
	}

	result := results[0]
	if result.Status != "success" {
		t.Errorf("Expected status 'success', got '%s'", result.Status)
	}
	if result.Symbol != "AAPL" {
		t.Errorf("Expected symbol 'AAPL', got '%s'", result.Symbol)
	}

	// SELL orders skip cash validation, should always execute
	if result.Error != nil {
		t.Errorf("Expected no error, got: %v", *result.Error)
	}
}

func TestExecuteTrades_BuyBlockedByNegativeBalance(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	mockClient := newMockTradernetClient(true)
	cashManager := newMockCashManager(map[string]float64{"EUR": -100.0}) // Negative balance
	// Use the balance-checking mock that actually validates balance
	exchangeService := newMockCurrencyExchangeServiceWithEnsureBalance(
		map[string]float64{},
		cashManager,
	)
	mockTradeRepo := newMockTradeRepository()

	service := &TradeExecutionService{
		brokerClient:    mockClient,
		cashManager:     cashManager,
		exchangeService: exchangeService,
		tradeRepo:       mockTradeRepo,
		log:             log,
	}

	recommendations := []TradeRecommendation{
		{
			Symbol:         "AAPL",
			Side:           "BUY",
			Quantity:       10,
			EstimatedPrice: 150.0,
			Currency:       "EUR",
		},
	}

	results := service.ExecuteTrades(recommendations)

	if len(results) != 1 {
		t.Fatalf("Expected 1 result, got %d", len(results))
	}

	result := results[0]
	if result.Status != "blocked" {
		t.Errorf("Expected status 'blocked', got '%s'", result.Status)
	}
	if result.Error == nil {
		t.Error("Expected error message, got nil")
	}
}

func TestExecuteTrades_BuyBlockedByInsufficientFunds(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	mockClient := newMockTradernetClient(true)
	cashManager := newMockCashManager(map[string]float64{"EUR": 500.0}) // Insufficient
	// Use the balance-checking mock that actually validates balance
	exchangeService := newMockCurrencyExchangeServiceWithEnsureBalance(
		map[string]float64{},
		cashManager,
	)
	mockTradeRepo := newMockTradeRepository()

	service := &TradeExecutionService{
		brokerClient:    mockClient,
		cashManager:     cashManager,
		exchangeService: exchangeService,
		tradeRepo:       mockTradeRepo,
		log:             log,
	}

	recommendations := []TradeRecommendation{
		{
			Symbol:         "AAPL",
			Side:           "BUY",
			Quantity:       10,
			EstimatedPrice: 150.0, // 1500 EUR needed + commission
			Currency:       "EUR",
		},
	}

	results := service.ExecuteTrades(recommendations)

	if len(results) != 1 {
		t.Fatalf("Expected 1 result, got %d", len(results))
	}

	result := results[0]
	if result.Status != "blocked" {
		t.Errorf("Expected status 'blocked', got '%s'", result.Status)
	}
}

func TestExecuteTrades_PlaceOrderFailure(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	mockClient := newMockTradernetClient(true)
	mockClient.placeOrderErr = fmt.Errorf("market closed")

	cashManager := newMockCashManager(map[string]float64{"EUR": 2000.0})
	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		brokerClient:    mockClient,
		cashManager:     cashManager,
		exchangeService: exchangeService,
		log:             log,
	}

	recommendations := []TradeRecommendation{
		{
			Symbol:         "AAPL",
			Side:           "BUY",
			Quantity:       10,
			EstimatedPrice: 150.0,
			Currency:       "EUR",
		},
	}

	results := service.ExecuteTrades(recommendations)

	if len(results) != 1 {
		t.Fatalf("Expected 1 result, got %d", len(results))
	}

	result := results[0]
	if result.Status != "error" {
		t.Errorf("Expected status 'error', got '%s'", result.Status)
	}
	if result.Error == nil {
		t.Error("Expected error message, got nil")
	} else if !contains(*result.Error, "market closed") {
		t.Errorf("Expected error to contain 'market closed', got: %s", *result.Error)
	}
}

func TestExecuteTrades_MultipleTrades_MixedResults(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	mockClient := newMockTradernetClient(true)
	mockTradeRepo := newMockTradeRepository()
	cashManager := newMockCashManager(map[string]float64{
		"EUR": 2000.0,  // Enough for AAPL, not for MSFT
		"USD": 10000.0, // Enough for GOOGL
	})
	exchangeService := newMockCurrencyExchangeServiceWithEnsureBalance(map[string]float64{}, cashManager)

	service := &TradeExecutionService{
		brokerClient:    mockClient,
		tradeRepo:       mockTradeRepo,
		cashManager:     cashManager,
		exchangeService: exchangeService,
		log:             log,
	}

	recommendations := []TradeRecommendation{
		{
			Symbol:         "AAPL",
			Side:           "BUY",
			Quantity:       10,
			EstimatedPrice: 150.0, // 1500 + commission ~1505 EUR (should succeed)
			Currency:       "EUR",
		},
		{
			Symbol:         "MSFT",
			Side:           "BUY",
			Quantity:       10,
			EstimatedPrice: 300.0, // 3000 + commission EUR (should fail - insufficient)
			Currency:       "EUR",
		},
		{
			Symbol:         "GOOGL",
			Side:           "BUY",
			Quantity:       10,
			EstimatedPrice: 100.0, // USD (should succeed)
			Currency:       "USD",
		},
		{
			Symbol:         "TSLA",
			Side:           "SELL",
			Quantity:       5,
			EstimatedPrice: 200.0, // SELL always succeeds
			Currency:       "USD",
		},
	}

	results := service.ExecuteTrades(recommendations)

	if len(results) != 4 {
		t.Fatalf("Expected 4 results, got %d", len(results))
	}

	// AAPL should succeed
	if results[0].Symbol != "AAPL" || results[0].Status != "success" {
		t.Errorf("AAPL should succeed, got status: %s", results[0].Status)
	}

	// MSFT should be blocked
	if results[1].Symbol != "MSFT" || results[1].Status != "blocked" {
		t.Errorf("MSFT should be blocked, got status: %s", results[1].Status)
	}

	// GOOGL should succeed
	if results[2].Symbol != "GOOGL" || results[2].Status != "success" {
		t.Errorf("GOOGL should succeed, got status: %s", results[2].Status)
	}

	// TSLA (SELL) should succeed
	if results[3].Symbol != "TSLA" || results[3].Status != "success" {
		t.Errorf("TSLA should succeed, got status: %s", results[3].Status)
	}

	// Only 3 trades should be recorded (AAPL, GOOGL, TSLA - MSFT was blocked)
	if len(mockTradeRepo.trades) != 3 {
		t.Errorf("Expected 3 trades recorded, got %d", len(mockTradeRepo.trades))
	}
}

func TestExecuteTrades_TradeRecordingFailure(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	mockClient := newMockTradernetClient(true)
	mockTradeRepo := newMockTradeRepository()
	mockTradeRepo.createErr = fmt.Errorf("database connection lost")

	cashManager := newMockCashManager(map[string]float64{"EUR": 2000.0})
	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		brokerClient:    mockClient,
		tradeRepo:       mockTradeRepo,
		cashManager:     cashManager,
		exchangeService: exchangeService,
		log:             log,
	}

	recommendations := []TradeRecommendation{
		{
			Symbol:         "AAPL",
			Side:           "BUY",
			Quantity:       10,
			EstimatedPrice: 150.0,
			Currency:       "EUR",
		},
	}

	results := service.ExecuteTrades(recommendations)

	// Trade execution should still succeed even if recording fails
	if len(results) != 1 {
		t.Fatalf("Expected 1 result, got %d", len(results))
	}

	result := results[0]
	if result.Status != "success" {
		t.Errorf("Expected status 'success' (trade went through), got '%s'", result.Status)
	}
}

func TestExecuteTrades_EmptyRecommendations(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	mockClient := newMockTradernetClient(true)

	service := &TradeExecutionService{
		brokerClient: mockClient,
		log:          log,
	}

	recommendations := []TradeRecommendation{}

	results := service.ExecuteTrades(recommendations)

	if len(results) != 0 {
		t.Errorf("Expected 0 results for empty recommendations, got %d", len(results))
	}
}

// Helper function
func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > len(substr) && (s[:len(substr)] == substr || s[len(s)-len(substr):] == substr || findSubstring(s, substr)))
}

func findSubstring(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

// ============================================================================
// Trade Execution Currency Conversion Tests
// ============================================================================

// TestExecuteTrades_ForeignCurrency_AutoConversion tests foreign currency BUY with automatic EUR conversion
func TestExecuteTrades_ForeignCurrency_AutoConversion(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	mockClient := newMockTradernetClient(true)
	mockTradeRepo := newMockTradeRepository()

	// EUR balance only, no HKD
	cashManager := newMockCashManager(map[string]float64{
		"EUR": 10000.0,
		"HKD": 0.0, // No HKD balance
	})

	// Mock exchange service that will convert EUR to HKD
	exchangeService := newMockCurrencyExchangeServiceWithEnsureBalance(
		map[string]float64{
			"EUR:HKD": 9.0, // 1 EUR = 9 HKD
		},
		cashManager,
	)

	service := &TradeExecutionService{
		brokerClient:    mockClient,
		tradeRepo:       mockTradeRepo,
		cashManager:     cashManager,
		exchangeService: exchangeService,
		log:             log,
	}

	// BUY HKD security
	recommendations := []TradeRecommendation{
		{
			Symbol:         "0700.HK",
			Side:           "BUY",
			Quantity:       100,
			EstimatedPrice: 90.0, // HKD
			Currency:       "HKD",
		},
	}

	results := service.ExecuteTrades(recommendations)

	// Verify:
	// 1. Trade succeeded
	assert.Equal(t, "success", results[0].Status, "Trade should succeed")

	// 2. EUR was converted to HKD
	assert.True(t, exchangeService.ensureBalanceCalled, "EnsureBalance should be called")
	assert.Equal(t, "HKD", exchangeService.ensureBalanceCurrency, "Should ensure HKD")

	// 3. Sufficient amount requested (trade + commission + margin)
	// Trade: 100 × 90 = 9000 HKD
	// Commission: 2 EUR * 9 (rate) + 0.2% of 9000 = 18 + 18 = 36 HKD
	// Total: 9000 + 36 = 9036 HKD
	// With 1% margin: 9036 * 1.01 = 9126.36 HKD
	assert.Greater(t, exchangeService.ensureBalanceAmount, 9000.0, "Should ensure enough for trade")
	assert.Less(t, exchangeService.ensureBalanceAmount, 10000.0, "Amount should be reasonable")
}

// TestExecuteTrades_EUR_NoConversionNeeded tests EUR trade does not trigger currency conversion
func TestExecuteTrades_EUR_NoConversionNeeded(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	mockClient := newMockTradernetClient(true)
	mockTradeRepo := newMockTradeRepository()
	cashManager := newMockCashManager(map[string]float64{"EUR": 10000.0})
	exchangeService := newMockCurrencyExchangeServiceWithEnsureBalance(
		map[string]float64{},
		cashManager,
	)

	service := &TradeExecutionService{
		brokerClient:    mockClient,
		tradeRepo:       mockTradeRepo,
		cashManager:     cashManager,
		exchangeService: exchangeService,
		log:             log,
	}

	recommendations := []TradeRecommendation{
		{
			Symbol:         "VWS.AS",
			Side:           "BUY",
			Quantity:       100,
			EstimatedPrice: 42.5,
			Currency:       "EUR",
		},
	}

	results := service.ExecuteTrades(recommendations)

	assert.Equal(t, "success", results[0].Status)
	// EnsureBalance is still called for EUR to validate we have enough
	assert.True(t, exchangeService.ensureBalanceCalled, "EnsureBalance should be called to validate EUR balance")
	assert.Equal(t, "EUR", exchangeService.ensureBalanceCurrency, "Should validate EUR balance")
}

// TestExecuteTrades_InsufficientEUR_Blocked tests insufficient EUR blocks foreign currency trade
func TestExecuteTrades_InsufficientEUR_Blocked(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	mockClient := newMockTradernetClient(true)

	// Only 100 EUR, not enough to convert for HKD trade
	cashManager := newMockCashManager(map[string]float64{
		"EUR": 100.0,
		"HKD": 0.0,
	})

	exchangeService := newMockCurrencyExchangeServiceWithEnsureBalance(
		map[string]float64{
			"EUR:HKD": 9.0,
		},
		cashManager,
	)

	service := &TradeExecutionService{
		brokerClient:    mockClient,
		cashManager:     cashManager,
		exchangeService: exchangeService,
		log:             log,
	}

	// Large HKD trade requiring ~10,000 EUR worth
	recommendations := []TradeRecommendation{
		{
			Symbol:         "0700.HK",
			Side:           "BUY",
			Quantity:       1000,
			EstimatedPrice: 90.0, // 90,000 HKD needed (~10,000 EUR)
			Currency:       "HKD",
		},
	}

	results := service.ExecuteTrades(recommendations)

	// Should be blocked
	assert.Equal(t, "blocked", results[0].Status, "Trade should be blocked due to insufficient EUR")
	assert.NotNil(t, results[0].Error)
}

// TestExecuteTrades_SELL_NoConversionNeeded tests SELL orders do not trigger currency conversion
func TestExecuteTrades_SELL_NoConversionNeeded(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	mockClient := newMockTradernetClient(true)
	mockTradeRepo := newMockTradeRepository()
	cashManager := newMockCashManager(map[string]float64{})
	exchangeService := newMockCurrencyExchangeServiceWithEnsureBalance(
		map[string]float64{},
		cashManager,
	)

	service := &TradeExecutionService{
		brokerClient:    mockClient,
		tradeRepo:       mockTradeRepo,
		exchangeService: exchangeService,
		log:             log,
	}

	recommendations := []TradeRecommendation{
		{
			Symbol:         "0700.HK",
			Side:           "SELL",
			Quantity:       100,
			EstimatedPrice: 90.0,
			Currency:       "HKD",
		},
	}

	results := service.ExecuteTrades(recommendations)

	assert.Equal(t, "success", results[0].Status)
	// EnsureBalance should NOT be called for SELL orders
	assert.False(t, exchangeService.ensureBalanceCalled, "EnsureBalance should NOT be called for SELL")
}

// ============================================================================
// Configurable Trading Fees Tests
// ============================================================================

// TestCalculateCommission_ConfigurableFees tests commission calculation with custom fees from planner config
func TestCalculateCommission_ConfigurableFees(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// Mock planner config repo with custom fees
	mockConfigRepo := newMockPlannerConfigRepo(3.0, 0.0025) // 3 EUR fixed, 0.25% variable

	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		exchangeService:   exchangeService,
		plannerConfigRepo: mockConfigRepo,
		log:               log,
	}

	// Trade value: 1000 EUR
	// Expected commission:
	// - Fixed: 3.0 EUR
	// - Variable: 1000 * 0.0025 = 2.5 EUR
	// - Total: 5.5 EUR
	commission, err := service.calculateCommission(1000.0, "EUR")

	assert.NoError(t, err)
	assert.Equal(t, 5.5, commission, "Commission should use configured fees")
}

// TestCalculateCommission_DefaultFallback tests commission calculation with default fees when settings unavailable
func TestCalculateCommission_DefaultFallback(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// No settings service
	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		exchangeService: exchangeService,
		settingsService: nil, // No settings
		log:             log,
	}

	// Should use defaults: 2 EUR + 0.2%
	// Trade value: 1000 EUR
	// Expected commission:
	// - Fixed: 2.0 EUR
	// - Variable: 1000 * 0.002 = 2.0 EUR
	// - Total: 4.0 EUR
	commission, err := service.calculateCommission(1000.0, "EUR")

	assert.NoError(t, err)
	assert.Equal(t, 4.0, commission, "Should use default fees")
}

// TestCalculateCommission_ConfigurableFees_USD tests commission calculation with custom fees for foreign currency
func TestCalculateCommission_ConfigurableFees_USD(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// Mock planner config repo with custom fees
	mockConfigRepo := newMockPlannerConfigRepo(5.0, 0.003) // 5 EUR fixed, 0.3% variable

	// EUR:USD rate = 1.1 (1 EUR = 1.1 USD)
	exchangeService := newMockCurrencyExchangeService(map[string]float64{
		"EUR:USD": 1.1,
	})

	service := &TradeExecutionService{
		exchangeService:   exchangeService,
		plannerConfigRepo: mockConfigRepo,
		log:               log,
	}

	// Trade value: 1000 USD
	// Expected commission:
	// - Fixed: 5.0 EUR * 1.1 = 5.5 USD
	// - Variable: 1000 * 0.003 = 3.0 USD
	// - Total: 8.5 USD
	commission, err := service.calculateCommission(1000.0, "USD")

	assert.NoError(t, err)
	assert.Equal(t, 8.5, commission, "Commission should use configured fees with currency conversion")
}

// TestCalculateCommission_PartialSettings tests graceful fallback when only fixed cost is custom
func TestCalculateCommission_PartialSettings(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// Mock planner config repo with custom fixed but default variable
	mockConfigRepo := newMockPlannerConfigRepo(3.0, 0.002) // 3 EUR fixed (custom), 0.2% variable (default)

	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		exchangeService:   exchangeService,
		plannerConfigRepo: mockConfigRepo,
		log:               log,
	}

	// Trade value: 1000 EUR
	// Expected commission:
	// - Fixed: 3.0 EUR (configured)
	// - Variable: 1000 * 0.002 = 2.0 EUR (default)
	// - Total: 5.0 EUR
	commission, err := service.calculateCommission(1000.0, "EUR")

	assert.NoError(t, err)
	assert.Equal(t, 5.0, commission, "Should mix configured and default values")
}
