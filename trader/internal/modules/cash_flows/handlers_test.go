package cash_flows

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// MockTradernetClient for testing
type MockTradernetClient struct {
	connected       bool
	cashFlows       []APITransaction
	shouldFailFetch bool
}

func (m *MockTradernetClient) GetAllCashFlows(limit int) ([]APITransaction, error) {
	if m.shouldFailFetch {
		return nil, fmt.Errorf("mock fetch error")
	}
	return m.cashFlows, nil
}

func (m *MockTradernetClient) IsConnected() bool {
	return m.connected
}

func TestHandleGetCashFlows_All(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())
	handler := NewHandler(repo, nil, nil, zerolog.Nop())

	// Create test data
	txType := "DEPOSIT"
	cashFlow := &CashFlow{
		TransactionID:   "TEST_TX",
		TypeDocID:       100,
		TransactionType: &txType,
		Date:            "2024-01-15",
		Amount:          1000.00,
		Currency:        "EUR",
		AmountEUR:       1000.00,
	}
	repo.Create(cashFlow)

	// Test GET all
	req := httptest.NewRequest("GET", "/cash-flows", nil)
	w := httptest.NewRecorder()
	handler.HandleGetCashFlows(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

	var cashFlows []CashFlow
	err := json.NewDecoder(w.Body).Decode(&cashFlows)
	require.NoError(t, err)
	assert.Len(t, cashFlows, 1)
	assert.Equal(t, "TEST_TX", cashFlows[0].TransactionID)
}

func TestHandleGetCashFlows_WithLimit(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())
	handler := NewHandler(repo, nil, nil, zerolog.Nop())

	// Create 5 cash flows
	for i := 1; i <= 5; i++ {
		txType := "DEPOSIT"
		cashFlow := &CashFlow{
			TransactionID:   fmt.Sprintf("TX%d", i),
			TypeDocID:       100,
			TransactionType: &txType,
			Date:            fmt.Sprintf("2024-01-%02d", i+10),
			Amount:          float64(i * 100),
			Currency:        "EUR",
			AmountEUR:       float64(i * 100),
		}
		repo.Create(cashFlow)
	}

	// Test with limit
	req := httptest.NewRequest("GET", "/cash-flows?limit=3", nil)
	w := httptest.NewRecorder()
	handler.HandleGetCashFlows(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var cashFlows []CashFlow
	err := json.NewDecoder(w.Body).Decode(&cashFlows)
	require.NoError(t, err)
	assert.Len(t, cashFlows, 3)
}

func TestHandleGetCashFlows_InvalidLimit(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())
	handler := NewHandler(repo, nil, nil, zerolog.Nop())

	tests := []struct {
		name       string
		limitParam string
	}{
		{"too high", "limit=99999"},
		{"zero", "limit=0"},
		{"negative", "limit=-1"},
		{"non-numeric", "limit=abc"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/cash-flows?"+tt.limitParam, nil)
			w := httptest.NewRecorder()
			handler.HandleGetCashFlows(w, req)

			assert.Equal(t, http.StatusBadRequest, w.Code)
			assert.Contains(t, w.Body.String(), "Invalid limit")
		})
	}
}

func TestHandleGetCashFlows_ByTransactionType(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())
	handler := NewHandler(repo, nil, nil, zerolog.Nop())

	// Create cash flows of different types
	deposit := "DEPOSIT"
	withdrawal := "WITHDRAWAL"

	repo.Create(&CashFlow{TransactionID: "TX1", TypeDocID: 100, TransactionType: &deposit, Date: "2024-01-10", Amount: 1000, Currency: "EUR", AmountEUR: 1000})
	repo.Create(&CashFlow{TransactionID: "TX2", TypeDocID: 101, TransactionType: &withdrawal, Date: "2024-01-15", Amount: 200, Currency: "EUR", AmountEUR: 200})
	repo.Create(&CashFlow{TransactionID: "TX3", TypeDocID: 100, TransactionType: &deposit, Date: "2024-01-20", Amount: 500, Currency: "EUR", AmountEUR: 500})

	// Test filter by DEPOSIT
	req := httptest.NewRequest("GET", "/cash-flows?transaction_type=DEPOSIT", nil)
	w := httptest.NewRecorder()
	handler.HandleGetCashFlows(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var cashFlows []CashFlow
	err := json.NewDecoder(w.Body).Decode(&cashFlows)
	require.NoError(t, err)
	assert.Len(t, cashFlows, 2)
}

func TestHandleGetCashFlows_ByDateRange(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())
	handler := NewHandler(repo, nil, nil, zerolog.Nop())

	// Create cash flows on different dates
	deposit := "DEPOSIT"
	repo.Create(&CashFlow{TransactionID: "TX1", TypeDocID: 100, TransactionType: &deposit, Date: "2024-01-10", Amount: 1000, Currency: "EUR", AmountEUR: 1000})
	repo.Create(&CashFlow{TransactionID: "TX2", TypeDocID: 100, TransactionType: &deposit, Date: "2024-01-15", Amount: 500, Currency: "EUR", AmountEUR: 500})
	repo.Create(&CashFlow{TransactionID: "TX3", TypeDocID: 100, TransactionType: &deposit, Date: "2024-01-20", Amount: 300, Currency: "EUR", AmountEUR: 300})

	// Test date range that includes only middle transaction
	req := httptest.NewRequest("GET", "/cash-flows?start_date=2024-01-12&end_date=2024-01-18", nil)
	w := httptest.NewRecorder()
	handler.HandleGetCashFlows(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var cashFlows []CashFlow
	err := json.NewDecoder(w.Body).Decode(&cashFlows)
	require.NoError(t, err)
	assert.Len(t, cashFlows, 1)
	assert.Equal(t, "2024-01-15", cashFlows[0].Date)
}

func TestHandleGetCashFlows_InvalidDateFormat(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())
	handler := NewHandler(repo, nil, nil, zerolog.Nop())

	tests := []struct {
		name      string
		startDate string
		endDate   string
	}{
		{"invalid format start", "01-01-2024", "2024-01-31"},
		{"invalid format end", "2024-01-01", "31-01-2024"},
		{"both invalid", "01/01/2024", "31/01/2024"},
		{"garbage", "not-a-date", "also-not-a-date"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", fmt.Sprintf("/cash-flows?start_date=%s&end_date=%s", tt.startDate, tt.endDate), nil)
			w := httptest.NewRecorder()
			handler.HandleGetCashFlows(w, req)

			assert.Equal(t, http.StatusBadRequest, w.Code)
			assert.Contains(t, w.Body.String(), "Invalid date format")
		})
	}
}

func TestHandleGetCashFlows_InvalidDateRange(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())
	handler := NewHandler(repo, nil, nil, zerolog.Nop())

	// start_date > end_date
	req := httptest.NewRequest("GET", "/cash-flows?start_date=2024-01-31&end_date=2024-01-01", nil)
	w := httptest.NewRecorder()
	handler.HandleGetCashFlows(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
	assert.Contains(t, w.Body.String(), "start_date must be <= end_date")
}

func TestHandleSyncCashFlows_Success(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	// Mock Tradernet client with test data
	mockClient := &MockTradernetClient{
		connected: true,
		cashFlows: []APITransaction{
			{
				TransactionID:   "SYNC_TX_1",
				TypeDocID:       100,
				TransactionType: "DEPOSIT",
				Date:            "2024-01-15",
				Amount:          1000.00,
				Currency:        "EUR",
				AmountEUR:       1000.00,
				Status:          "COMPLETED",
				StatusC:         1,
				Description:     "Test sync deposit",
				Params:          map[string]interface{}{"source": "test"},
			},
			{
				TransactionID:   "SYNC_TX_2",
				TypeDocID:       101,
				TransactionType: "WITHDRAWAL",
				Date:            "2024-01-16",
				Amount:          500.00,
				Currency:        "EUR",
				AmountEUR:       500.00,
				Status:          "COMPLETED",
				StatusC:         1,
				Description:     "Test sync withdrawal",
				Params:          map[string]interface{}{},
			},
		},
	}

	handler := NewHandler(repo, nil, mockClient, zerolog.Nop())

	req := httptest.NewRequest("GET", "/cash-flows/sync", nil)
	w := httptest.NewRecorder()
	handler.HandleSyncCashFlows(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Equal(t, float64(2), response["synced"])
	assert.Equal(t, float64(2), response["total_from_api"])
	assert.Contains(t, response["message"], "Synced 2 new cash flows")

	// Verify data was actually inserted
	all, _ := repo.GetAll(nil)
	assert.Len(t, all, 2)
}

func TestHandleSyncCashFlows_DuplicatePrevention(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	mockClient := &MockTradernetClient{
		connected: true,
		cashFlows: []APITransaction{
			{
				TransactionID:   "DUP_TX",
				TypeDocID:       100,
				TransactionType: "DEPOSIT",
				Date:            "2024-01-15",
				Amount:          1000.00,
				Currency:        "EUR",
				AmountEUR:       1000.00,
				Status:          "COMPLETED",
				StatusC:         1,
				Description:     "Duplicate test",
			},
		},
	}

	handler := NewHandler(repo, nil, mockClient, zerolog.Nop())

	// First sync
	req := httptest.NewRequest("GET", "/cash-flows/sync", nil)
	w := httptest.NewRecorder()
	handler.HandleSyncCashFlows(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response1 map[string]interface{}
	json.NewDecoder(w.Body).Decode(&response1)
	assert.Equal(t, float64(1), response1["synced"])

	// Second sync - should skip duplicate
	req2 := httptest.NewRequest("GET", "/cash-flows/sync", nil)
	w2 := httptest.NewRecorder()
	handler.HandleSyncCashFlows(w2, req2)

	assert.Equal(t, http.StatusOK, w2.Code)

	var response2 map[string]interface{}
	json.NewDecoder(w2.Body).Decode(&response2)
	assert.Equal(t, float64(0), response2["synced"], "Second sync should skip duplicate")
	assert.Equal(t, float64(1), response2["total_from_api"])

	// Verify only one record exists
	all, _ := repo.GetAll(nil)
	assert.Len(t, all, 1)
}

func TestHandleSyncCashFlows_TradernetNotConnected(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	mockClient := &MockTradernetClient{
		connected: false,
	}

	handler := NewHandler(repo, nil, mockClient, zerolog.Nop())

	req := httptest.NewRequest("GET", "/cash-flows/sync", nil)
	w := httptest.NewRecorder()
	handler.HandleSyncCashFlows(w, req)

	assert.Equal(t, http.StatusServiceUnavailable, w.Code)
	assert.Contains(t, w.Body.String(), "Tradernet service unavailable")
}

func TestHandleSyncCashFlows_FetchError(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())

	mockClient := &MockTradernetClient{
		connected:       true,
		shouldFailFetch: true,
	}

	handler := NewHandler(repo, nil, mockClient, zerolog.Nop())

	req := httptest.NewRequest("GET", "/cash-flows/sync", nil)
	w := httptest.NewRecorder()
	handler.HandleSyncCashFlows(w, req)

	assert.Equal(t, http.StatusInternalServerError, w.Code)
	assert.Contains(t, w.Body.String(), "Failed to fetch from Tradernet")
}

func TestHandleGetSummary_WithMultipleTypes(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())
	handler := NewHandler(repo, nil, nil, zerolog.Nop())

	// Create cash flows of different types
	deposit := "DEPOSIT"
	refill := "REFILL"
	withdrawal := "WITHDRAWAL"
	dividend := "DIVIDEND"

	repo.Create(&CashFlow{TransactionID: "TX1", TypeDocID: 100, TransactionType: &deposit, Date: "2024-01-10", Amount: 1000, Currency: "EUR", AmountEUR: 1000})
	repo.Create(&CashFlow{TransactionID: "TX2", TypeDocID: 100, TransactionType: &deposit, Date: "2024-01-15", Amount: 500, Currency: "EUR", AmountEUR: 500})
	repo.Create(&CashFlow{TransactionID: "TX3", TypeDocID: 100, TransactionType: &refill, Date: "2024-01-16", Amount: 300, Currency: "EUR", AmountEUR: 300})
	repo.Create(&CashFlow{TransactionID: "TX4", TypeDocID: 101, TransactionType: &withdrawal, Date: "2024-01-20", Amount: 200, Currency: "EUR", AmountEUR: 200})
	repo.Create(&CashFlow{TransactionID: "TX5", TypeDocID: 102, TransactionType: &dividend, Date: "2024-01-25", Amount: 50, Currency: "EUR", AmountEUR: 50})

	req := httptest.NewRequest("GET", "/cash-flows/summary", nil)
	w := httptest.NewRecorder()
	handler.HandleGetSummary(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

	var summary map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&summary)
	require.NoError(t, err)

	// Verify totals
	assert.Equal(t, float64(5), summary["total_transactions"])

	// Verify deposits (DEPOSIT + REFILL)
	assert.Equal(t, 1800.0, summary["total_deposits"])

	// Verify withdrawals
	assert.Equal(t, 200.0, summary["total_withdrawals"])

	// Verify net cash flow
	assert.Equal(t, 1600.0, summary["net_cash_flow"])

	// Verify by_type grouping
	byType := summary["by_type"].(map[string]interface{})
	assert.Len(t, byType, 4)

	depositSummary := byType["DEPOSIT"].(map[string]interface{})
	assert.Equal(t, float64(2), depositSummary["count"])
	assert.Equal(t, 1500.0, depositSummary["total"])

	withdrawalSummary := byType["WITHDRAWAL"].(map[string]interface{})
	assert.Equal(t, float64(1), withdrawalSummary["count"])
	assert.Equal(t, 200.0, withdrawalSummary["total"])
}

func TestHandleGetSummary_EmptyRepository(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())
	handler := NewHandler(repo, nil, nil, zerolog.Nop())

	req := httptest.NewRequest("GET", "/cash-flows/summary", nil)
	w := httptest.NewRecorder()
	handler.HandleGetSummary(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var summary map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&summary)
	require.NoError(t, err)

	assert.Equal(t, float64(0), summary["total_transactions"])
	assert.Equal(t, 0.0, summary["total_deposits"])
	assert.Equal(t, 0.0, summary["total_withdrawals"])
	assert.Equal(t, 0.0, summary["net_cash_flow"])

	byType := summary["by_type"].(map[string]interface{})
	assert.Len(t, byType, 0)
}

func TestHandleGetSummary_NullTransactionTypes(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db, zerolog.Nop())
	handler := NewHandler(repo, nil, nil, zerolog.Nop())

	// Create cash flow with null transaction type
	repo.Create(&CashFlow{TransactionID: "TX_NULL", TypeDocID: 100, TransactionType: nil, Date: "2024-01-10", Amount: 1000, Currency: "EUR", AmountEUR: 1000})

	req := httptest.NewRequest("GET", "/cash-flows/summary", nil)
	w := httptest.NewRecorder()
	handler.HandleGetSummary(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var summary map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&summary)
	require.NoError(t, err)

	// Should have 1 transaction but type summary should be empty (null types skipped)
	assert.Equal(t, float64(1), summary["total_transactions"])

	byType := summary["by_type"].(map[string]interface{})
	assert.Len(t, byType, 0)
}
