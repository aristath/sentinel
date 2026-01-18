package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/aristath/sentinel/internal/market_regime"
	"github.com/aristath/sentinel/internal/modules/adaptation"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	_ "modernc.org/sqlite"
)

// setupTestDB creates an in-memory SQLite database with test data
func setupTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)

	// Create market_regime_history table
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS market_regime_history (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			recorded_at INTEGER NOT NULL,
			region TEXT NOT NULL DEFAULT 'GLOBAL',
			raw_score REAL NOT NULL,
			smoothed_score REAL NOT NULL,
			discrete_regime TEXT
		)
	`)
	require.NoError(t, err)

	// Insert test regime history data
	testData := []struct {
		recordedAt     int64
		rawScore       float64
		smoothedScore  float64
		discreteRegime string
	}{
		{time.Now().Add(-10 * time.Minute).Unix(), 0.5, 0.45, "bull"},
		{time.Now().Add(-5 * time.Minute).Unix(), 0.6, 0.50, "bull"},
		{time.Now().Unix(), 0.55, 0.52, "bull"},
	}

	for _, d := range testData {
		_, err = db.Exec(`
			INSERT INTO market_regime_history (recorded_at, region, raw_score, smoothed_score, discrete_regime)
			VALUES (?, ?, ?, ?, ?)
		`, d.recordedAt, "GLOBAL", d.rawScore, d.smoothedScore, d.discreteRegime)
		require.NoError(t, err)
	}

	return db
}

func TestHandleGetCurrent(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	adaptiveService := adaptation.NewAdaptiveMarketService(nil, nil, nil, nil, logger)
	regimePersistence := market_regime.NewRegimePersistence(db, logger)
	handler := NewHandler(regimePersistence, adaptiveService, logger)

	req := httptest.NewRequest("GET", "/api/adaptation/current", nil)
	w := httptest.NewRecorder()

	handler.HandleGetCurrent(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	// Verify response structure
	assert.Contains(t, response, "data")
	assert.Contains(t, response, "metadata")

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "raw_score")
	assert.Contains(t, data, "smoothed_score")
	assert.Contains(t, data, "discrete_regime")
	assert.Contains(t, data, "recorded_at")

	// Verify values are from latest entry
	assert.Equal(t, 0.55, data["raw_score"].(float64))
	assert.Equal(t, 0.52, data["smoothed_score"].(float64))
	assert.Equal(t, "bull", data["discrete_regime"].(string))
}

func TestHandleGetHistory(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	adaptiveService := adaptation.NewAdaptiveMarketService(nil, nil, nil, nil, logger)
	regimePersistence := market_regime.NewRegimePersistence(db, logger)
	handler := NewHandler(regimePersistence, adaptiveService, logger)

	req := httptest.NewRequest("GET", "/api/adaptation/history?limit=10", nil)
	w := httptest.NewRecorder()

	handler.HandleGetHistory(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "history")
	assert.Contains(t, data, "count")

	history := data["history"].([]interface{})
	assert.Equal(t, 3, len(history))

	// Verify history entry structure
	entry := history[0].(map[string]interface{})
	assert.Contains(t, entry, "recorded_at")
	assert.Contains(t, entry, "raw_score")
	assert.Contains(t, entry, "smoothed_score")
	assert.Contains(t, entry, "discrete_regime")
}

func TestHandleGetAdaptiveWeights(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	adaptiveService := adaptation.NewAdaptiveMarketService(nil, nil, nil, nil, logger)
	regimePersistence := market_regime.NewRegimePersistence(db, logger)
	handler := NewHandler(regimePersistence, adaptiveService, logger)

	req := httptest.NewRequest("GET", "/api/adaptation/adaptive-weights", nil)
	w := httptest.NewRecorder()

	handler.HandleGetAdaptiveWeights(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "regime_score")
	assert.Contains(t, data, "weights")

	weights := data["weights"].(map[string]interface{})
	assert.Contains(t, weights, "long_term")
	assert.Contains(t, weights, "stability")
	assert.Contains(t, weights, "dividends")
	assert.Contains(t, weights, "opportunity")
}

func TestHandleGetAdaptiveParameters(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	adaptiveService := adaptation.NewAdaptiveMarketService(nil, nil, nil, nil, logger)
	regimePersistence := market_regime.NewRegimePersistence(db, logger)
	handler := NewHandler(regimePersistence, adaptiveService, logger)

	req := httptest.NewRequest("GET", "/api/adaptation/adaptive-parameters", nil)
	w := httptest.NewRecorder()

	handler.HandleGetAdaptiveParameters(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "regime_score")
	assert.Contains(t, data, "weights")
	assert.Contains(t, data, "blend")
	assert.Contains(t, data, "quality_gates")

	qualityGates := data["quality_gates"].(map[string]interface{})
	assert.Contains(t, qualityGates, "stability")
	assert.Contains(t, qualityGates, "long_term")
}

func TestHandleGetComponentPerformance(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	adaptiveService := adaptation.NewAdaptiveMarketService(nil, nil, nil, nil, logger)
	regimePersistence := market_regime.NewRegimePersistence(db, logger)
	handler := NewHandler(regimePersistence, adaptiveService, logger)

	req := httptest.NewRequest("GET", "/api/adaptation/component-performance", nil)
	w := httptest.NewRecorder()

	handler.HandleGetComponentPerformance(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "components")
}

func TestHandleGetPerformanceHistory(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	adaptiveService := adaptation.NewAdaptiveMarketService(nil, nil, nil, nil, logger)
	regimePersistence := market_regime.NewRegimePersistence(db, logger)
	handler := NewHandler(regimePersistence, adaptiveService, logger)

	req := httptest.NewRequest("GET", "/api/adaptation/performance-history", nil)
	w := httptest.NewRecorder()

	handler.HandleGetPerformanceHistory(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "history")
}

func TestRouteIntegration(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	adaptiveService := adaptation.NewAdaptiveMarketService(nil, nil, nil, nil, logger)
	regimePersistence := market_regime.NewRegimePersistence(db, logger)
	handler := NewHandler(regimePersistence, adaptiveService, logger)

	router := chi.NewRouter()
	handler.RegisterRoutes(router)

	tests := []struct {
		name           string
		method         string
		path           string
		expectedStatus int
	}{
		{"get current regime", "GET", "/adaptation/current", http.StatusOK},
		{"get regime history", "GET", "/adaptation/history", http.StatusOK},
		{"get adaptive weights", "GET", "/adaptation/adaptive-weights", http.StatusOK},
		{"get adaptive parameters", "GET", "/adaptation/adaptive-parameters", http.StatusOK},
		{"get component performance", "GET", "/adaptation/component-performance", http.StatusOK},
		{"get performance history", "GET", "/adaptation/performance-history", http.StatusOK},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(tt.method, tt.path, nil)
			w := httptest.NewRecorder()

			router.ServeHTTP(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
		})
	}
}
