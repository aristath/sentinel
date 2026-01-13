package handlers

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aristath/sentinel/internal/modules/optimization"
	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/sequences"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func setupTestService() *sequences.Service {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	riskBuilder := &optimization.RiskModelBuilder{}
	// Pass nil enforcer - tests don't need constraint enforcement
	return sequences.NewService(logger, riskBuilder, nil)
}

func TestHandleGenerate(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	requestBody := map[string]interface{}{
		"opportunities": map[string]interface{}{
			"profit_taking":  []interface{}{},
			"averaging_down": []interface{}{},
		},
		"config": map[string]interface{}{
			"max_depth":     5,
			"max_sequences": 100,
		},
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/sequences/generate", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleGenerate(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
	assert.Contains(t, response, "metadata")
}

func TestHandleGenerateWithOpportunities(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	requestBody := GenerateRequest{
		Opportunities: domain.OpportunitiesByCategory{
			domain.OpportunityCategoryProfitTaking: []domain.ActionCandidate{
				{
					Symbol:   "AAPL",
					ISIN:     "US0378331005",
					Side:     "SELL",
					Quantity: 10,
					Price:    150.0,
					ValueEUR: 1500.0,
					Priority: 0.8,
				},
			},
			domain.OpportunityCategoryOpportunityBuys: []domain.ActionCandidate{
				{
					Symbol:   "GOOGL",
					ISIN:     "US02079K1079",
					Side:     "BUY",
					Quantity: 5,
					Price:    100.0,
					ValueEUR: 500.0,
					Priority: 0.7,
				},
			},
		},
		Config: &domain.PlannerConfiguration{
			MaxDepth: 3,
		},
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/sequences/generate", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleGenerate(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	count := int(data["count"].(float64))
	// Should generate sequences: single SELL, single BUY, and SELL+BUY combo
	assert.GreaterOrEqual(t, count, 1, "Should generate at least one sequence")
}

func TestHandleGetInfo(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	req := httptest.NewRequest("GET", "/api/sequences/info", nil)
	w := httptest.NewRecorder()

	handler.HandleGetInfo(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Equal(t, "exhaustive", data["generator"])
	assert.Contains(t, data, "features")
	assert.Contains(t, data, "filters")
}

func TestHandleFilterCorrelation(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	requestBody := map[string]interface{}{
		"sequences": []interface{}{
			map[string]interface{}{
				"actions": []interface{}{
					map[string]interface{}{
						"symbol":   "AAPL",
						"isin":     "US0378331005",
						"side":     "BUY",
						"quantity": 1,
						"price":    150.0,
					},
				},
				"pattern_type": "exhaustive",
			},
		},
		"config": map[string]interface{}{},
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/sequences/filter/correlation", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleFilterCorrelation(w, req)

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

	req := httptest.NewRequest("POST", "/api/sequences/generate", bytes.NewReader([]byte("invalid json")))
	w := httptest.NewRecorder()

	handler.HandleGenerate(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}
