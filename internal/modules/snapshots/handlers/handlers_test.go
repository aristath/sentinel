package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aristath/sentinel/internal/market_regime"
	"github.com/aristath/sentinel/internal/modules/adaptation"
	"github.com/aristath/sentinel/internal/modules/market_hours"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	_ "modernc.org/sqlite"
)

// mockCashManager is a simple mock
type mockCashManager struct{}

func (m *mockCashManager) UpdateCashPosition(currency string, balance float64) error {
	return nil
}

func (m *mockCashManager) GetAllCashBalances() (map[string]float64, error) {
	return map[string]float64{"EUR": 1000.0}, nil
}

func (m *mockCashManager) GetCashBalance(currency string) (float64, error) {
	return 1000.0, nil
}

// setupTestHandler creates a handler with all required dependencies
func setupTestHandler(t *testing.T) *Handler {
	logger := zerolog.New(nil).Level(zerolog.Disabled)

	// Create in-memory databases
	ledgerDB, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)
	t.Cleanup(func() { ledgerDB.Close() })

	configDB, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)
	t.Cleanup(func() { configDB.Close() })

	historyDBConn, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)
	t.Cleanup(func() { historyDBConn.Close() })

	// Create ledger tables
	_, err = ledgerDB.Exec(`CREATE TABLE IF NOT EXISTS trades (
		id INTEGER PRIMARY KEY,
		symbol TEXT,
		side TEXT,
		quantity REAL,
		price REAL,
		executed_at TEXT
	)`)
	require.NoError(t, err)

	_, err = ledgerDB.Exec(`CREATE TABLE IF NOT EXISTS dividends (
		id INTEGER PRIMARY KEY,
		symbol TEXT,
		amount REAL,
		payment_date TEXT
	)`)
	require.NoError(t, err)

	// Create portfolio database
	portfolioDB, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)
	t.Cleanup(func() { portfolioDB.Close() })

	// Create portfolio tables with complete schema
	_, err = portfolioDB.Exec(`CREATE TABLE IF NOT EXISTS positions (
		isin TEXT PRIMARY KEY,
		symbol TEXT NOT NULL,
		quantity REAL NOT NULL DEFAULT 0,
		avg_price REAL NOT NULL DEFAULT 0,
		current_price REAL DEFAULT 0,
		currency TEXT DEFAULT 'EUR',
		currency_rate REAL DEFAULT 1.0,
		market_value_eur REAL DEFAULT 0,
		cost_basis_eur REAL DEFAULT 0,
		unrealized_pnl REAL DEFAULT 0,
		unrealized_pnl_pct REAL DEFAULT 0,
		last_updated INTEGER,
		first_bought INTEGER,
		last_sold INTEGER
	)`)
	require.NoError(t, err)

	_, err = portfolioDB.Exec(`CREATE TABLE IF NOT EXISTS position_scores (
		isin TEXT PRIMARY KEY,
		total_score REAL DEFAULT 0
	)`)
	require.NoError(t, err)

	// Create universe database
	universeDB, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)
	t.Cleanup(func() { universeDB.Close() })

	// Create universe tables with complete schema
	_, err = universeDB.Exec(`CREATE TABLE IF NOT EXISTS securities (
		isin TEXT PRIMARY KEY,
		symbol TEXT NOT NULL,
		name TEXT,
		geography TEXT,
		fullExchangeName TEXT,
		industry TEXT,
		currency TEXT DEFAULT 'EUR',
		allow_sell INTEGER DEFAULT 1,
		active INTEGER DEFAULT 1
	)`)
	require.NoError(t, err)

	positionRepo := portfolio.NewPositionRepository(portfolioDB, universeDB, nil, logger)
	historyDB := universe.NewHistoryDB(historyDBConn, nil, logger)
	cashManager := &mockCashManager{}

	// Create real service instances
	// AdaptiveMarketService methods we use (CalculateAdaptiveWeights, CalculateAdaptiveBlend,
	// CalculateAdaptiveQualityGates) are pure calculations that don't require dependencies
	adaptiveService := adaptation.NewAdaptiveMarketService(
		nil, // regimeDetector - not needed for pure calculation methods
		nil, // performanceTracker - optional
		nil, // weightsCalculator - optional
		nil, // repository - optional
		logger,
	)
	marketHoursService := market_hours.NewMarketHoursService()

	// Create RegimePersistence instance
	regimePersistence := market_regime.NewRegimePersistence(configDB, logger)

	return NewHandler(
		positionRepo,
		historyDB,
		ledgerDB,
		regimePersistence,
		cashManager,
		adaptiveService,
		marketHoursService,
		logger,
	)
}

func TestHandleGetComplete(t *testing.T) {
	handler := setupTestHandler(t)

	req := httptest.NewRequest("GET", "/api/snapshots/complete", nil)
	w := httptest.NewRecorder()

	handler.HandleGetComplete(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
	assert.Contains(t, response, "metadata")

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "portfolio")
	assert.Contains(t, data, "market_context")
	assert.Contains(t, data, "risk")
}

func TestHandleGetPortfolioState(t *testing.T) {
	handler := setupTestHandler(t)

	req := httptest.NewRequest("GET", "/api/snapshots/portfolio-state", nil)
	w := httptest.NewRecorder()

	handler.HandleGetPortfolioState(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "positions")
	assert.Contains(t, data, "scores")
	assert.Contains(t, data, "cash_balances")
	assert.Contains(t, data, "metrics")
}

func TestHandleGetMarketContext(t *testing.T) {
	handler := setupTestHandler(t)

	req := httptest.NewRequest("GET", "/api/snapshots/market-context", nil)
	w := httptest.NewRecorder()

	handler.HandleGetMarketContext(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "regime")
	assert.Contains(t, data, "adaptive_weights")
	assert.Contains(t, data, "market_hours")
}

func TestHandleGetPendingActions(t *testing.T) {
	handler := setupTestHandler(t)

	req := httptest.NewRequest("GET", "/api/snapshots/pending-actions", nil)
	w := httptest.NewRecorder()

	handler.HandleGetPendingActions(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "pending_retries")
	// Note: recommendations and opportunities are not yet implemented
}

func TestHandleGetHistoricalSummary(t *testing.T) {
	handler := setupTestHandler(t)

	req := httptest.NewRequest("GET", "/api/snapshots/historical-summary", nil)
	w := httptest.NewRecorder()

	handler.HandleGetHistoricalSummary(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "recent_trades")
	assert.Contains(t, data, "recent_dividends")
	assert.Contains(t, data, "period")
}

func TestHandleGetRiskSnapshot(t *testing.T) {
	handler := setupTestHandler(t)

	req := httptest.NewRequest("GET", "/api/snapshots/risk-snapshot", nil)
	w := httptest.NewRecorder()

	handler.HandleGetRiskSnapshot(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "portfolio_risk")
	assert.Contains(t, data, "concentration")
}

func TestRouteIntegration(t *testing.T) {
	handler := setupTestHandler(t)

	router := chi.NewRouter()
	handler.RegisterRoutes(router)

	tests := []struct {
		name           string
		method         string
		path           string
		expectedStatus int
	}{
		{"get complete snapshot", "GET", "/snapshots/complete", http.StatusOK},
		{"get portfolio state", "GET", "/snapshots/portfolio-state", http.StatusOK},
		{"get market context", "GET", "/snapshots/market-context", http.StatusOK},
		{"get pending actions", "GET", "/snapshots/pending-actions", http.StatusOK},
		{"get historical summary", "GET", "/snapshots/historical-summary", http.StatusOK},
		{"get risk snapshot", "GET", "/snapshots/risk-snapshot", http.StatusOK},
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
