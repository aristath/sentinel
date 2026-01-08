package sdk

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

// TestNewUser tests NewUser method
func TestNewUser(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedURL string
	var capturedMethod string
	var capturedQuery string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedURL = r.URL.Path
		capturedMethod = r.Method
		capturedQuery = r.URL.RawQuery

		response := map[string]interface{}{
			"result": map[string]interface{}{
				"clientId": "12345",
				"userId":   "67890",
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	password := "testpass"
	tariffID := 1
	result, err := client.NewUser("testuser", "35", "1234567890", "Doe", "John", &password, nil, &tariffID)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, "GET", capturedMethod, "NewUser should use GET method (plainRequest)")
	assert.Equal(t, "/api", capturedURL, "URL should be /api")
	assert.Contains(t, capturedQuery, "q=", "Query should contain 'q' parameter")
	// The query parameter contains JSON with the command
	assert.Contains(t, capturedQuery, "registerNewUser", "Query should contain command")
}

// TestCheckMissingFields tests CheckMissingFields method
func TestCheckMissingFields(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedURL string
	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedURL = r.URL.Path

		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": map[string]interface{}{
				"not_completed": []string{"field1", "field2"},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	result, err := client.CheckMissingFields(1, "office1")

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, "/api/checkStep", capturedURL)
	assert.Contains(t, capturedBody, `"step":1`)
	assert.Contains(t, capturedBody, `"office":"office1"`)
}

// TestGetProfileFields tests GetProfileFields method
func TestGetProfileFields(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedURL string
	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedURL = r.URL.Path

		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": map[string]interface{}{
				"fields": []string{"field1", "field2"},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	result, err := client.GetProfileFields(35)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, "/api/getAnketaFields", capturedURL)
	assert.Contains(t, capturedBody, `"anketa_for_reception":35`)
}

// TestGetUserData tests GetUserData method
func TestGetUserData(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedURL string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedURL = r.URL.Path

		response := map[string]interface{}{
			"result": map[string]interface{}{
				"orders":    []interface{}{},
				"portfolio": map[string]interface{}{},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	result, err := client.GetUserData()

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, "/api/getOPQ", capturedURL)
}

// TestGetMarketStatus tests GetMarketStatus method
func TestGetMarketStatus(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": map[string]interface{}{
				"status": "open",
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	// Test with default market
	result, err := client.GetMarketStatus("", nil)
	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Contains(t, capturedBody, `"market":"*"`)

	// Test with specific market
	mode := "demo"
	result2, err := client.GetMarketStatus("NYSE", &mode)
	assert.NoError(t, err)
	assert.NotNil(t, result2)
	assert.Contains(t, capturedBody, `"market":"NYSE"`)
}

// TestGetOptions tests GetOptions method
func TestGetOptions(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": []interface{}{
				map[string]interface{}{"symbol": "AAPL220121C00150000"},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	result, err := client.GetOptions("AAPL.US", "CBOE")

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Contains(t, capturedBody, `"base_contract_code":"AAPL.US"`)
	assert.Contains(t, capturedBody, `"ltr":"CBOE"`)
}

// TestGetMostTraded tests GetMostTraded method
func TestGetMostTraded(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedURL string
	var capturedMethod string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedURL = r.URL.Path + "?" + r.URL.RawQuery
		capturedMethod = r.Method

		response := map[string]interface{}{
			"result": []interface{}{
				map[string]interface{}{"symbol": "AAPL.US"},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	// Test with defaults
	result, err := client.GetMostTraded("", "", true, 0)
	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, "GET", capturedMethod)
	assert.Contains(t, capturedURL, "getTopSecurities")

	// Test with specific params
	result2, err := client.GetMostTraded("stocks", "usa", false, 20)
	assert.NoError(t, err)
	assert.NotNil(t, result2)
}

// TestStop tests Stop method
func TestStop(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": map[string]interface{}{
				"order_id": 12345,
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	result, err := client.Stop("AAPL.US", 150.0)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Contains(t, capturedBody, `"instr_name":"AAPL.US"`)
	assert.Contains(t, capturedBody, `"stop_loss":150`)
}

// TestTrailingStop tests TrailingStop method
func TestTrailingStop(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": map[string]interface{}{
				"order_id": 12345,
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	result, err := client.TrailingStop("AAPL.US", 5.0)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Contains(t, capturedBody, `"instr_name":"AAPL.US"`)
	assert.Contains(t, capturedBody, `"stop_loss_percent":5`)
	assert.Contains(t, capturedBody, `"stoploss_trailing_percent":5`)
}

// TestTakeProfit tests TakeProfit method
func TestTakeProfit(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": map[string]interface{}{
				"order_id": 12345,
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	result, err := client.TakeProfit("AAPL.US", 200.0)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Contains(t, capturedBody, `"instr_name":"AAPL.US"`)
	assert.Contains(t, capturedBody, `"take_profit":200`)
}

// TestCancelAll tests CancelAll method
func TestCancelAll(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	callCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		if strings.Contains(r.URL.Path, "getNotifyOrderJson") {
			// First call: get placed orders
			response := map[string]interface{}{
				"result": map[string]interface{}{
					"orders": map[string]interface{}{
						"order": []interface{}{
							map[string]interface{}{"id": 123},
							map[string]interface{}{"id": 456},
						},
					},
				},
			}
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(response)
		} else {
			// Subsequent calls: cancel orders
			response := map[string]interface{}{
				"result": map[string]interface{}{
					"status": "cancelled",
				},
			}
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(response)
		}
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	result, err := client.CancelAll()

	assert.NoError(t, err)
	assert.NotNil(t, result)
	// Should call GetPlaced once, then Cancel twice
	assert.GreaterOrEqual(t, callCount, 3)
}

// TestGetHistorical tests GetHistorical method
func TestGetHistorical(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": map[string]interface{}{
				"orders": []interface{}{},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	start := time.Date(2023, 1, 1, 0, 0, 0, 0, time.UTC)
	end := time.Date(2023, 12, 31, 23, 59, 59, 0, time.UTC)

	result, err := client.GetHistorical(start, end)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Contains(t, capturedBody, `"from":"2023-01-01T00:00:00"`)
	assert.Contains(t, capturedBody, `"till":"2023-12-31T23:59:59"`)
}

// TestGetOrderFiles tests GetOrderFiles method
func TestGetOrderFiles(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": map[string]interface{}{
				"files": []interface{}{},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	orderID := 12345
	result, err := client.GetOrderFiles(&orderID, nil)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Contains(t, capturedBody, `"id":12345`)

	// Test with internal_id
	internalID := 67890
	result2, err := client.GetOrderFiles(nil, &internalID)
	assert.NoError(t, err)
	assert.NotNil(t, result2)
	assert.Contains(t, capturedBody, `"internal_id":67890`)
}

// TestGetBrokerReport tests GetBrokerReport method
func TestGetBrokerReport(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": map[string]interface{}{
				"report": "data",
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	start := time.Date(2023, 1, 1, 0, 0, 0, 0, time.UTC)
	end := time.Date(2023, 12, 31, 0, 0, 0, 0, time.UTC)
	period := time.Date(0, 0, 0, 23, 59, 59, 0, time.UTC)
	dataBlockType := "account_at_end"

	result, err := client.GetBrokerReport(start, end, period, &dataBlockType)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Contains(t, capturedBody, `"date_start":"2023-01-01"`)
	assert.Contains(t, capturedBody, `"date_end":"2023-12-31"`)
	assert.Contains(t, capturedBody, `"time_period":"23:59:59"`)
	assert.Contains(t, capturedBody, `"format":"json"`)
	assert.Contains(t, capturedBody, `"type":"account_at_end"`)
}

// TestGetNews tests GetNews method
func TestGetNews(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": []interface{}{
				map[string]interface{}{"title": "News 1"},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	symbol := "AAPL.US"
	result, err := client.GetNews("AAPL", &symbol, nil, 30)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Contains(t, capturedBody, `"searchFor":"AAPL"`)
	assert.Contains(t, capturedBody, `"ticker":"AAPL.US"`)
	assert.Contains(t, capturedBody, `"limit":30`)
}

// TestSymbol tests Symbol method
func TestSymbol(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": map[string]interface{}{
				"symbol": "AAPL.US",
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	result, err := client.Symbol("AAPL.US", "en")

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Contains(t, capturedBody, `"ticker":"AAPL.US"`)
	assert.Contains(t, capturedBody, `"lang":"en"`)
}

// TestSymbols tests Symbols method
func TestSymbols(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": map[string]interface{}{
				"symbols": []interface{}{},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	exchange := "USA"
	result, err := client.Symbols(&exchange)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	// Python SDK converts to lowercase
	assert.Contains(t, capturedBody, `"mkt":"usa"`)
}

// TestCorporateActions tests CorporateActions method
func TestCorporateActions(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": []interface{}{},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	result, err := client.CorporateActions(35)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Contains(t, capturedBody, `"reception":35`)
}

// TestGetPriceAlerts tests GetPriceAlerts method
func TestGetPriceAlerts(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": []interface{}{},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	symbol := "AAPL.US"
	result, err := client.GetPriceAlerts(&symbol)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Contains(t, capturedBody, `"ticker":"AAPL.US"`)

	// Test without symbol
	result2, err := client.GetPriceAlerts(nil)
	assert.NoError(t, err)
	assert.NotNil(t, result2)
}

// TestAddPriceAlert tests AddPriceAlert method
func TestAddPriceAlert(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": map[string]interface{}{
				"alert_id": 12345,
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	// Test with single price
	result, err := client.AddPriceAlert("AAPL.US", 150.0, "crossing", "ltp", "email", 0, 0)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Contains(t, capturedBody, `"ticker":"AAPL.US"`)
	assert.Contains(t, capturedBody, `"price":["150"]`)
	assert.Contains(t, capturedBody, `"trigger_type":"crossing"`)
	assert.Contains(t, capturedBody, `"quote_type":"ltp"`)
	assert.Contains(t, capturedBody, `"notification_type":"email"`)

	// Test with price array
	prices := []float64{150.0, 200.0}
	result2, err := client.AddPriceAlert("AAPL.US", prices, "crossing", "ltp", "email", 0, 0)
	assert.NoError(t, err)
	assert.NotNil(t, result2)
}

// TestDeletePriceAlert tests DeletePriceAlert method
func TestDeletePriceAlert(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedBody string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		capturedBody = string(body)

		response := map[string]interface{}{
			"result": map[string]interface{}{
				"status": "deleted",
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	result, err := client.DeletePriceAlert(12345)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Contains(t, capturedBody, `"id":12345`)
	assert.Contains(t, capturedBody, `"del":true`)
}

// TestGetTariffsList tests GetTariffsList method
func TestGetTariffsList(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	var capturedURL string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedURL = r.URL.Path

		response := map[string]interface{}{
			"result": []interface{}{
				map[string]interface{}{"id": 1, "name": "Basic"},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := &Client{
		publicKey:  "test_public",
		privateKey: "test_private",
		baseURL:    server.URL,
		httpClient: &http.Client{},
		log:        log,
	}

	result, err := client.GetTariffsList()

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, "/api/GetListTariffs", capturedURL)
}
