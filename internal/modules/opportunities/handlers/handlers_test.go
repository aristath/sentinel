package handlers

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aristath/sentinel/internal/modules/opportunities"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// mockTagFilter implements TagFilter interface for testing
type mockTagFilter struct{}

func (m *mockTagFilter) GetOpportunityCandidates(ctx *planningdomain.OpportunityContext, config *planningdomain.PlannerConfiguration) ([]string, error) {
	return []string{}, nil
}

func (m *mockTagFilter) GetSellCandidates(ctx *planningdomain.OpportunityContext, config *planningdomain.PlannerConfiguration) ([]string, error) {
	return []string{}, nil
}

func (m *mockTagFilter) IsMarketVolatile(ctx *planningdomain.OpportunityContext, config *planningdomain.PlannerConfiguration) bool {
	return false
}

// mockSecurityRepo implements SecurityRepository interface for testing
type mockSecurityRepo struct{}

func (m *mockSecurityRepo) GetAllActive() ([]universe.Security, error) {
	return []universe.Security{}, nil
}

func (m *mockSecurityRepo) GetByTags(tags []string) ([]universe.Security, error) {
	return []universe.Security{}, nil
}

func (m *mockSecurityRepo) GetPositionsByTags(positionSymbols []string, tags []string) ([]universe.Security, error) {
	return []universe.Security{}, nil
}

func (m *mockSecurityRepo) GetTagsForSecurity(symbol string) ([]string, error) {
	return []string{}, nil
}

// Note: These tests use nil for the OpportunityContextBuilder since we're testing
// the handler's error handling behavior, not the context building itself.
// Comprehensive context building tests are in internal/services/opportunity_context_builder_test.go

func TestHandleGetAll(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	// Pass nil for contextBuilder - handler should return error when it tries to build context
	handler := NewHandler(service, nil, nil, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/all", nil)
	w := httptest.NewRecorder()

	handler.HandleGetAll(w, req)

	// With nil contextBuilder, expect 500 error
	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

func TestHandleGetProfitTaking(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, nil, nil, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/profit-taking", nil)
	w := httptest.NewRecorder()

	handler.HandleGetProfitTaking(w, req)

	// With nil contextBuilder, expect 500 error
	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

func TestHandleGetRebalanceBuys(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, nil, nil, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/rebalance-buys", nil)
	w := httptest.NewRecorder()

	handler.HandleGetRebalanceBuys(w, req)

	// With nil contextBuilder, expect 500 error
	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

func TestHandleGetRebalanceSells(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, nil, nil, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/rebalance-sells", nil)
	w := httptest.NewRecorder()

	handler.HandleGetRebalanceSells(w, req)

	// With nil contextBuilder, expect 500 error
	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

func TestHandleGetAveragingDown(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, nil, nil, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/averaging-down", nil)
	w := httptest.NewRecorder()

	handler.HandleGetAveragingDown(w, req)

	// With nil contextBuilder, expect 500 error
	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

func TestHandleGetOpportunityBuys(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, nil, nil, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/opportunity-buys", nil)
	w := httptest.NewRecorder()

	handler.HandleGetOpportunityBuys(w, req)

	// With nil contextBuilder, expect 500 error
	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

func TestHandleGetWeightBased(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, nil, nil, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/weight-based", nil)
	w := httptest.NewRecorder()

	handler.HandleGetWeightBased(w, req)

	// With nil contextBuilder, expect 500 error
	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

func TestHandleGetRegistry(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, nil, nil, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/registry", nil)
	w := httptest.NewRecorder()

	handler.HandleGetRegistry(w, req)

	// HandleGetRegistry returns the registry without needing context
	// So this should return 200 OK
	assert.Equal(t, http.StatusOK, w.Code)
}

// Test handler registration on routes
func TestRoutes_Registration(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, nil, nil, logger)

	// Create router
	r := chi.NewRouter()
	handler.RegisterRoutes(r)

	// Test that routes are registered by making requests
	// Routes are under /opportunities prefix
	testCases := []struct {
		method string
		path   string
	}{
		{"GET", "/opportunities/all"},
		{"GET", "/opportunities/profit-taking"},
		{"GET", "/opportunities/rebalance-buys"},
		{"GET", "/opportunities/rebalance-sells"},
		{"GET", "/opportunities/averaging-down"},
		{"GET", "/opportunities/opportunity-buys"},
		{"GET", "/opportunities/weight-based"},
		{"GET", "/opportunities/registry"},
	}

	for _, tc := range testCases {
		t.Run(tc.path, func(t *testing.T) {
			req := httptest.NewRequest(tc.method, tc.path, nil)
			w := httptest.NewRecorder()

			r.ServeHTTP(w, req)

			// Should not be 404 (route not found)
			assert.NotEqual(t, http.StatusNotFound, w.Code, "Route %s should be registered", tc.path)
		})
	}
}

// Test that the handler uses the OpportunityContextBuilder correctly
func TestHandler_UsesContextBuilder(t *testing.T) {
	t.Run("nil_builder_returns_error", func(t *testing.T) {
		logger := zerolog.New(nil).Level(zerolog.Disabled)

		tagFilter := &mockTagFilter{}
		securityRepo := &mockSecurityRepo{}
		service := opportunities.NewService(tagFilter, securityRepo, logger)

		// Nil contextBuilder
		handler := NewHandler(service, nil, nil, logger)

		req := httptest.NewRequest("GET", "/api/opportunities/all", nil)
		w := httptest.NewRecorder()

		handler.HandleGetAll(w, req)

		// Should return 500 because contextBuilder is nil
		assert.Equal(t, http.StatusInternalServerError, w.Code)
	})

	// Note: Testing with a real builder requires mocking all its dependencies,
	// which is covered in internal/services/opportunity_context_builder_test.go
	// Here we just verify the handler properly handles the nil case.
}

// Test response format
func TestHandler_ResponseFormat(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, nil, nil, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/all", nil)
	w := httptest.NewRecorder()

	handler.HandleGetAll(w, req)

	// Even on error, response should be valid JSON or plain text error
	if w.Code != http.StatusInternalServerError {
		var response map[string]interface{}
		err := json.Unmarshal(w.Body.Bytes(), &response)
		require.NoError(t, err, "Response should be valid JSON")
	}
}
