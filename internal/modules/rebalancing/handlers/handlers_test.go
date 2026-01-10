package handlers

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aristath/sentinel/internal/modules/rebalancing"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func setupTestService() *rebalancing.Service {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	// Create minimal service for testing (nil dependencies)
	triggerChecker := rebalancing.NewTriggerChecker(logger)
	negativeRebalancer := rebalancing.NewNegativeBalanceRebalancer(
		logger,
		nil, // cashManager
		nil, // brokerClient
		nil, // securityRepo
		nil, // positionRepo
		nil, // settingsRepo
		nil, // currencyExchangeService
		nil, // tradeExecutionService
		nil, // recommendationRepo
	)
	return rebalancing.NewService(
		triggerChecker,
		negativeRebalancer,
		nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil,
		logger,
	)
}

func TestHandleCalculateRebalance(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	requestBody := map[string]interface{}{
		"available_cash": 1000.0,
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/rebalancing/calculate", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleCalculateRebalance(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
	assert.Contains(t, response, "metadata")
}

func TestHandleCalculateTargetWeights(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	requestBody := map[string]interface{}{
		"target_weights": map[string]interface{}{
			"US0378331005": 0.30,
			"US5949181045": 0.20,
		},
		"available_cash": 1000.0,
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/rebalancing/calculate/target-weights", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleCalculateTargetWeights(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
}

func TestHandleGetTriggers(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	req := httptest.NewRequest("GET", "/api/rebalancing/triggers", nil)
	w := httptest.NewRecorder()

	handler.HandleGetTriggers(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "should_rebalance")
}

func TestHandleGetMinTradeAmount(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	req := httptest.NewRequest("GET", "/api/rebalancing/min-trade-amount", nil)
	w := httptest.NewRecorder()

	handler.HandleGetMinTradeAmount(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "min_trade_amount")
}

func TestHandleSimulateRebalance(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	requestBody := map[string]interface{}{
		"trades": []interface{}{
			map[string]interface{}{
				"symbol":   "AAPL",
				"side":     "BUY",
				"quantity": 10,
				"price":    150.0,
			},
		},
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/rebalancing/simulate-rebalance", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleSimulateRebalance(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
}

func TestHandleNegativeBalanceCheck(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	requestBody := map[string]interface{}{
		"trades": []interface{}{
			map[string]interface{}{
				"symbol":   "AAPL",
				"side":     "BUY",
				"quantity": 10,
				"price":    150.0,
				"currency": "USD",
			},
		},
		"cash_balances": map[string]interface{}{
			"USD": 1000.0,
			"EUR": 500.0,
		},
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/rebalancing/negative-balance-check", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleNegativeBalanceCheck(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
}

func TestInvalidJSONRequest(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	req := httptest.NewRequest("POST", "/api/rebalancing/calculate", bytes.NewReader([]byte("invalid json")))
	w := httptest.NewRecorder()

	handler.HandleCalculateRebalance(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestMissingAvailableCash(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	requestBody := map[string]interface{}{}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/rebalancing/calculate", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleCalculateRebalance(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}
