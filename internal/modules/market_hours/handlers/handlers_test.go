package handlers

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aristath/sentinel/internal/modules/market_hours"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestHandleGetStatus(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := market_hours.NewMarketHoursService()
	handler := NewHandler(service, logger)

	tests := []struct {
		name           string
		expectedStatus int
		validate       func(*testing.T, *httptest.ResponseRecorder)
	}{
		{
			name:           "success",
			expectedStatus: http.StatusOK,
			validate: func(t *testing.T, w *httptest.ResponseRecorder) {
				var response map[string]interface{}
				err := json.Unmarshal(w.Body.Bytes(), &response)
				require.NoError(t, err)
				assert.NotNil(t, response["data"])

				data := response["data"].(map[string]interface{})
				assert.NotNil(t, data["markets"])
				markets := data["markets"].([]interface{})
				assert.Greater(t, len(markets), 0, "should have at least one market")
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/api/market-hours/status", nil)
			w := httptest.NewRecorder()

			handler.HandleGetStatus(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
			if tt.validate != nil {
				tt.validate(t, w)
			}
		})
	}
}

func TestHandleGetStatusByExchange(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := market_hours.NewMarketHoursService()
	handler := NewHandler(service, logger)

	tests := []struct {
		name           string
		exchange       string
		expectedStatus int
		validate       func(*testing.T, *httptest.ResponseRecorder)
	}{
		{
			name:           "valid exchange - XNYS",
			exchange:       "XNYS",
			expectedStatus: http.StatusOK,
			validate: func(t *testing.T, w *httptest.ResponseRecorder) {
				var response map[string]interface{}
				err := json.Unmarshal(w.Body.Bytes(), &response)
				require.NoError(t, err)

				data := response["data"].(map[string]interface{})
				assert.Equal(t, "XNYS", data["exchange"])
				assert.NotEmpty(t, data["timezone"])
				assert.Contains(t, data, "open")
			},
		},
		{
			name:           "valid exchange - XETR",
			exchange:       "XETR",
			expectedStatus: http.StatusOK,
			validate: func(t *testing.T, w *httptest.ResponseRecorder) {
				var response map[string]interface{}
				err := json.Unmarshal(w.Body.Bytes(), &response)
				require.NoError(t, err)

				data := response["data"].(map[string]interface{})
				assert.Equal(t, "XETR", data["exchange"])
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/api/market-hours/status/"+tt.exchange, nil)
			w := httptest.NewRecorder()

			// Create a mock router context
			handler.HandleGetStatusByExchange(w, req, tt.exchange)

			assert.Equal(t, tt.expectedStatus, w.Code)
			if tt.validate != nil {
				tt.validate(t, w)
			}
		})
	}
}

func TestHandleGetOpenMarkets(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := market_hours.NewMarketHoursService()
	handler := NewHandler(service, logger)

	tests := []struct {
		name           string
		expectedStatus int
		validate       func(*testing.T, *httptest.ResponseRecorder)
	}{
		{
			name:           "success",
			expectedStatus: http.StatusOK,
			validate: func(t *testing.T, w *httptest.ResponseRecorder) {
				var response map[string]interface{}
				err := json.Unmarshal(w.Body.Bytes(), &response)
				require.NoError(t, err)
				assert.NotNil(t, response["data"])

				data := response["data"].(map[string]interface{})
				assert.NotNil(t, data["open_markets"])
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/api/market-hours/open-markets", nil)
			w := httptest.NewRecorder()

			handler.HandleGetOpenMarkets(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
			if tt.validate != nil {
				tt.validate(t, w)
			}
		})
	}
}

func TestHandleGetHolidays(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := market_hours.NewMarketHoursService()
	handler := NewHandler(service, logger)

	tests := []struct {
		name           string
		queryParams    string
		expectedStatus int
		validate       func(*testing.T, *httptest.ResponseRecorder)
	}{
		{
			name:           "default - current year",
			queryParams:    "",
			expectedStatus: http.StatusOK,
			validate: func(t *testing.T, w *httptest.ResponseRecorder) {
				var response map[string]interface{}
				err := json.Unmarshal(w.Body.Bytes(), &response)
				require.NoError(t, err)
				assert.NotNil(t, response["data"])
			},
		},
		{
			name:           "specific year",
			queryParams:    "?year=2025",
			expectedStatus: http.StatusOK,
			validate: func(t *testing.T, w *httptest.ResponseRecorder) {
				var response map[string]interface{}
				err := json.Unmarshal(w.Body.Bytes(), &response)
				require.NoError(t, err)
				data := response["data"].(map[string]interface{})
				assert.NotEmpty(t, data)
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/api/market-hours/holidays"+tt.queryParams, nil)
			w := httptest.NewRecorder()

			handler.HandleGetHolidays(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
			if tt.validate != nil {
				tt.validate(t, w)
			}
		})
	}
}

func TestHandleValidateTradingWindow(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := market_hours.NewMarketHoursService()
	handler := NewHandler(service, logger)

	tests := []struct {
		name           string
		queryParams    string
		expectedStatus int
		validate       func(*testing.T, *httptest.ResponseRecorder)
	}{
		{
			name:           "valid trading window - XNYS BUY",
			queryParams:    "?symbol=AAPL&side=BUY&exchange=XNYS",
			expectedStatus: http.StatusOK,
			validate: func(t *testing.T, w *httptest.ResponseRecorder) {
				var response map[string]interface{}
				err := json.Unmarshal(w.Body.Bytes(), &response)
				require.NoError(t, err)
				data := response["data"].(map[string]interface{})
				assert.Contains(t, data, "can_trade")
				assert.Contains(t, data, "market_open")
			},
		},
		{
			name:           "missing symbol",
			queryParams:    "?side=BUY&exchange=XNYS",
			expectedStatus: http.StatusBadRequest,
		},
		{
			name:           "missing side",
			queryParams:    "?symbol=AAPL&exchange=XNYS",
			expectedStatus: http.StatusBadRequest,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/api/market-hours/validate-trading-window"+tt.queryParams, nil)
			w := httptest.NewRecorder()

			handler.HandleValidateTradingWindow(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
			if tt.validate != nil {
				tt.validate(t, w)
			}
		})
	}
}

func TestResponseFormat(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := market_hours.NewMarketHoursService()
	handler := NewHandler(service, logger)

	req := httptest.NewRequest("GET", "/api/market-hours/status", nil)
	w := httptest.NewRecorder()

	handler.HandleGetStatus(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

	var response map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	// Verify standard response format
	assert.Contains(t, response, "data")
	assert.Contains(t, response, "metadata")

	metadata := response["metadata"].(map[string]interface{})
	assert.Contains(t, metadata, "timestamp")
}
