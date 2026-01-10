package handlers

import (
	"database/sql"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aristath/sentinel/internal/clients/yahoo"
	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/dividends"
	"github.com/aristath/sentinel/internal/modules/optimization"
	"github.com/aristath/sentinel/internal/services"
	testingpkg "github.com/aristath/sentinel/internal/testing"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestRegisterRoutes(t *testing.T) {
	// Create mock dependencies
	service := &optimization.OptimizerService{}
	var db *sql.DB = nil
	var yahooClient yahoo.FullClientInterface = nil
	tradernetClient := testingpkg.NewMockBrokerClient()
	currencyExchangeService := &services.CurrencyExchangeService{}
	dividendRepo := &dividends.DividendRepository{}
	var cashManager domain.CashManager = nil

	// Create handler - we're only testing that RegisterRoutes works, not handler execution
	handler := NewHandler(
		service,
		db,
		yahooClient,
		tradernetClient,
		currencyExchangeService,
		dividendRepo,
		cashManager,
		nil, // plannerConfigRepo - not needed for route registration test
		zerolog.Nop(),
	)

	// Create router and register routes - this should not panic
	router := chi.NewRouter()
	require.NotPanics(t, func() {
		handler.RegisterRoutes(router)
	}, "RegisterRoutes should not panic")

	// Test that routes are registered by checking they don't return 404
	// Note: They may return 500 due to nil dependencies, but 404 means route not found
	testCases := []struct {
		method string
		path   string
		name   string
	}{
		{"GET", "/optimizer/", "GetStatus"},
		{"POST", "/optimizer/run", "Run"},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequest(tc.method, tc.path, nil)
			rec := httptest.NewRecorder()

			// Catch panics from nil pointer dereferences
			var panicked bool
			func() {
				defer func() {
					if r := recover(); r != nil {
						panicked = true
						// Panic is OK - it means route was found and handler was called
						// We just need to verify it's not a 404
					}
				}()
				router.ServeHTTP(rec, req)
			}()

			// Route should be registered (not 404)
			// 404 means route not found
			// Panic or 500 means route exists but handler failed (expected with nil deps)
			if !panicked {
				assert.NotEqual(t, http.StatusNotFound, rec.Code, "Route %s %s should be registered (got %d)", tc.method, tc.path, rec.Code)
			} else {
				// Panic means route was found and handler executed (which is what we want to verify)
				assert.True(t, true, "Route %s %s was found (handler executed, panic expected with nil deps)", tc.method, tc.path)
			}
		})
	}
}

func TestRegisterRoutes_RoutePrefix(t *testing.T) {
	// Verify that routes are registered under /optimizer prefix
	service := &optimization.OptimizerService{}
	var db *sql.DB = nil
	var yahooClient yahoo.FullClientInterface = nil
	tradernetClient := testingpkg.NewMockBrokerClient()
	currencyExchangeService := &services.CurrencyExchangeService{}
	dividendRepo := &dividends.DividendRepository{}
	var cashManager domain.CashManager = nil

	handler := NewHandler(
		service,
		db,
		yahooClient,
		tradernetClient,
		currencyExchangeService,
		dividendRepo,
		cashManager,
		nil, // plannerConfigRepo
		zerolog.Nop(),
	)

	router := chi.NewRouter()
	handler.RegisterRoutes(router)

	// Test that routes outside /optimizer prefix return 404
	req := httptest.NewRequest("GET", "/run", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	assert.Equal(t, http.StatusNotFound, rec.Code, "Route without /optimizer prefix should return 404")
}
