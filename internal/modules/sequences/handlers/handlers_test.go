package handlers

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aristath/sentinel/internal/modules/optimization"
	"github.com/aristath/sentinel/internal/modules/sequences"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func setupTestService() *sequences.Service {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	riskBuilder := &optimization.RiskModelBuilder{}
	return sequences.NewService(logger, riskBuilder)
}

func TestHandleGenerateFromPattern(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	requestBody := map[string]interface{}{
		"pattern_type": "opportunity_first",
		"opportunities": map[string]interface{}{
			"profit_taking":  []interface{}{},
			"averaging_down": []interface{}{},
		},
		"config": map[string]interface{}{
			"patterns": map[string]interface{}{
				"opportunity_first": map[string]interface{}{
					"enabled": true,
				},
			},
		},
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/sequences/generate/pattern", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleGenerateFromPattern(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
	assert.Contains(t, response, "metadata")
}

func TestHandleGenerateFromAllPatterns(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	requestBody := map[string]interface{}{
		"opportunities": map[string]interface{}{
			"profit_taking":  []interface{}{},
			"averaging_down": []interface{}{},
		},
		"config": map[string]interface{}{
			"patterns": map[string]interface{}{
				"opportunity_first": map[string]interface{}{
					"enabled": true,
				},
			},
		},
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/sequences/generate/all-patterns", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleGenerateFromAllPatterns(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
}

func TestHandleListPatterns(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	req := httptest.NewRequest("GET", "/api/sequences/patterns", nil)
	w := httptest.NewRecorder()

	handler.HandleListPatterns(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	patterns := data["patterns"].([]interface{})
	assert.Greater(t, len(patterns), 0, "Should have at least one pattern")
}

func TestHandleFilterEligibility(t *testing.T) {
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
				"pattern_type": "direct_buy",
			},
		},
		"config": map[string]interface{}{},
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/sequences/filter/eligibility", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleFilterEligibility(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
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
				"pattern_type": "direct_buy",
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

func TestHandleFilterRecentlyTraded(t *testing.T) {
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
				"pattern_type": "direct_buy",
			},
		},
		"config": map[string]interface{}{},
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/sequences/filter/recently-traded", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleFilterRecentlyTraded(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
}

func TestHandleFilterTags(t *testing.T) {
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
				"pattern_type": "direct_buy",
			},
		},
		"config": map[string]interface{}{},
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/sequences/filter/tags", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleFilterTags(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
}

func TestHandleGetContext(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	req := httptest.NewRequest("GET", "/api/sequences/context", nil)
	w := httptest.NewRecorder()

	handler.HandleGetContext(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "patterns")
	assert.Contains(t, data, "filters")
}

func TestHandleGenerateCombinatorial(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	requestBody := map[string]interface{}{
		"pattern_types": []string{"opportunity_first", "direct_buy"},
		"opportunities": map[string]interface{}{
			"profit_taking":  []interface{}{},
			"averaging_down": []interface{}{},
		},
		"config": map[string]interface{}{
			"patterns": map[string]interface{}{
				"opportunity_first": map[string]interface{}{
					"enabled": true,
				},
				"direct_buy": map[string]interface{}{
					"enabled": true,
				},
			},
		},
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/sequences/generate/combinatorial", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleGenerateCombinatorial(w, req)

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

	req := httptest.NewRequest("POST", "/api/sequences/generate/pattern", bytes.NewReader([]byte("invalid json")))
	w := httptest.NewRecorder()

	handler.HandleGenerateFromPattern(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestMissingPatternType(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	requestBody := map[string]interface{}{
		"opportunities": map[string]interface{}{},
		"config":        map[string]interface{}{},
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/sequences/generate/pattern", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleGenerateFromPattern(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}
