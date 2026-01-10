package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	_ "modernc.org/sqlite"
)

// mockPositionRepository is a simple mock for testing
type mockPositionRepository struct{}

func (m *mockPositionRepository) GetAll() ([]portfolio.Position, error) {
	// Return empty positions for tests that don't need portfolio data
	return []portfolio.Position{}, nil
}

func (m *mockPositionRepository) GetWithSecurityInfo() ([]portfolio.PositionWithSecurity, error) {
	return []portfolio.PositionWithSecurity{}, nil
}

func (m *mockPositionRepository) GetBySymbol(symbol string) (*portfolio.Position, error) {
	return nil, nil
}

func (m *mockPositionRepository) GetByISIN(isin string) (*portfolio.Position, error) {
	return nil, nil
}

func (m *mockPositionRepository) GetByIdentifier(identifier string) (*portfolio.Position, error) {
	return nil, nil
}

func (m *mockPositionRepository) GetCount() (int, error) {
	return 0, nil
}

func (m *mockPositionRepository) GetTotalValue() (float64, error) {
	return 0, nil
}

func (m *mockPositionRepository) Upsert(position portfolio.Position) error {
	return nil
}

func (m *mockPositionRepository) Delete(isin string) error {
	return nil
}

func (m *mockPositionRepository) DeleteAll() error {
	return nil
}

func (m *mockPositionRepository) UpdatePrice(isin string, price float64, currencyRate float64) error {
	return nil
}

func (m *mockPositionRepository) UpdateLastSoldAt(isin string) error {
	return nil
}

// setupTestDB creates an in-memory SQLite database with test data
func setupTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)

	// Create daily_prices table (date is Unix timestamp, matching real schema)
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS daily_prices (
			isin TEXT NOT NULL,
			date INTEGER NOT NULL,
			open REAL NOT NULL,
			high REAL NOT NULL,
			low REAL NOT NULL,
			close REAL NOT NULL,
			volume INTEGER,
			PRIMARY KEY (isin, date)
		)
	`)
	require.NoError(t, err)

	// Insert test price data for volatility/sharpe/sortino calculations
	// Using 10 days of prices with some volatility
	testISIN := "US0378331005" // Apple
	prices := []struct {
		dateStr string
		close   float64
	}{
		{"2024-01-10", 150.00},
		{"2024-01-09", 152.00},
		{"2024-01-08", 148.00},
		{"2024-01-05", 151.00},
		{"2024-01-04", 149.00},
		{"2024-01-03", 153.00},
		{"2024-01-02", 150.00},
		{"2023-12-29", 155.00},
		{"2023-12-28", 152.00},
		{"2023-12-27", 150.00},
	}

	for _, p := range prices {
		// Parse date and convert to Unix timestamp
		parsedTime, err := time.Parse("2006-01-02", p.dateStr)
		require.NoError(t, err)
		dateUnix := parsedTime.Unix()

		_, err = db.Exec(`
			INSERT INTO daily_prices (isin, date, open, high, low, close, volume)
			VALUES (?, ?, ?, ?, ?, ?, ?)
		`, testISIN, dateUnix, p.close, p.close+1, p.close-1, p.close, 1000000)
		require.NoError(t, err)
	}

	return db
}

func TestHandleGetPortfolioVaR(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, &mockPositionRepository{}, logger)

	req := httptest.NewRequest("GET", "/api/risk/portfolio/var", nil)
	w := httptest.NewRecorder()

	handler.HandleGetPortfolioVaR(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	// Verify response structure
	assert.Contains(t, response, "data")
	assert.Contains(t, response, "metadata")

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "var_95")
	assert.Contains(t, data, "var_99")
}

func TestHandleGetPortfolioCVaR(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, &mockPositionRepository{}, logger)

	req := httptest.NewRequest("GET", "/api/risk/portfolio/cvar", nil)
	w := httptest.NewRecorder()

	handler.HandleGetPortfolioCVaR(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "cvar_95")
	assert.Contains(t, data, "cvar_99")
	assert.Contains(t, data, "contributions")
}

func TestHandleGetPortfolioVolatility(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, &mockPositionRepository{}, logger)

	req := httptest.NewRequest("GET", "/api/risk/portfolio/volatility", nil)
	w := httptest.NewRecorder()

	handler.HandleGetPortfolioVolatility(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "annualized_volatility")
}

func TestHandleGetPortfolioSharpe(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, &mockPositionRepository{}, logger)

	req := httptest.NewRequest("GET", "/api/risk/portfolio/sharpe", nil)
	w := httptest.NewRecorder()

	handler.HandleGetPortfolioSharpe(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "sharpe_ratio")
}

func TestHandleGetPortfolioSortino(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, &mockPositionRepository{}, logger)

	req := httptest.NewRequest("GET", "/api/risk/portfolio/sortino", nil)
	w := httptest.NewRecorder()

	handler.HandleGetPortfolioSortino(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "sortino_ratio")
}

func TestHandleGetPortfolioMaxDrawdown(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, &mockPositionRepository{}, logger)

	req := httptest.NewRequest("GET", "/api/risk/portfolio/max-drawdown", nil)
	w := httptest.NewRecorder()

	handler.HandleGetPortfolioMaxDrawdown(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "max_drawdown")
	assert.Contains(t, data, "current_drawdown")
	assert.Contains(t, data, "days_in_drawdown")
}

func TestHandleGetSecurityVolatility(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, &mockPositionRepository{}, logger)

	tests := []struct {
		name           string
		isin           string
		expectedStatus int
		hasData        bool
	}{
		{
			name:           "valid ISIN with data",
			isin:           "US0378331005",
			expectedStatus: http.StatusOK,
			hasData:        true,
		},
		{
			name:           "ISIN with no data returns zero volatility",
			isin:           "INVALID123",
			expectedStatus: http.StatusOK,
			hasData:        false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/api/risk/securities/"+tt.isin+"/volatility", nil)
			w := httptest.NewRecorder()

			handler.HandleGetSecurityVolatility(w, req, tt.isin)

			assert.Equal(t, tt.expectedStatus, w.Code)

			var response map[string]interface{}
			err := json.NewDecoder(w.Body).Decode(&response)
			require.NoError(t, err)

			data := response["data"].(map[string]interface{})
			assert.Equal(t, tt.isin, data["isin"])
			assert.Contains(t, data, "annualized_volatility")

			if tt.hasData {
				assert.Greater(t, data["annualized_volatility"].(float64), 0.0)
			}
		})
	}
}

func TestHandleGetSecuritySharpe(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, &mockPositionRepository{}, logger)

	tests := []struct {
		name           string
		isin           string
		expectedStatus int
	}{
		{
			name:           "valid ISIN with data",
			isin:           "US0378331005",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "ISIN with no data returns calculated result",
			isin:           "INVALID123",
			expectedStatus: http.StatusOK,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/api/risk/securities/"+tt.isin+"/sharpe", nil)
			w := httptest.NewRecorder()

			handler.HandleGetSecuritySharpe(w, req, tt.isin)

			assert.Equal(t, tt.expectedStatus, w.Code)

			var response map[string]interface{}
			err := json.NewDecoder(w.Body).Decode(&response)
			require.NoError(t, err)

			data := response["data"].(map[string]interface{})
			assert.Equal(t, tt.isin, data["isin"])
			assert.Contains(t, data, "sharpe_ratio")
		})
	}
}

func TestHandleGetSecuritySortino(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, &mockPositionRepository{}, logger)

	tests := []struct {
		name           string
		isin           string
		expectedStatus int
	}{
		{
			name:           "valid ISIN with data",
			isin:           "US0378331005",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "ISIN with no data returns calculated result",
			isin:           "INVALID123",
			expectedStatus: http.StatusOK,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/api/risk/securities/"+tt.isin+"/sortino", nil)
			w := httptest.NewRecorder()

			handler.HandleGetSecuritySortino(w, req, tt.isin)

			assert.Equal(t, tt.expectedStatus, w.Code)

			var response map[string]interface{}
			err := json.NewDecoder(w.Body).Decode(&response)
			require.NoError(t, err)

			data := response["data"].(map[string]interface{})
			assert.Equal(t, tt.isin, data["isin"])
			assert.Contains(t, data, "sortino_ratio")
		})
	}
}

func TestHandleGetSecurityMaxDrawdown(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, &mockPositionRepository{}, logger)

	tests := []struct {
		name           string
		isin           string
		expectedStatus int
	}{
		{
			name:           "valid ISIN with data",
			isin:           "US0378331005",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "ISIN with no data returns calculated result",
			isin:           "INVALID123",
			expectedStatus: http.StatusOK,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/api/risk/securities/"+tt.isin+"/max-drawdown", nil)
			w := httptest.NewRecorder()

			handler.HandleGetSecurityMaxDrawdown(w, req, tt.isin)

			assert.Equal(t, tt.expectedStatus, w.Code)

			var response map[string]interface{}
			err := json.NewDecoder(w.Body).Decode(&response)
			require.NoError(t, err)

			data := response["data"].(map[string]interface{})
			assert.Equal(t, tt.isin, data["isin"])
			assert.Contains(t, data, "metrics")
		})
	}
}

func TestHandleGetSecurityBeta(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, &mockPositionRepository{}, logger)

	req := httptest.NewRequest("GET", "/api/risk/securities/US0378331005/beta", nil)
	w := httptest.NewRecorder()

	handler.HandleGetSecurityBeta(w, req, "US0378331005")

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Equal(t, "US0378331005", data["isin"])
	assert.Contains(t, data, "beta")
	assert.Equal(t, 1.0, data["beta"].(float64))
}

func TestHandleGetKellySizes(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, &mockPositionRepository{}, logger)

	req := httptest.NewRequest("GET", "/api/risk/kelly-sizes", nil)
	w := httptest.NewRecorder()

	handler.HandleGetKellySizes(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "kelly_sizes")
	kellySizes := data["kelly_sizes"].([]interface{})
	assert.Equal(t, 0, len(kellySizes))
}

func TestHandleGetKellySize(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, &mockPositionRepository{}, logger)

	req := httptest.NewRequest("GET", "/api/risk/kelly-sizes/US0378331005", nil)
	w := httptest.NewRecorder()

	handler.HandleGetKellySize(w, req, "US0378331005")

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Equal(t, "US0378331005", data["isin"])
	assert.Contains(t, data, "kelly_fraction")
	assert.Contains(t, data, "constrained_fraction")
}

func TestRouteIntegration(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, &mockPositionRepository{}, logger)

	router := chi.NewRouter()
	handler.RegisterRoutes(router)

	tests := []struct {
		name           string
		method         string
		path           string
		expectedStatus int
	}{
		{"portfolio var", "GET", "/risk/portfolio/var", http.StatusOK},
		{"portfolio cvar", "GET", "/risk/portfolio/cvar", http.StatusOK},
		{"portfolio volatility", "GET", "/risk/portfolio/volatility", http.StatusOK},
		{"portfolio sharpe", "GET", "/risk/portfolio/sharpe", http.StatusOK},
		{"portfolio sortino", "GET", "/risk/portfolio/sortino", http.StatusOK},
		{"portfolio max-drawdown", "GET", "/risk/portfolio/max-drawdown", http.StatusOK},
		{"security volatility", "GET", "/risk/securities/US0378331005/volatility", http.StatusOK},
		{"security sharpe", "GET", "/risk/securities/US0378331005/sharpe", http.StatusOK},
		{"security sortino", "GET", "/risk/securities/US0378331005/sortino", http.StatusOK},
		{"security max-drawdown", "GET", "/risk/securities/US0378331005/max-drawdown", http.StatusOK},
		{"security beta", "GET", "/risk/securities/US0378331005/beta", http.StatusOK},
		{"kelly sizes", "GET", "/risk/kelly-sizes", http.StatusOK},
		{"kelly size by isin", "GET", "/risk/kelly-sizes/US0378331005", http.StatusOK},
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
