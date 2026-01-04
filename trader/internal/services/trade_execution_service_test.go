package services

import (
	"fmt"
	"testing"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/modules/trading"
	"github.com/aristath/arduino-trader/pkg/logger"
)

// Mock implementations for testing

type mockBalanceService struct {
	balances map[string]float64 // currency -> balance
}

func newMockBalanceService(balances map[string]float64) *mockBalanceService {
	return &mockBalanceService{
		balances: balances,
	}
}

func (m *mockBalanceService) GetBalanceAmount(bucketID string, currency string) (float64, error) {
	if balance, ok := m.balances[currency]; ok {
		return balance, nil
	}
	return 0.0, nil
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

// Test validateBuyCashBalance

func TestValidateBuyCashBalance_AlreadyNegative(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// Balance is negative
	balanceService := newMockBalanceService(map[string]float64{
		"EUR": -100.0,
	})

	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		balanceService:  balanceService,
		exchangeService: exchangeService,
		log:             log,
	}

	rec := TradeRecommendation{
		Symbol:         "AAPL",
		Side:           "BUY",
		Quantity:       10,
		EstimatedPrice: 150.0,
		Currency:       "EUR",
	}

	result := service.validateBuyCashBalance(rec)

	if result == nil {
		t.Fatal("Expected validation to fail, but it passed")
	}

	if result.Status != "blocked" {
		t.Errorf("Expected status 'blocked', got '%s'", result.Status)
	}

	if result.Error == nil {
		t.Error("Expected error message, got nil")
	} else if *result.Error != "Negative EUR balance (-100.00 EUR)" {
		t.Errorf("Unexpected error message: %s", *result.Error)
	}
}

func TestValidateBuyCashBalance_InsufficientFunds(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// Balance is 1000 EUR, but trade needs more
	balanceService := newMockBalanceService(map[string]float64{
		"EUR": 1000.0,
	})

	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		balanceService:  balanceService,
		exchangeService: exchangeService,
		log:             log,
	}

	// Trade value: 10 * 150 = 1500 EUR
	// Commission: 2 + (1500 * 0.002) = 2 + 3 = 5 EUR
	// Total needed: 1505 EUR
	// Available: 1000 EUR
	// Should be blocked
	rec := TradeRecommendation{
		Symbol:         "AAPL",
		Side:           "BUY",
		Quantity:       10,
		EstimatedPrice: 150.0,
		Currency:       "EUR",
	}

	result := service.validateBuyCashBalance(rec)

	if result == nil {
		t.Fatal("Expected validation to fail, but it passed")
	}

	if result.Status != "blocked" {
		t.Errorf("Expected status 'blocked', got '%s'", result.Status)
	}

	if result.Error == nil {
		t.Error("Expected error message, got nil")
	} else if *result.Error != "Insufficient EUR balance (need 1505.00, have 1000.00)" {
		t.Errorf("Unexpected error message: %s", *result.Error)
	}
}

func TestValidateBuyCashBalance_SufficientFunds(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// Balance is 2000 EUR, enough for the trade
	balanceService := newMockBalanceService(map[string]float64{
		"EUR": 2000.0,
	})

	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		balanceService:  balanceService,
		exchangeService: exchangeService,
		log:             log,
	}

	// Trade value: 10 * 150 = 1500 EUR
	// Commission: 2 + (1500 * 0.002) = 2 + 3 = 5 EUR
	// Total needed: 1505 EUR
	// Available: 2000 EUR
	// Should pass
	rec := TradeRecommendation{
		Symbol:         "AAPL",
		Side:           "BUY",
		Quantity:       10,
		EstimatedPrice: 150.0,
		Currency:       "EUR",
	}

	result := service.validateBuyCashBalance(rec)

	if result != nil {
		t.Errorf("Expected validation to pass, but got error: %v", *result.Error)
	}
}

func TestValidateBuyCashBalance_EdgeCase_ExactBalance(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// Balance is exactly what's needed
	balanceService := newMockBalanceService(map[string]float64{
		"EUR": 1505.0,
	})

	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		balanceService:  balanceService,
		exchangeService: exchangeService,
		log:             log,
	}

	// Trade value: 10 * 150 = 1500 EUR
	// Commission: 2 + (1500 * 0.002) = 2 + 3 = 5 EUR
	// Total needed: 1505 EUR
	// Available: 1505 EUR (exact match)
	// Should pass
	rec := TradeRecommendation{
		Symbol:         "AAPL",
		Side:           "BUY",
		Quantity:       10,
		EstimatedPrice: 150.0,
		Currency:       "EUR",
	}

	result := service.validateBuyCashBalance(rec)

	if result != nil {
		t.Errorf("Expected validation to pass with exact balance, but got error: %v", *result.Error)
	}
}

func TestValidateBuyCashBalance_SmallTrade(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// Small balance but trade is even smaller
	balanceService := newMockBalanceService(map[string]float64{
		"EUR": 50.0,
	})

	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		balanceService:  balanceService,
		exchangeService: exchangeService,
		log:             log,
	}

	// Trade value: 1 * 10 = 10 EUR
	// Commission: 2 + (10 * 0.002) = 2 + 0.02 = 2.02 EUR
	// Total needed: 12.02 EUR
	// Available: 50 EUR
	// Should pass
	rec := TradeRecommendation{
		Symbol:         "AAPL",
		Side:           "BUY",
		Quantity:       1,
		EstimatedPrice: 10.0,
		Currency:       "EUR",
	}

	result := service.validateBuyCashBalance(rec)

	if result != nil {
		t.Errorf("Expected validation to pass, but got error: %v", *result.Error)
	}
}

// Mock Tradernet Client for testing

type mockTradernetClient struct {
	connected      bool
	placeOrderErr  error
	placeOrderResp *tradernet.OrderResult
}

func newMockTradernetClient(connected bool) *mockTradernetClient {
	return &mockTradernetClient{
		connected: connected,
	}
}

func (m *mockTradernetClient) IsConnected() bool {
	return m.connected
}

func (m *mockTradernetClient) PlaceOrder(symbol, side string, quantity float64) (*tradernet.OrderResult, error) {
	if m.placeOrderErr != nil {
		return nil, m.placeOrderErr
	}
	if m.placeOrderResp != nil {
		return m.placeOrderResp, nil
	}
	// Default successful response
	return &tradernet.OrderResult{
		OrderID:  "ORDER-" + symbol,
		Symbol:   symbol,
		Side:     side,
		Quantity: quantity,
		Price:    100.0, // Default price
	}, nil
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

// Test ExecuteTrades orchestration

func TestExecuteTrades_TradernetNotConnected(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	mockClient := newMockTradernetClient(false) // Not connected

	service := &TradeExecutionService{
		tradernetClient: mockClient,
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
	balanceService := newMockBalanceService(map[string]float64{"EUR": 2000.0})
	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		tradernetClient: mockClient,
		tradeRepo:       mockTradeRepo,
		balanceService:  balanceService,
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
		tradernetClient: mockClient,
		tradeRepo:       mockTradeRepo,
		log:             log,
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
	balanceService := newMockBalanceService(map[string]float64{"EUR": -100.0}) // Negative balance
	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		tradernetClient: mockClient,
		balanceService:  balanceService,
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
	balanceService := newMockBalanceService(map[string]float64{"EUR": 500.0}) // Insufficient
	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		tradernetClient: mockClient,
		balanceService:  balanceService,
		exchangeService: exchangeService,
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

	balanceService := newMockBalanceService(map[string]float64{"EUR": 2000.0})
	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		tradernetClient: mockClient,
		balanceService:  balanceService,
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
	balanceService := newMockBalanceService(map[string]float64{
		"EUR": 2000.0,  // Enough for AAPL, not for MSFT
		"USD": 10000.0, // Enough for GOOGL
	})
	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		tradernetClient: mockClient,
		tradeRepo:       mockTradeRepo,
		balanceService:  balanceService,
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

	balanceService := newMockBalanceService(map[string]float64{"EUR": 2000.0})
	exchangeService := newMockCurrencyExchangeService(map[string]float64{})

	service := &TradeExecutionService{
		tradernetClient: mockClient,
		tradeRepo:       mockTradeRepo,
		balanceService:  balanceService,
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
		tradernetClient: mockClient,
		log:             log,
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
