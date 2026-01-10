package handlers

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aristath/sentinel/internal/modules/quantum"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func setupTestCalculator() *quantum.QuantumProbabilityCalculator {
	return quantum.NewQuantumProbabilityCalculator()
}

func TestHandleCalculateAmplitude(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	calculator := setupTestCalculator()
	handler := NewHandler(calculator, logger)

	requestBody := map[string]interface{}{
		"probability": 0.8,
		"energy":      1.5,
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/quantum/amplitude", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleCalculateAmplitude(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "probability")
	assert.Contains(t, data, "energy")
	assert.Contains(t, data, "amplitude")
}

func TestHandleCalculateInterference(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	calculator := setupTestCalculator()
	handler := NewHandler(calculator, logger)

	requestBody := map[string]interface{}{
		"p1":      0.6,
		"p2":      0.4,
		"energy1": 1.0,
		"energy2": 2.0,
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/quantum/interference", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleCalculateInterference(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "interference")
}

func TestHandleCalculateProbability(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	calculator := setupTestCalculator()
	handler := NewHandler(calculator, logger)

	requestBody := map[string]interface{}{
		"amplitude_real": 0.7071,
		"amplitude_imag": 0.7071,
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/quantum/probability", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleCalculateProbability(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "probability")
}

func TestHandleGetEnergyLevels(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	calculator := setupTestCalculator()
	handler := NewHandler(calculator, logger)

	req := httptest.NewRequest("GET", "/api/quantum/energy-levels", nil)
	w := httptest.NewRecorder()

	handler.HandleGetEnergyLevels(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "levels")

	levels := data["levels"].([]interface{})
	assert.Equal(t, 5, len(levels))
}

func TestHandleCalculateMultimodalCorrection(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	calculator := setupTestCalculator()
	handler := NewHandler(calculator, logger)

	requestBody := map[string]interface{}{
		"volatility": 0.25,
		"kurtosis":   3.5,
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/quantum/multimodal-correction", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleCalculateMultimodalCorrection(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "correction")
}

func TestHandleCalculateMultimodalCorrection_NoKurtosis(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	calculator := setupTestCalculator()
	handler := NewHandler(calculator, logger)

	requestBody := map[string]interface{}{
		"volatility": 0.25,
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/quantum/multimodal-correction", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleCalculateMultimodalCorrection(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
}

func TestInvalidJSONRequest(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	calculator := setupTestCalculator()
	handler := NewHandler(calculator, logger)

	req := httptest.NewRequest("POST", "/api/quantum/amplitude", bytes.NewReader([]byte("invalid json")))
	w := httptest.NewRecorder()

	handler.HandleCalculateAmplitude(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestMissingRequiredFields(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	calculator := setupTestCalculator()
	handler := NewHandler(calculator, logger)

	requestBody := map[string]interface{}{
		"probability": 0.8,
		// Missing "energy"
	}
	bodyBytes, _ := json.Marshal(requestBody)

	req := httptest.NewRequest("POST", "/api/quantum/amplitude", bytes.NewReader(bodyBytes))
	w := httptest.NewRecorder()

	handler.HandleCalculateAmplitude(w, req)

	// Should still succeed with default energy value of 0
	assert.Equal(t, http.StatusOK, w.Code)
}
