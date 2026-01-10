package handlers

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/services"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func setupTestServices() (*services.CurrencyExchangeService, *services.ExchangeRateCacheService) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	// Create minimal services for testing (nil dependencies)
	var brokerClient domain.BrokerClient
	currencyExchangeService := services.NewCurrencyExchangeService(brokerClient, logger)
	exchangeRateCacheService := services.NewExchangeRateCacheService(nil, currencyExchangeService, nil, nil, nil, logger)
	return currencyExchangeService, exchangeRateCacheService
}

func TestHandleGetConversionPath(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	currencyService, cacheService := setupTestServices()
	handler := NewHandler(currencyService, cacheService, nil, logger)

	router := chi.NewRouter()
	router.Get("/conversion-path/{from}/{to}", handler.HandleGetConversionPath)

	req := httptest.NewRequest("GET", "/conversion-path/EUR/USD", nil)
	w := httptest.NewRecorder()

	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
	assert.Contains(t, response, "metadata")
}

func TestHandleConvert(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	currencyService, cacheService := setupTestServices()
	handler := NewHandler(currencyService, cacheService, nil, logger)

	requestBody := map[string]interface{}{
		"from_currency": "EUR",
		"to_currency":   "USD",
		"amount":        100.0,
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/currency/convert", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleConvert(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
}

func TestHandleGetAvailableCurrencies(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	currencyService, cacheService := setupTestServices()
	handler := NewHandler(currencyService, cacheService, nil, logger)

	req := httptest.NewRequest("GET", "/api/currency/available-currencies", nil)
	w := httptest.NewRecorder()

	handler.HandleGetAvailableCurrencies(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "currencies")
}

func TestHandleGetRateSources(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	currencyService, cacheService := setupTestServices()
	handler := NewHandler(currencyService, cacheService, nil, logger)

	req := httptest.NewRequest("GET", "/api/currency/rates/sources", nil)
	w := httptest.NewRecorder()

	handler.HandleGetRateSources(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
}

func TestHandleGetRateStaleness(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	currencyService, cacheService := setupTestServices()
	handler := NewHandler(currencyService, cacheService, nil, logger)

	req := httptest.NewRequest("GET", "/api/currency/rates/staleness", nil)
	w := httptest.NewRecorder()

	handler.HandleGetRateStaleness(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
}

func TestHandleGetFallbackChain(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	currencyService, cacheService := setupTestServices()
	handler := NewHandler(currencyService, cacheService, nil, logger)

	req := httptest.NewRequest("GET", "/api/currency/rates/fallback-chain", nil)
	w := httptest.NewRecorder()

	handler.HandleGetFallbackChain(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
}

func TestHandleSyncRates(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	currencyService, cacheService := setupTestServices()
	handler := NewHandler(currencyService, cacheService, nil, logger)

	req := httptest.NewRequest("POST", "/api/currency/rates/sync", nil)
	w := httptest.NewRecorder()

	handler.HandleSyncRates(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
}

func TestHandleGetBalances(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	currencyService, cacheService := setupTestServices()
	handler := NewHandler(currencyService, cacheService, nil, logger)

	req := httptest.NewRequest("GET", "/api/currency/balances", nil)
	w := httptest.NewRecorder()

	handler.HandleGetBalances(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
}

func TestHandleBalanceCheck(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	currencyService, cacheService := setupTestServices()
	handler := NewHandler(currencyService, cacheService, nil, logger)

	requestBody := map[string]interface{}{
		"currency": "EUR",
		"amount":   100.0,
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/currency/balance-check", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleBalanceCheck(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
}

func TestHandleConversionRequirements(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	currencyService, cacheService := setupTestServices()
	handler := NewHandler(currencyService, cacheService, nil, logger)

	requestBody := map[string]interface{}{
		"symbol":   "AAPL",
		"side":     "BUY",
		"quantity": 10,
		"price":    150.0,
		"currency": "USD",
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/currency/conversion-requirements", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleConversionRequirements(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
}

func TestInvalidJSONRequest(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	currencyService, cacheService := setupTestServices()
	handler := NewHandler(currencyService, cacheService, nil, logger)

	req := httptest.NewRequest("POST", "/api/currency/convert", bytes.NewReader([]byte("invalid json")))
	w := httptest.NewRecorder()

	handler.HandleConvert(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}
