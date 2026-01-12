package tradernet

import (
	"errors"
	"testing"
	"time"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

// mockSDKClient is a mock implementation of SDKClient for testing
type mockSDKClient struct {
	accountSummaryResult       interface{}
	accountSummaryError        error
	buyResult                  interface{}
	buyError                   error
	sellResult                 interface{}
	sellError                  error
	getPlacedResult            interface{}
	getPlacedError             error
	getClientCpsHistoryResult  interface{}
	getClientCpsHistoryError   error
	corporateActionsResult     interface{}
	corporateActionsError      error
	getTradesHistoryResult     interface{}
	getTradesHistoryError      error
	findSymbolResult           interface{}
	findSymbolError            error
	getQuotesResult            interface{}
	getQuotesError             error
	getLevel1QuoteResult       interface{}
	getLevel1QuoteError        error
	getCandlesResult           interface{}
	getCandlesError            error
	getCrossRatesForDateResult interface{}
	getCrossRatesForDateError  error
	userInfoResult             interface{}
	userInfoError              error
	lastLimitPrice             float64 // Track limit price passed to Buy/Sell
}

func (m *mockSDKClient) AccountSummary() (interface{}, error) {
	return m.accountSummaryResult, m.accountSummaryError
}

func (m *mockSDKClient) Buy(symbol string, quantity int, price float64, duration string, useMargin bool, customOrderID *int) (interface{}, error) {
	m.lastLimitPrice = price
	return m.buyResult, m.buyError
}

func (m *mockSDKClient) Sell(symbol string, quantity int, price float64, duration string, useMargin bool, customOrderID *int) (interface{}, error) {
	m.lastLimitPrice = price
	return m.sellResult, m.sellError
}

func (m *mockSDKClient) GetPlaced(active bool) (interface{}, error) {
	return m.getPlacedResult, m.getPlacedError
}

func (m *mockSDKClient) GetClientCpsHistory(dateFrom, dateTo string, cpsDocID, id, limit, offset, cpsStatus *int) (interface{}, error) {
	return m.getClientCpsHistoryResult, m.getClientCpsHistoryError
}

func (m *mockSDKClient) CorporateActions(reception int) (interface{}, error) {
	return m.corporateActionsResult, m.corporateActionsError
}

func (m *mockSDKClient) GetTradesHistory(start, end string, tradeID, limit, reception *int, symbol, currency *string) (interface{}, error) {
	return m.getTradesHistoryResult, m.getTradesHistoryError
}

func (m *mockSDKClient) FindSymbol(symbol string, exchange *string) (interface{}, error) {
	return m.findSymbolResult, m.findSymbolError
}

func (m *mockSDKClient) GetQuotes(symbols []string) (interface{}, error) {
	return m.getQuotesResult, m.getQuotesError
}

func (m *mockSDKClient) GetLevel1Quote(symbol string) (interface{}, error) {
	return m.getLevel1QuoteResult, m.getLevel1QuoteError
}

func (m *mockSDKClient) GetCandles(symbol string, start, end time.Time, timeframeSeconds int) (interface{}, error) {
	return m.getCandlesResult, m.getCandlesError
}

func (m *mockSDKClient) GetCrossRatesForDate(baseCurrency string, currencies []string, date *string) (interface{}, error) {
	return m.getCrossRatesForDateResult, m.getCrossRatesForDateError
}

func (m *mockSDKClient) UserInfo() (interface{}, error) {
	return m.userInfoResult, m.userInfoError
}

func (m *mockSDKClient) Close() {
	// No-op for mock
}

// TestClient_GetPortfolio tests GetPortfolio() using SDK
func TestClient_GetPortfolio(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockSDK := &mockSDKClient{
		accountSummaryResult: map[string]interface{}{
			"result": map[string]interface{}{
				"ps": map[string]interface{}{
					"pos": []interface{}{
						map[string]interface{}{
							"i":            "AAPL.US",
							"q":            float64(10),
							"bal_price_a":  float64(150.5),
							"mkt_price":    float64(155.0),
							"profit_close": float64(45.0),
							"curr":         "USD",
						},
					},
				},
			},
		},
	}

	client := &Client{
		sdkClient: mockSDK,
		log:       log,
	}

	positions, err := client.GetPortfolio()

	assert.NoError(t, err)
	assert.Len(t, positions, 1)
	assert.Equal(t, "AAPL.US", positions[0].Symbol)
	assert.Equal(t, float64(10), positions[0].Quantity)
	assert.Equal(t, float64(150.5), positions[0].AvgPrice)
	assert.Equal(t, float64(155.0), positions[0].CurrentPrice)
}

// TestClient_GetPortfolio_SDKError tests GetPortfolio() error handling
func TestClient_GetPortfolio_SDKError(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockSDK := &mockSDKClient{
		accountSummaryError: errors.New("SDK error"),
	}

	client := &Client{
		sdkClient: mockSDK,
		log:       log,
	}

	positions, err := client.GetPortfolio()

	assert.Error(t, err)
	assert.Nil(t, positions)
}

// TestClient_GetCashBalances tests GetCashBalances() using SDK
func TestClient_GetCashBalances(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockSDK := &mockSDKClient{
		accountSummaryResult: map[string]interface{}{
			"result": map[string]interface{}{
				"ps": map[string]interface{}{
					"acc": []interface{}{
						map[string]interface{}{
							"curr": "USD",
							"s":    float64(1000.50),
						},
					},
				},
			},
		},
	}

	client := &Client{
		sdkClient: mockSDK,
		log:       log,
	}

	balances, err := client.GetCashBalances()

	assert.NoError(t, err)
	assert.Len(t, balances, 1)
	assert.Equal(t, "USD", balances[0].Currency)
	assert.Equal(t, float64(1000.50), balances[0].Amount)
}

// TestClient_PlaceOrder_Buy tests PlaceOrder() with BUY side using SDK
func TestClient_PlaceOrder_Buy(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockSDK := &mockSDKClient{
		buyResult: map[string]interface{}{
			"id":    float64(12345),
			"price": float64(150.5),
		},
	}

	client := &Client{
		sdkClient: mockSDK,
		log:       log,
	}

	orderResult, err := client.PlaceOrder("AAPL.US", "BUY", 10.0, 0.0) // Market order

	assert.NoError(t, err)
	assert.NotNil(t, orderResult)
	assert.Equal(t, "12345", orderResult.OrderID)
	assert.Equal(t, "AAPL.US", orderResult.Symbol)
	assert.Equal(t, "BUY", orderResult.Side)
	assert.Equal(t, float64(10), orderResult.Quantity)
	assert.Equal(t, float64(150.5), orderResult.Price)
}

// TestClient_PlaceOrder_Sell tests PlaceOrder() with SELL side using SDK
func TestClient_PlaceOrder_Sell(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockSDK := &mockSDKClient{
		sellResult: map[string]interface{}{
			"id":    float64(67890),
			"price": float64(200.0),
		},
	}

	client := &Client{
		sdkClient: mockSDK,
		log:       log,
	}

	orderResult, err := client.PlaceOrder("TSLA.US", "SELL", 5.0, 0.0) // Market order

	assert.NoError(t, err)
	assert.NotNil(t, orderResult)
	assert.Equal(t, "67890", orderResult.OrderID)
	assert.Equal(t, "TSLA.US", orderResult.Symbol)
	assert.Equal(t, "SELL", orderResult.Side)
	assert.Equal(t, float64(5), orderResult.Quantity)
	assert.Equal(t, float64(200.0), orderResult.Price)
}

// TestClient_GetPendingOrders tests GetPendingOrders() using SDK
func TestClient_GetPendingOrders(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockSDK := &mockSDKClient{
		getPlacedResult: map[string]interface{}{
			"result": []interface{}{
				map[string]interface{}{
					"id":   float64(111),
					"i":    "AAPL.US",
					"q":    float64(10),
					"p":    float64(150.5),
					"curr": "USD",
				},
			},
		},
	}

	client := &Client{
		sdkClient: mockSDK,
		log:       log,
	}

	orders, err := client.GetPendingOrders()

	assert.NoError(t, err)
	assert.Len(t, orders, 1)
	assert.Equal(t, "111", orders[0].OrderID)
	assert.Equal(t, "AAPL.US", orders[0].Symbol)
}

// TestClient_GetCashMovements tests GetCashMovements() using SDK
func TestClient_GetCashMovements(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockSDK := &mockSDKClient{
		getClientCpsHistoryResult: map[string]interface{}{
			"result": []interface{}{
				map[string]interface{}{
					"id":     float64(1),
					"type":   "withdrawal",
					"amount": float64(100.0),
					"date":   "2024-01-15",
				},
			},
		},
	}

	client := &Client{
		sdkClient: mockSDK,
		log:       log,
	}

	result, err := client.GetCashMovements()

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Len(t, result.Withdrawals, 1)
}

// TestClient_GetAllCashFlows tests GetAllCashFlows() using SDK
func TestClient_GetAllCashFlows(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockSDK := &mockSDKClient{
		getClientCpsHistoryResult: map[string]interface{}{
			"cps": []interface{}{
				map[string]interface{}{
					"id":               "tx1",
					"transaction_id":   "tx1",
					"type_doc_id":      float64(1),
					"type":             "dividend",
					"transaction_type": "dividend",
					"dt":               "2024-01-15T10:00:00Z",
					"date":             "2024-01-15",
					"sm":               "50.0", // Tradernet returns amounts as strings
					"amount":           "50.0",
					"curr":             "USD",
					"currency":         "USD",
				},
			},
			"total": "50.0",
		},
	}

	client := &Client{
		sdkClient: mockSDK,
		log:       log,
	}

	transactions, err := client.GetAllCashFlows(100)

	assert.NoError(t, err)
	assert.Len(t, transactions, 1)
	assert.Equal(t, "tx1", transactions[0].ID)
}

// TestClient_GetExecutedTrades tests GetExecutedTrades() using SDK
func TestClient_GetExecutedTrades(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockSDK := &mockSDKClient{
		getTradesHistoryResult: map[string]interface{}{
			"trades": map[string]interface{}{
				"trade": []interface{}{
					map[string]interface{}{
						"order_id": "111",
						"instr_nm": "AAPL.US",
						"q":        float64(10),
						"p":        "150.5", // Tradernet returns price as string
						"date":     "2024-01-15T10:00:00Z",
						"type":     "1", // 1 = BUY, 2 = SELL
					},
				},
				"max_trade_id": []interface{}{
					map[string]interface{}{
						"@text": "111",
					},
				},
			},
		},
	}

	client := &Client{
		sdkClient: mockSDK,
		log:       log,
	}

	trades, err := client.GetExecutedTrades(100)

	assert.NoError(t, err)
	assert.Len(t, trades, 1)
	assert.Equal(t, "111", trades[0].OrderID)
	assert.Equal(t, "AAPL.US", trades[0].Symbol)
	assert.Equal(t, 150.5, trades[0].Price)
}

// TestClient_FindSymbol tests FindSymbol() using SDK
func TestClient_FindSymbol(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockSDK := &mockSDKClient{
		findSymbolResult: map[string]interface{}{
			"result": []interface{}{
				map[string]interface{}{
					"symbol":   "AAPL.US",
					"name":     "Apple Inc.",
					"isin":     "US0378331005",
					"currency": "USD",
				},
			},
		},
	}

	client := &Client{
		sdkClient: mockSDK,
		log:       log,
	}

	securities, err := client.FindSymbol("AAPL", nil)

	assert.NoError(t, err)
	assert.Len(t, securities, 1)
	assert.Equal(t, "AAPL.US", securities[0].Symbol)
}

// TestClient_GetQuote tests GetQuote() using SDK
func TestClient_GetQuote(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockSDK := &mockSDKClient{
		getQuotesResult: map[string]interface{}{
			"result": map[string]interface{}{
				"AAPL.US": map[string]interface{}{
					"p":          float64(150.5),
					"change":     float64(2.5),
					"change_pct": float64(1.69),
					"volume":     float64(1000000),
					"timestamp":  "2024-01-15T10:00:00Z",
				},
			},
		},
	}

	client := &Client{
		sdkClient: mockSDK,
		log:       log,
	}

	quote, err := client.GetQuote("AAPL.US")

	assert.NoError(t, err)
	assert.NotNil(t, quote)
	assert.Equal(t, "AAPL.US", quote.Symbol)
	assert.Equal(t, float64(150.5), quote.Price)
}

// TestClient_HealthCheck tests HealthCheck() using SDK UserInfo()
func TestClient_HealthCheck(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockSDK := &mockSDKClient{
		userInfoResult: map[string]interface{}{
			"result": map[string]interface{}{
				"id":    float64(123),
				"login": "testuser",
			},
		},
	}

	client := &Client{
		sdkClient: mockSDK,
		log:       log,
	}

	result, err := client.HealthCheck()

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.True(t, result.Connected)
}

// TestClient_HealthCheck_Error tests HealthCheck() error handling
func TestClient_HealthCheck_Error(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockSDK := &mockSDKClient{
		userInfoError: errors.New("SDK error"),
	}

	client := &Client{
		sdkClient: mockSDK,
		log:       log,
	}

	result, err := client.HealthCheck()

	assert.NoError(t, err) // HealthCheck returns result, not error
	assert.NotNil(t, result)
	assert.False(t, result.Connected)
}
