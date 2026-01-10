package handlers

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestRegisterRoutes(t *testing.T) {
	// Create mock dependencies
	// For evaluation, we'll create a minimal handler with nil dependencies
	handler := NewHandler(nil, zerolog.Nop())

	// Create router and register routes - this should not panic
	router := chi.NewRouter()
	require.NotPanics(t, func() {
		handler.RegisterRoutes(router)
	}, "RegisterRoutes should not panic")

	// Test that routes are registered by checking they don't return 404
	// Note: They may return 500 due to nil dependencies, but 404 means route not found
	// Note: Routes are mounted at /api/v1, not /api
	testCases := []struct {
		method string
		path   string
		name   string
	}{
		{"POST", "/api/v1/evaluate/batch", "EvaluateBatch"},
		{"POST", "/api/v1/evaluate/single", "EvaluateSingle"},
		{"POST", "/api/v1/evaluate/compare", "EvaluateCompare"},
		{"POST", "/api/v1/evaluate/monte-carlo", "EvaluateMonteCarlo"},
		{"POST", "/api/v1/evaluate/stochastic", "EvaluateStochastic"},
		{"GET", "/api/v1/evaluation/criteria", "GetEvaluationCriteria"},
		{"POST", "/api/v1/simulate/batch", "SimulateBatch"},
		{"POST", "/api/v1/simulate/custom-prices", "SimulateCustomPrices"},
		{"POST", "/api/v1/monte-carlo/advanced", "MonteCarloAdvanced"},
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
	// Verify that routes are registered under /api/v1 prefix
	handler := NewHandler(nil, zerolog.Nop())

	router := chi.NewRouter()
	handler.RegisterRoutes(router)

	// Test that routes outside /api/v1 prefix return 404
	req := httptest.NewRequest("POST", "/evaluate/batch", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	assert.Equal(t, http.StatusNotFound, rec.Code, "Route without /api/v1 prefix should return 404")
}
