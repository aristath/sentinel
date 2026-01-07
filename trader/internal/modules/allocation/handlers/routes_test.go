package handlers

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/events"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestRegisterRoutes(t *testing.T) {
	// Create mock dependencies
	portfolioSummaryProvider := &mockPortfolioSummaryProvider{}
	eventManager := &events.Manager{}

	// Create handler - we're only testing that RegisterRoutes works, not handler execution
	handler := NewHandler(
		nil, // allocRepo - nil is OK for route registration test
		nil, // groupingRepo
		nil, // alertService
		portfolioSummaryProvider,
		eventManager,
		zerolog.Nop(),
	)

	// Create router and register routes - this should not panic
	router := chi.NewRouter()
	require.NotPanics(t, func() {
		handler.RegisterRoutes(router)
	}, "RegisterRoutes should not panic")

	// Test that routes are registered by checking they don't return 404
	// Note: They may return 500 due to nil repositories, but 404 means route not found
	testCases := []struct {
		method string
		path   string
		name   string
	}{
		{"GET", "/allocation/targets", "GetTargets"},
		{"GET", "/allocation/current", "GetCurrentAllocation"},
		{"GET", "/allocation/deviations", "GetDeviations"},
		{"GET", "/allocation/groups/country", "GetCountryGroups"},
		{"GET", "/allocation/groups/industry", "GetIndustryGroups"},
		{"PUT", "/allocation/groups/country", "UpdateCountryGroup"},
		{"PUT", "/allocation/groups/industry", "UpdateIndustryGroup"},
		{"DELETE", "/allocation/groups/country/test-group", "DeleteCountryGroup"},
		{"DELETE", "/allocation/groups/industry/test-group", "DeleteIndustryGroup"},
		{"GET", "/allocation/groups/available/countries", "GetAvailableCountries"},
		{"GET", "/allocation/groups/available/industries", "GetAvailableIndustries"},
		{"GET", "/allocation/groups/allocation", "GetGroupAllocation"},
		{"PUT", "/allocation/groups/targets/country", "UpdateCountryGroupTargets"},
		{"PUT", "/allocation/groups/targets/industry", "UpdateIndustryGroupTargets"},
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
			// Panic or 500 means route exists but handler failed (expected with nil repos)
			if !panicked {
				assert.NotEqual(t, http.StatusNotFound, rec.Code, "Route %s %s should be registered (got %d)", tc.method, tc.path, rec.Code)
			} else {
				// Panic means route was found and handler executed (which is what we want to verify)
				assert.True(t, true, "Route %s %s was found (handler executed, panic expected with nil repos)", tc.method, tc.path)
			}
		})
	}
}

func TestRegisterRoutes_RoutePrefix(t *testing.T) {
	// Verify that routes are registered under /allocation prefix
	portfolioSummaryProvider := &mockPortfolioSummaryProvider{}
	eventManager := &events.Manager{}

	handler := NewHandler(
		nil, // allocRepo
		nil, // groupingRepo
		nil, // alertService
		portfolioSummaryProvider,
		eventManager,
		zerolog.Nop(),
	)

	router := chi.NewRouter()
	handler.RegisterRoutes(router)

	// Test that routes outside /allocation prefix return 404
	req := httptest.NewRequest("GET", "/targets", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	assert.Equal(t, http.StatusNotFound, rec.Code, "Route without /allocation prefix should return 404")
}

// mockPortfolioSummaryProvider is a mock implementation for testing
type mockPortfolioSummaryProvider struct{}

func (m *mockPortfolioSummaryProvider) GetPortfolioSummary() (domain.PortfolioSummary, error) {
	return domain.PortfolioSummary{}, nil
}
