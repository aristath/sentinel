package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

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

	// Create trades table
	_, err = db.Exec(`
		CREATE TABLE trades (
			id INTEGER PRIMARY KEY,
			symbol TEXT NOT NULL,
			isin TEXT,
			side TEXT NOT NULL,
			quantity REAL NOT NULL,
			price REAL NOT NULL,
			executed_at TEXT NOT NULL,
			order_id TEXT UNIQUE,
			currency TEXT,
			currency_rate REAL,
			value_eur REAL,
			source TEXT DEFAULT 'tradernet',
			created_at TEXT NOT NULL,
			bucket_id TEXT DEFAULT 'core',
			mode TEXT DEFAULT 'live'
		)
	`)
	require.NoError(t, err)

	// Create cash_flows table
	_, err = db.Exec(`
		CREATE TABLE cash_flows (
			id INTEGER PRIMARY KEY,
			transaction_id TEXT UNIQUE NOT NULL,
			type_doc_id INTEGER NOT NULL,
			transaction_type TEXT,
			date TEXT NOT NULL,
			amount REAL NOT NULL,
			currency TEXT NOT NULL,
			amount_eur REAL NOT NULL,
			status TEXT,
			status_c INTEGER,
			description TEXT,
			params_json TEXT,
			created_at TEXT NOT NULL
		)
	`)
	require.NoError(t, err)

	// Create dividend_history table
	_, err = db.Exec(`
		CREATE TABLE dividend_history (
			id INTEGER PRIMARY KEY,
			symbol TEXT NOT NULL,
			cash_flow_id INTEGER,
			amount REAL NOT NULL,
			currency TEXT NOT NULL,
			amount_eur REAL NOT NULL,
			payment_date TEXT NOT NULL,
			reinvested INTEGER DEFAULT 0,
			reinvested_at TEXT,
			reinvested_quantity INTEGER,
			pending_bonus REAL DEFAULT 0,
			bonus_cleared INTEGER DEFAULT 0,
			cleared_at TEXT,
			created_at TEXT NOT NULL,
			FOREIGN KEY (cash_flow_id) REFERENCES cash_flows(id)
		)
	`)
	require.NoError(t, err)

	// Insert test data
	now := time.Now().Format(time.RFC3339)

	// Test trades
	_, err = db.Exec(`
		INSERT INTO trades (symbol, isin, side, quantity, price, executed_at, order_id, currency, value_eur, created_at)
		VALUES
		('AAPL', 'US0378331005', 'BUY', 10, 150.00, ?, 'ORDER1', 'USD', 1500.00, ?),
		('MSFT', 'US5949181045', 'SELL', 5, 300.00, ?, 'ORDER2', 'USD', 1500.00, ?)
	`, now, now, now, now)
	require.NoError(t, err)

	// Test cash flows
	_, err = db.Exec(`
		INSERT INTO cash_flows (transaction_id, type_doc_id, transaction_type, date, amount, currency, amount_eur, created_at)
		VALUES
		('CF1', 1, 'DEPOSIT', ?, 1000.00, 'EUR', 1000.00, ?),
		('CF2', 2, 'WITHDRAWAL', ?, 500.00, 'EUR', 500.00, ?),
		('CF3', 3, 'DIVIDEND', ?, 50.00, 'EUR', 50.00, ?)
	`, now, now, now, now, now, now)
	require.NoError(t, err)

	// Test dividends
	_, err = db.Exec(`
		INSERT INTO dividend_history (symbol, amount, currency, amount_eur, payment_date, reinvested, created_at)
		VALUES
		('AAPL', 5.00, 'USD', 4.50, ?, 0, ?),
		('MSFT', 10.00, 'USD', 9.00, ?, 1, ?)
	`, now, now, now, now)
	require.NoError(t, err)

	return db
}

func TestHandleGetTrades(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	handler := NewHandler(db, logger)

	req := httptest.NewRequest("GET", "/api/ledger/trades", nil)
	w := httptest.NewRecorder()

	handler.HandleGetTrades(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "data")
	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "trades")
	assert.Contains(t, data, "count")

	trades := data["trades"].([]interface{})
	assert.Equal(t, 2, len(trades))
}

func TestHandleGetTradeByID(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	handler := NewHandler(db, logger)

	req := httptest.NewRequest("GET", "/api/ledger/trades/1", nil)
	w := httptest.NewRecorder()

	handler.HandleGetTradeByID(w, req, "1")

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "symbol")
	assert.Equal(t, "AAPL", data["symbol"])
}

func TestHandleGetTradesSummary(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	handler := NewHandler(db, logger)

	req := httptest.NewRequest("GET", "/api/ledger/trades/summary", nil)
	w := httptest.NewRecorder()

	handler.HandleGetTradesSummary(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "total_trades")
	assert.Contains(t, data, "buy_count")
	assert.Contains(t, data, "sell_count")
}

func TestHandleGetAllCashFlows(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	handler := NewHandler(db, logger)

	req := httptest.NewRequest("GET", "/api/ledger/cash-flows/all", nil)
	w := httptest.NewRecorder()

	handler.HandleGetAllCashFlows(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "cash_flows")
	assert.Contains(t, data, "count")

	cashFlows := data["cash_flows"].([]interface{})
	assert.Equal(t, 3, len(cashFlows))
}

func TestHandleGetCashFlowsSummary(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	handler := NewHandler(db, logger)

	req := httptest.NewRequest("GET", "/api/ledger/cash-flows/summary", nil)
	w := httptest.NewRecorder()

	handler.HandleGetCashFlowsSummary(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "total_count")
}

func TestHandleGetDividendHistory(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	handler := NewHandler(db, logger)

	req := httptest.NewRequest("GET", "/api/ledger/dividends/history", nil)
	w := httptest.NewRecorder()

	handler.HandleGetDividendHistory(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "dividends")
	assert.Contains(t, data, "count")

	dividends := data["dividends"].([]interface{})
	assert.Equal(t, 2, len(dividends))
}

func TestHandleGetDividendReinvestmentStats(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	handler := NewHandler(db, logger)

	req := httptest.NewRequest("GET", "/api/ledger/dividends/reinvestment-stats", nil)
	w := httptest.NewRecorder()

	handler.HandleGetDividendReinvestmentStats(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "total_dividends")
	assert.Contains(t, data, "reinvested_count")
	assert.Contains(t, data, "pending_count")
}

func TestRouteIntegration(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	handler := NewHandler(db, logger)

	router := chi.NewRouter()
	handler.RegisterRoutes(router)

	tests := []struct {
		name           string
		method         string
		path           string
		expectedStatus int
	}{
		{"get trades", "GET", "/ledger/trades", http.StatusOK},
		{"get trade by id", "GET", "/ledger/trades/1", http.StatusOK},
		{"get trades summary", "GET", "/ledger/trades/summary", http.StatusOK},
		{"get all cash flows", "GET", "/ledger/cash-flows/all", http.StatusOK},
		{"get deposits", "GET", "/ledger/cash-flows/deposits", http.StatusOK},
		{"get withdrawals", "GET", "/ledger/cash-flows/withdrawals", http.StatusOK},
		{"get fees", "GET", "/ledger/cash-flows/fees", http.StatusOK},
		{"get cash flows summary", "GET", "/ledger/cash-flows/summary", http.StatusOK},
		{"get dividend history", "GET", "/ledger/dividends/history", http.StatusOK},
		{"get reinvestment stats", "GET", "/ledger/dividends/reinvestment-stats", http.StatusOK},
		{"get pending reinvestments", "GET", "/ledger/dividends/pending-reinvestments", http.StatusOK},
		{"get drip tracking", "GET", "/ledger/drip-tracking", http.StatusOK},
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
