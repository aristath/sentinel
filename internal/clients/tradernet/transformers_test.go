package tradernet

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

// TestTransformPositions tests transformation of SDK AccountSummary positions to []Position
func TestTransformPositions(t *testing.T) {
	// Mock SDK AccountSummary response structure
	sdkResult := map[string]interface{}{
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
					map[string]interface{}{
						"i":            "TSLA.US",
						"q":            float64(5),
						"bal_price_a":  float64(200.0),
						"mkt_price":    float64(210.0),
						"profit_close": float64(50.0),
						"curr":         "USD",
					},
				},
			},
		},
	}

	log := zerolog.New(nil).Level(zerolog.Disabled)
	positions, err := transformPositions(sdkResult, log)

	assert.NoError(t, err)
	assert.Len(t, positions, 2)

	// Check first position
	assert.Equal(t, "AAPL.US", positions[0].Symbol)
	assert.Equal(t, float64(10), positions[0].Quantity)
	assert.Equal(t, float64(150.5), positions[0].AvgPrice)
	assert.Equal(t, float64(155.0), positions[0].CurrentPrice)
	assert.Equal(t, float64(45.0), positions[0].UnrealizedPnL)
	assert.Equal(t, "USD", positions[0].Currency)
	assert.Equal(t, float64(1550.0), positions[0].MarketValue) // q * mkt_price

	// Check second position
	assert.Equal(t, "TSLA.US", positions[1].Symbol)
	assert.Equal(t, float64(5), positions[1].Quantity)
	assert.Equal(t, float64(200.0), positions[1].AvgPrice)
	assert.Equal(t, float64(210.0), positions[1].CurrentPrice)
	assert.Equal(t, float64(50.0), positions[1].UnrealizedPnL)
	assert.Equal(t, "USD", positions[1].Currency)
	assert.Equal(t, float64(1050.0), positions[1].MarketValue) // q * mkt_price
}

// TestTransformPositions_EmptyArray tests transformation with empty positions array
func TestTransformPositions_EmptyArray(t *testing.T) {
	sdkResult := map[string]interface{}{
		"result": map[string]interface{}{
			"ps": map[string]interface{}{
				"pos": []interface{}{},
			},
		},
	}

	log := zerolog.New(nil).Level(zerolog.Disabled)
	positions, err := transformPositions(sdkResult, log)

	assert.NoError(t, err)
	assert.Len(t, positions, 0)
}

// TestTransformPositions_MissingFields tests transformation with missing optional fields
func TestTransformPositions_MissingFields(t *testing.T) {
	sdkResult := map[string]interface{}{
		"result": map[string]interface{}{
			"ps": map[string]interface{}{
				"pos": []interface{}{
					map[string]interface{}{
						"i":    "AAPL.US",
						"q":    float64(10),
						"curr": "USD",
						// Missing bal_price_a, mkt_price, profit_close
					},
				},
			},
		},
	}

	log := zerolog.New(nil).Level(zerolog.Disabled)
	positions, err := transformPositions(sdkResult, log)

	assert.NoError(t, err)
	assert.Len(t, positions, 1)
	assert.Equal(t, "AAPL.US", positions[0].Symbol)
	assert.Equal(t, float64(10), positions[0].Quantity)
	assert.Equal(t, float64(0), positions[0].AvgPrice)
	assert.Equal(t, float64(0), positions[0].CurrentPrice)
	assert.Equal(t, float64(0), positions[0].UnrealizedPnL)
}

// TestTransformCashBalances tests transformation of SDK AccountSummary cash accounts to []CashBalance
func TestTransformCashBalances(t *testing.T) {
	sdkResult := map[string]interface{}{
		"result": map[string]interface{}{
			"ps": map[string]interface{}{
				"acc": []interface{}{
					map[string]interface{}{
						"curr": "USD",
						"s":    float64(1000.50),
					},
					map[string]interface{}{
						"curr": "EUR",
						"s":    float64(500.25),
					},
				},
			},
		},
	}

	balances, err := transformCashBalances(sdkResult)

	assert.NoError(t, err)
	assert.Len(t, balances, 2)

	assert.Equal(t, "USD", balances[0].Currency)
	assert.Equal(t, float64(1000.50), balances[0].Amount)

	assert.Equal(t, "EUR", balances[1].Currency)
	assert.Equal(t, float64(500.25), balances[1].Amount)
}

// TestTransformCashBalances_EmptyArray tests transformation with empty cash accounts array
func TestTransformCashBalances_EmptyArray(t *testing.T) {
	sdkResult := map[string]interface{}{
		"result": map[string]interface{}{
			"ps": map[string]interface{}{
				"acc": []interface{}{},
			},
		},
	}

	balances, err := transformCashBalances(sdkResult)

	assert.NoError(t, err)
	assert.Len(t, balances, 0)
}

// TestTransformOrderResult tests transformation of SDK Buy/Sell response to OrderResult
func TestTransformOrderResult(t *testing.T) {
	// Mock SDK Buy response
	sdkResult := map[string]interface{}{
		"id":    float64(12345),
		"price": float64(150.5),
		"p":     float64(150.5), // Alternative field name
	}

	orderResult, err := transformOrderResult(sdkResult, "AAPL.US", "BUY", float64(10))

	assert.NoError(t, err)
	assert.NotNil(t, orderResult)
	assert.Equal(t, "12345", orderResult.OrderID)
	assert.Equal(t, "AAPL.US", orderResult.Symbol)
	assert.Equal(t, "BUY", orderResult.Side)
	assert.Equal(t, float64(10), orderResult.Quantity)
	assert.Equal(t, float64(150.5), orderResult.Price)
}

// TestTransformOrderResult_WithOrderID tests transformation with order_id field
func TestTransformOrderResult_WithOrderID(t *testing.T) {
	sdkResult := map[string]interface{}{
		"order_id": float64(67890),
		"price":    float64(200.0),
	}

	orderResult, err := transformOrderResult(sdkResult, "TSLA.US", "SELL", float64(5))

	assert.NoError(t, err)
	assert.NotNil(t, orderResult)
	assert.Equal(t, "67890", orderResult.OrderID)
	assert.Equal(t, "TSLA.US", orderResult.Symbol)
	assert.Equal(t, "SELL", orderResult.Side)
	assert.Equal(t, float64(5), orderResult.Quantity)
	assert.Equal(t, float64(200.0), orderResult.Price)
}

// TestTransformOrderResult_StringID tests transformation with string order ID
func TestTransformOrderResult_StringID(t *testing.T) {
	sdkResult := map[string]interface{}{
		"id":    "12345",
		"price": float64(150.5),
	}

	orderResult, err := transformOrderResult(sdkResult, "AAPL.US", "BUY", float64(10))

	assert.NoError(t, err)
	assert.NotNil(t, orderResult)
	assert.Equal(t, "12345", orderResult.OrderID)
}

// TestTransformPendingOrders tests transformation of SDK GetPlaced response to []PendingOrder
func TestTransformPendingOrders(t *testing.T) {
	sdkResult := map[string]interface{}{
		"result": []interface{}{
			map[string]interface{}{
				"id":      float64(111),
				"orderId": float64(111), // Alternative field
				"i":       "AAPL.US",
				"q":       float64(10),
				"p":       float64(150.5),
				"curr":    "USD",
			},
			map[string]interface{}{
				"id":   float64(222),
				"i":    "TSLA.US",
				"q":    float64(5),
				"p":    float64(200.0),
				"curr": "USD",
			},
		},
	}

	orders, err := transformPendingOrders(sdkResult)

	assert.NoError(t, err)
	assert.Len(t, orders, 2)

	assert.Equal(t, "111", orders[0].OrderID)
	assert.Equal(t, "AAPL.US", orders[0].Symbol)
	assert.Equal(t, float64(10), orders[0].Quantity)
	assert.Equal(t, float64(150.5), orders[0].Price)
	assert.Equal(t, "USD", orders[0].Currency)

	assert.Equal(t, "222", orders[1].OrderID)
	assert.Equal(t, "TSLA.US", orders[1].Symbol)
	assert.Equal(t, float64(5), orders[1].Quantity)
	assert.Equal(t, float64(200.0), orders[1].Price)
}

// TestTransformPendingOrders_EmptyArray tests transformation with empty orders array
func TestTransformPendingOrders_EmptyArray(t *testing.T) {
	sdkResult := map[string]interface{}{
		"result": []interface{}{},
	}

	orders, err := transformPendingOrders(sdkResult)

	assert.NoError(t, err)
	assert.Len(t, orders, 0)
}

// TestTransformCashMovements tests transformation of SDK GetClientCpsHistory to CashMovementsResponse
func TestTransformCashMovements(t *testing.T) {
	sdkResult := map[string]interface{}{
		"result": []interface{}{
			map[string]interface{}{
				"id":     float64(1),
				"type":   "withdrawal",
				"amount": float64(100.0),
				"date":   "2024-01-15",
			},
			map[string]interface{}{
				"id":     float64(2),
				"type":   "withdrawal",
				"amount": float64(200.0),
				"date":   "2024-01-20",
			},
		},
	}

	result, err := transformCashMovements(sdkResult)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, float64(300.0), result.TotalWithdrawals)
	assert.Len(t, result.Withdrawals, 2)
}

// TestTransformCashFlows tests transformation of SDK responses to []CashFlowTransaction
func TestTransformCashFlows(t *testing.T) {
	sdkResult := map[string]interface{}{
		"cps": []interface{}{
			map[string]interface{}{
				"id":               "tx1",
				"transaction_id":   "tx1",
				"type_doc_id":      float64(1),
				"type":             "dividend",
				"transaction_type": "dividend",
				"dt":               "2024-01-15T10:00:00Z",
				"date":             "2024-01-15",
				"sm":               float64(50.0),
				"amount":           float64(50.0),
				"curr":             "USD",
				"currency":         "USD",
				"sm_eur":           float64(45.0),
				"amount_eur":       float64(45.0),
				"status":           "completed",
				"status_c":         float64(1),
				"description":      "Dividend payment",
				"params":           map[string]interface{}{},
			},
		},
		"total": float64(1),
	}

	transactions, err := transformCashFlows(sdkResult)

	assert.NoError(t, err)
	assert.Len(t, transactions, 1)

	tx := transactions[0]
	assert.Equal(t, "tx1", tx.ID)
	assert.Equal(t, "tx1", tx.TransactionID)
	assert.Equal(t, 1, tx.TypeDocID)
	assert.Equal(t, "dividend", tx.Type)
	assert.Equal(t, float64(50.0), tx.Amount)
	assert.Equal(t, "USD", tx.Currency)
}

// TestTransformTrades tests transformation of SDK GetTradesHistory to []Trade
func TestTransformTrades(t *testing.T) {
	sdkResult := map[string]interface{}{
		"trades": map[string]interface{}{
			"trade": []interface{}{
				map[string]interface{}{
					"order_id": float64(111),
					"id":       float64(111),
					"instr_nm": "AAPL.US",
					"q":        float64(10),
					"p":        float64(150.5),
					"date":     "2024-01-15T10:00:00Z",
					"type":     float64(1), // 1 = Buy, 2 = Sell
				},
			},
			"max_trade_id": []interface{}{
				map[string]interface{}{
					"@text": "111",
				},
			},
		},
	}

	trades, err := transformTrades(sdkResult)

	assert.NoError(t, err)
	assert.Len(t, trades, 1)

	trade := trades[0]
	assert.Equal(t, "111", trade.OrderID)
	assert.Equal(t, "AAPL.US", trade.Symbol)
	assert.Equal(t, "BUY", trade.Side)
	assert.Equal(t, float64(10), trade.Quantity)
	assert.Equal(t, float64(150.5), trade.Price)
	assert.Equal(t, "2024-01-15T10:00:00Z", trade.ExecutedAt)
}

// TestTransformTrades_StringPrice tests that prices returned as strings (actual API format) are correctly converted
func TestTransformTrades_StringPrice(t *testing.T) {
	// This test verifies the fix for prices returned as strings by Tradernet API (e.g., "p": "141.4")
	sdkResult := map[string]interface{}{
		"trades": map[string]interface{}{
			"trade": []interface{}{
				map[string]interface{}{
					"order_id": "299998887727",
					"instr_nm": "AAPL.US",
					"q":        "20",
					"p":        "141.4", // String price - actual API format
					"date":     "2019-08-15T10:10:22",
					"type":     "1", // 1 = Buy, 2 = Sell
				},
			},
			"max_trade_id": []interface{}{
				map[string]interface{}{
					"@text": "40975888",
				},
			},
		},
	}

	trades, err := transformTrades(sdkResult)

	assert.NoError(t, err)
	assert.Len(t, trades, 1)

	trade := trades[0]
	assert.Equal(t, "299998887727", trade.OrderID)
	assert.Equal(t, "AAPL.US", trade.Symbol)
	assert.Equal(t, "BUY", trade.Side)
	assert.Equal(t, float64(20), trade.Quantity)
	assert.Equal(t, float64(141.4), trade.Price) // Should parse string to float
	assert.Equal(t, "2019-08-15T10:10:22", trade.ExecutedAt)
}

// TestTransformSecurityInfo tests transformation of SDK FindSymbol to []SecurityInfo
func TestTransformSecurityInfo(t *testing.T) {
	sdkResult := map[string]interface{}{
		"result": []interface{}{
			map[string]interface{}{
				"symbol":        "AAPL.US",
				"name":          "Apple Inc.",
				"isin":          "US0378331005",
				"currency":      "USD",
				"market":        "NASDAQ",
				"exchange_code": "NASDAQ",
			},
		},
	}

	securities, err := transformSecurityInfo(sdkResult)

	assert.NoError(t, err)
	assert.Len(t, securities, 1)

	sec := securities[0]
	assert.Equal(t, "AAPL.US", sec.Symbol)
	assert.NotNil(t, sec.Name)
	assert.Equal(t, "Apple Inc.", *sec.Name)
	assert.NotNil(t, sec.ISIN)
	assert.Equal(t, "US0378331005", *sec.ISIN)
	assert.NotNil(t, sec.Currency)
	assert.Equal(t, "USD", *sec.Currency)
}

// TestTransformSecurityInfo_NullFields tests transformation with null optional fields
func TestTransformSecurityInfo_NullFields(t *testing.T) {
	sdkResult := map[string]interface{}{
		"result": []interface{}{
			map[string]interface{}{
				"symbol": "AAPL.US",
				// name, isin, currency are null/missing
			},
		},
	}

	securities, err := transformSecurityInfo(sdkResult)

	assert.NoError(t, err)
	assert.Len(t, securities, 1)

	sec := securities[0]
	assert.Equal(t, "AAPL.US", sec.Symbol)
	assert.Nil(t, sec.Name)
	assert.Nil(t, sec.ISIN)
}

// TestTransformSecurityInfo_FoundFormat tests transformation with raw API format ("found" key and short field names)
func TestTransformSecurityInfo_FoundFormat(t *testing.T) {
	sdkResult := map[string]interface{}{
		"found": []interface{}{
			map[string]interface{}{
				"t":       "RHM.EU",
				"nm":      "Rheinmetall AG",
				"n":       "Rheinmetall AG",
				"isin":    "DE0007030009",
				"x_curr":  "EUR",
				"mkt":     "EU",
				"codesub": "XETRA",
			},
		},
	}

	securities, err := transformSecurityInfo(sdkResult)

	assert.NoError(t, err)
	assert.Len(t, securities, 1)

	sec := securities[0]
	assert.Equal(t, "RHM.EU", sec.Symbol)
	assert.NotNil(t, sec.Name)
	assert.Equal(t, "Rheinmetall AG", *sec.Name)
	assert.NotNil(t, sec.ISIN)
	assert.Equal(t, "DE0007030009", *sec.ISIN)
	assert.NotNil(t, sec.Currency)
	assert.Equal(t, "EUR", *sec.Currency)
	assert.NotNil(t, sec.Market)
	assert.Equal(t, "EU", *sec.Market)
	assert.NotNil(t, sec.ExchangeCode)
	assert.Equal(t, "XETRA", *sec.ExchangeCode)
}

// TestTransformQuote tests transformation of SDK GetQuotes to Quote
func TestTransformQuote(t *testing.T) {
	sdkResult := map[string]interface{}{
		"result": map[string]interface{}{
			"AAPL.US": map[string]interface{}{
				"p":          float64(150.5),
				"change":     float64(2.5),
				"change_pct": float64(1.69),
				"volume":     float64(1000000),
				"timestamp":  "2024-01-15T10:00:00Z",
			},
		},
	}

	quote, err := transformQuote(sdkResult, "AAPL.US")

	assert.NoError(t, err)
	assert.NotNil(t, quote)
	assert.Equal(t, "AAPL.US", quote.Symbol)
	assert.Equal(t, float64(150.5), quote.Price)
	assert.Equal(t, float64(2.5), quote.Change)
	assert.Equal(t, float64(1.69), quote.ChangePct)
	assert.Equal(t, int64(1000000), quote.Volume)
	assert.Equal(t, "2024-01-15T10:00:00Z", quote.Timestamp)
}

// TestTransformQuote_MissingSymbol tests transformation when symbol not found
func TestTransformQuote_MissingSymbol(t *testing.T) {
	sdkResult := map[string]interface{}{
		"result": map[string]interface{}{
			"TSLA.US": map[string]interface{}{
				"p": float64(200.0),
			},
		},
	}

	quote, err := transformQuote(sdkResult, "AAPL.US")

	assert.Error(t, err)
	assert.Nil(t, quote)
}

// TestTransformQuote_ArrayFormat tests transformation when API returns array format
func TestTransformQuote_ArrayFormat(t *testing.T) {
	sdkResult := map[string]interface{}{
		"result": []interface{}{
			map[string]interface{}{
				"symbol":     "EURUSD_T0.ITS",
				"p":          float64(1.085),
				"change":     float64(0.001),
				"change_pct": float64(0.09),
				"volume":     float64(1000000),
				"timestamp":  "2024-01-15T10:00:00Z",
			},
			map[string]interface{}{
				"symbol":     "EURGBP_T0.ITS",
				"p":          float64(0.85),
				"change":     float64(0.002),
				"change_pct": float64(0.24),
				"volume":     float64(500000),
				"timestamp":  "2024-01-15T10:00:00Z",
			},
		},
	}

	quote, err := transformQuote(sdkResult, "EURUSD_T0.ITS")

	assert.NoError(t, err)
	assert.NotNil(t, quote)
	assert.Equal(t, "EURUSD_T0.ITS", quote.Symbol)
	assert.Equal(t, float64(1.085), quote.Price)
	assert.Equal(t, float64(0.001), quote.Change)
	assert.Equal(t, float64(0.09), quote.ChangePct)
	assert.Equal(t, int64(1000000), quote.Volume)
	assert.Equal(t, "2024-01-15T10:00:00Z", quote.Timestamp)
}

// TestGetString tests the getString helper function
func TestGetString(t *testing.T) {
	tests := []struct {
		name     string
		m        map[string]interface{}
		key      string
		expected string
	}{
		{
			name:     "string value",
			m:        map[string]interface{}{"key": "value"},
			key:      "key",
			expected: "value",
		},
		{
			name:     "missing key",
			m:        map[string]interface{}{"other": "value"},
			key:      "key",
			expected: "",
		},
		{
			name:     "int value converted to string",
			m:        map[string]interface{}{"key": 123},
			key:      "key",
			expected: "123",
		},
		{
			name:     "float value converted to string",
			m:        map[string]interface{}{"key": 45.67},
			key:      "key",
			expected: "45.67",
		},
		{
			name:     "bool value converted to string",
			m:        map[string]interface{}{"key": true},
			key:      "key",
			expected: "true",
		},
		{
			name:     "empty string",
			m:        map[string]interface{}{"key": ""},
			key:      "key",
			expected: "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := getString(tt.m, tt.key)
			assert.Equal(t, tt.expected, result)
		})
	}
}

// TestGetFloat64 tests the getFloat64 helper function
func TestGetFloat64(t *testing.T) {
	tests := []struct {
		name     string
		m        map[string]interface{}
		key      string
		expected float64
	}{
		{
			name:     "float64 value",
			m:        map[string]interface{}{"key": float64(123.45)},
			key:      "key",
			expected: 123.45,
		},
		{
			name:     "float32 value",
			m:        map[string]interface{}{"key": float32(123.45)},
			key:      "key",
			expected: 123.44999694824219, // float32 precision loss when converted to float64
		},
		{
			name:     "int value",
			m:        map[string]interface{}{"key": 123},
			key:      "key",
			expected: 123.0,
		},
		{
			name:     "int64 value",
			m:        map[string]interface{}{"key": int64(456)},
			key:      "key",
			expected: 456.0,
		},
		{
			name:     "int32 value",
			m:        map[string]interface{}{"key": int32(789)},
			key:      "key",
			expected: 789.0,
		},
		{
			name:     "missing key",
			m:        map[string]interface{}{"other": 123.0},
			key:      "key",
			expected: 0.0,
		},
		{
			name:     "unsupported type",
			m:        map[string]interface{}{"key": "not a number"},
			key:      "key",
			expected: 0.0,
		},
		{
			name:     "zero value",
			m:        map[string]interface{}{"key": float64(0)},
			key:      "key",
			expected: 0.0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := getFloat64(tt.m, tt.key)
			if tt.name == "float32 value" {
				// Use InDelta for float32 due to precision loss
				assert.InDelta(t, tt.expected, result, 0.0001)
			} else {
				assert.Equal(t, tt.expected, result)
			}
		})
	}
}

// TestGetFloat64FromValue tests the getFloat64FromValue helper function
func TestGetFloat64FromValue(t *testing.T) {
	tests := []struct {
		name     string
		val      interface{}
		expected float64
	}{
		{
			name:     "float64",
			val:      float64(123.45),
			expected: 123.45,
		},
		{
			name:     "float32",
			val:      float32(123.45),
			expected: 123.44999694824219, // float32 precision loss when converted to float64
		},
		{
			name:     "int",
			val:      123,
			expected: 123.0,
		},
		{
			name:     "int64",
			val:      int64(456),
			expected: 456.0,
		},
		{
			name:     "int32",
			val:      int32(789),
			expected: 789.0,
		},
		{
			name:     "string",
			val:      "not a number",
			expected: 0.0,
		},
		{
			name:     "bool",
			val:      true,
			expected: 0.0,
		},
		{
			name:     "nil",
			val:      nil,
			expected: 0.0,
		},
		{
			name:     "zero float64",
			val:      float64(0),
			expected: 0.0,
		},
		{
			name:     "negative int",
			val:      -123,
			expected: -123.0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := getFloat64FromValue(tt.val)
			if tt.name == "float32" {
				// Use InDelta for float32 due to precision loss
				assert.InDelta(t, tt.expected, result, 0.0001)
			} else {
				assert.Equal(t, tt.expected, result)
			}
		})
	}
}

// TestTransformCrossRates tests transformation of SDK getCrossRatesForDate response to map[string]float64
func TestTransformCrossRates(t *testing.T) {
	sdkResult := map[string]interface{}{
		"rates": map[string]interface{}{
			"EUR": 0.92261342533093,
			"HKD": 7.8070160113905,
		},
	}

	rates, err := transformCrossRates(sdkResult)

	assert.NoError(t, err)
	assert.NotNil(t, rates)
	assert.Len(t, rates, 2)
	assert.Equal(t, 0.92261342533093, rates["EUR"])
	assert.Equal(t, 7.8070160113905, rates["HKD"])
}

// TestTransformCrossRates_EmptyRates tests transformation with empty rates map
func TestTransformCrossRates_EmptyRates(t *testing.T) {
	sdkResult := map[string]interface{}{
		"rates": map[string]interface{}{},
	}

	rates, err := transformCrossRates(sdkResult)

	assert.NoError(t, err)
	assert.NotNil(t, rates)
	assert.Len(t, rates, 0)
}

// TestTransformCrossRates_MissingRatesKey tests error handling for missing "rates" key
func TestTransformCrossRates_MissingRatesKey(t *testing.T) {
	sdkResult := map[string]interface{}{
		"data": map[string]interface{}{
			"EUR": 0.9226,
		},
	}

	rates, err := transformCrossRates(sdkResult)

	assert.Error(t, err)
	assert.Nil(t, rates)
	assert.Contains(t, err.Error(), "missing or invalid 'rates' key")
}

// TestTransformCrossRates_InvalidResponseFormat tests error handling for invalid response format
func TestTransformCrossRates_InvalidResponseFormat(t *testing.T) {
	sdkResult := "invalid format"

	rates, err := transformCrossRates(sdkResult)

	assert.Error(t, err)
	assert.Nil(t, rates)
	assert.Contains(t, err.Error(), "invalid SDK result format")
}

// TestTransformCrossRates_InvalidRatesType tests error handling for invalid rates type
func TestTransformCrossRates_InvalidRatesType(t *testing.T) {
	sdkResult := map[string]interface{}{
		"rates": "not a map",
	}

	rates, err := transformCrossRates(sdkResult)

	assert.Error(t, err)
	assert.Nil(t, rates)
	assert.Contains(t, err.Error(), "missing or invalid 'rates' key")
}
