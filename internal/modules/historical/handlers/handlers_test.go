package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aristath/sentinel/internal/modules/universe"
	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestHandleGetDailyPrices(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, logger)

	tests := []struct {
		name           string
		isin           string
		queryParams    string
		expectedStatus int
		validate       func(*testing.T, *httptest.ResponseRecorder)
	}{
		{
			name:           "valid request",
			isin:           "US0378331005",
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
			name:           "with limit",
			isin:           "US0378331005",
			queryParams:    "?limit=10",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "with date range",
			isin:           "US0378331005",
			queryParams:    "?from=2024-01-01&to=2024-12-31",
			expectedStatus: http.StatusOK,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/api/historical/prices/daily/"+tt.isin+tt.queryParams, nil)
			w := httptest.NewRecorder()

			handler.HandleGetDailyPrices(w, req, tt.isin)

			assert.Equal(t, tt.expectedStatus, w.Code)
			if tt.validate != nil {
				tt.validate(t, w)
			}
		})
	}
}

func TestHandleGetMonthlyPrices(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, logger)

	tests := []struct {
		name           string
		isin           string
		expectedStatus int
	}{
		{
			name:           "valid request",
			isin:           "US0378331005",
			expectedStatus: http.StatusOK,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/api/historical/prices/monthly/"+tt.isin, nil)
			w := httptest.NewRecorder()

			handler.HandleGetMonthlyPrices(w, req, tt.isin)

			assert.Equal(t, tt.expectedStatus, w.Code)
		})
	}
}

func TestHandleGetLatestPrice(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, logger)

	req := httptest.NewRequest("GET", "/api/historical/prices/latest/US0378331005", nil)
	w := httptest.NewRecorder()

	handler.HandleGetLatestPrice(w, req, "US0378331005")

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestHandleGetPriceRange(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, logger)

	tests := []struct {
		name           string
		queryParams    string
		expectedStatus int
	}{
		{
			name:           "valid request",
			queryParams:    "?isins=US0378331005,IE00B4L5Y983",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "missing isins",
			queryParams:    "",
			expectedStatus: http.StatusBadRequest,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/api/historical/prices/range"+tt.queryParams, nil)
			w := httptest.NewRecorder()

			handler.HandleGetPriceRange(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
		})
	}
}

func TestHandleGetDailyReturns(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, logger)

	req := httptest.NewRequest("GET", "/api/historical/returns/daily/US0378331005", nil)
	w := httptest.NewRecorder()

	handler.HandleGetDailyReturns(w, req, "US0378331005")

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestHandleGetMonthlyReturns(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, logger)

	req := httptest.NewRequest("GET", "/api/historical/returns/monthly/US0378331005", nil)
	w := httptest.NewRecorder()

	handler.HandleGetMonthlyReturns(w, req, "US0378331005")

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestHandleGetCorrelationMatrix(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, logger)

	req := httptest.NewRequest("GET", "/api/historical/returns/correlation-matrix", nil)
	w := httptest.NewRecorder()

	handler.HandleGetCorrelationMatrix(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestHandleGetExchangeRateHistory(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, logger)

	tests := []struct {
		name           string
		queryParams    string
		expectedStatus int
	}{
		{
			name:           "valid request",
			queryParams:    "?from_currency=USD&to_currency=EUR",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "missing from_currency",
			queryParams:    "?to_currency=EUR",
			expectedStatus: http.StatusBadRequest,
		},
		{
			name:           "missing to_currency",
			queryParams:    "?from_currency=USD",
			expectedStatus: http.StatusBadRequest,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/api/historical/exchange-rates/history"+tt.queryParams, nil)
			w := httptest.NewRecorder()

			handler.HandleGetExchangeRateHistory(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
		})
	}
}

func TestHandleGetCurrentExchangeRates(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, logger)

	req := httptest.NewRequest("GET", "/api/historical/exchange-rates/current", nil)
	w := httptest.NewRecorder()

	handler.HandleGetCurrentExchangeRates(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestHandleGetExchangeRate(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	handler := NewHandler(historyDB, logger)

	req := httptest.NewRequest("GET", "/api/historical/exchange-rates/USD/EUR", nil)
	w := httptest.NewRecorder()

	handler.HandleGetExchangeRate(w, req, "USD", "EUR")

	assert.Equal(t, http.StatusOK, w.Code)
}

// setupTestDB creates an in-memory SQLite database for testing
func setupTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)

	// Create tables
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS daily_prices (
			isin TEXT NOT NULL,
			date INTEGER NOT NULL,
			open REAL,
			high REAL,
			low REAL,
			close REAL NOT NULL,
			volume INTEGER,
			adjusted_close REAL,
			PRIMARY KEY (isin, date)
		);

		CREATE TABLE IF NOT EXISTS monthly_prices (
			isin TEXT NOT NULL,
			year_month TEXT NOT NULL,
			avg_close REAL,
			avg_adj_close REAL,
			source TEXT,
			created_at INTEGER,
			PRIMARY KEY (isin, year_month)
		);

		CREATE TABLE IF NOT EXISTS exchange_rates (
			from_currency TEXT NOT NULL,
			to_currency TEXT NOT NULL,
			date INTEGER NOT NULL,
			rate REAL NOT NULL,
			PRIMARY KEY (from_currency, to_currency, date)
		);
	`)
	require.NoError(t, err)

	return db
}
