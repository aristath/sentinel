package work

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewHandlers(t *testing.T) {
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{})
	processor := NewProcessor(registry, market, nil)

	handlers := NewHandlers(processor, registry)

	assert.NotNil(t, handlers)
	assert.Equal(t, processor, handlers.processor)
	assert.Equal(t, registry, handlers.registry)
}

func TestHandlers_ListWorkTypes(t *testing.T) {
	// Setup
	registry := NewRegistry()
	registry.Register(&WorkType{
		ID:           "test:work1",
		MarketTiming: AnyTime,
		DependsOn:    []string{"test:dep"},
		FindSubjects: func() []string { return nil },
		Execute:      func(ctx context.Context, subject string, progress *ProgressReporter) error { return nil },
	})
	registry.Register(&WorkType{
		ID:           "test:work2",
		MarketTiming: AfterMarketClose,
		FindSubjects: func() []string { return nil },
		Execute:      func(ctx context.Context, subject string, progress *ProgressReporter) error { return nil },
	})

	market := NewMarketTimingChecker(&MockMarketChecker{})
	processor := NewProcessor(registry, market, nil)
	handlers := NewHandlers(processor, registry)

	// Create request
	req := httptest.NewRequest(http.MethodGet, "/api/work/types", nil)
	rec := httptest.NewRecorder()

	// Execute
	handlers.ListWorkTypes(rec, req)

	// Verify
	assert.Equal(t, http.StatusOK, rec.Code)
	assert.Equal(t, "application/json", rec.Header().Get("Content-Type"))

	var response []map[string]any
	err := json.NewDecoder(rec.Body).Decode(&response)
	require.NoError(t, err)
	assert.Len(t, response, 2)

	// Check that work types are present (in priority order)
	ids := make([]string, len(response))
	for i, wt := range response {
		ids[i] = wt["id"].(string)
	}
	assert.Contains(t, ids, "test:work1")
	assert.Contains(t, ids, "test:work2")
}

func TestHandlers_ExecuteWorkType(t *testing.T) {
	// Setup
	executed := false
	registry := NewRegistry()
	registry.Register(&WorkType{
		ID:           "test:global",
		MarketTiming: AnyTime,
		FindSubjects: func() []string { return []string{""} },
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			executed = true
			return nil
		},
	})

	market := NewMarketTimingChecker(&MockMarketChecker{})
	processor := NewProcessorWithTimeout(registry, market, nil, 1*time.Second)
	handlers := NewHandlers(processor, registry)

	// Create router to extract URL params
	r := chi.NewRouter()
	r.Post("/api/work/{workType}/execute", handlers.ExecuteWorkType)

	// Create request
	req := httptest.NewRequest(http.MethodPost, "/api/work/test:global/execute", nil)
	rec := httptest.NewRecorder()

	// Execute
	r.ServeHTTP(rec, req)

	// Verify
	assert.Equal(t, http.StatusOK, rec.Code)
	assert.True(t, executed)

	var response map[string]string
	err := json.NewDecoder(rec.Body).Decode(&response)
	require.NoError(t, err)
	assert.Equal(t, "executed", response["status"])
	assert.Equal(t, "test:global", response["work_type"])
}

func TestHandlers_ExecuteWorkType_NotFound(t *testing.T) {
	// Setup
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{})
	processor := NewProcessor(registry, market, nil)
	handlers := NewHandlers(processor, registry)

	// Create router
	r := chi.NewRouter()
	r.Post("/api/work/{workType}/execute", handlers.ExecuteWorkType)

	// Create request for non-existent work type
	req := httptest.NewRequest(http.MethodPost, "/api/work/nonexistent:work/execute", nil)
	rec := httptest.NewRecorder()

	// Execute
	r.ServeHTTP(rec, req)

	// Verify - should return error
	assert.Equal(t, http.StatusBadRequest, rec.Code)
}

func TestHandlers_ExecuteWorkTypeWithSubject(t *testing.T) {
	// Setup
	executedSubject := ""
	registry := NewRegistry()
	registry.Register(&WorkType{
		ID:           "test:per-security",
		MarketTiming: AnyTime,
		FindSubjects: func() []string { return []string{"NL0010273215"} },
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			executedSubject = subject
			return nil
		},
	})

	market := NewMarketTimingChecker(&MockMarketChecker{})
	processor := NewProcessorWithTimeout(registry, market, nil, 1*time.Second)
	handlers := NewHandlers(processor, registry)

	// Create router
	r := chi.NewRouter()
	r.Post("/api/work/{workType}/{subject}/execute", handlers.ExecuteWorkTypeWithSubject)

	// Create request
	req := httptest.NewRequest(http.MethodPost, "/api/work/test:per-security/NL0010273215/execute", nil)
	rec := httptest.NewRecorder()

	// Execute
	r.ServeHTTP(rec, req)

	// Verify
	assert.Equal(t, http.StatusOK, rec.Code)
	assert.Equal(t, "NL0010273215", executedSubject)

	var response map[string]string
	err := json.NewDecoder(rec.Body).Decode(&response)
	require.NoError(t, err)
	assert.Equal(t, "executed", response["status"])
	assert.Equal(t, "test:per-security", response["work_type"])
	assert.Equal(t, "NL0010273215", response["subject"])
}

func TestHandlers_ExecuteWorkType_DependenciesNotMet(t *testing.T) {
	t.Skip("Requires cache to track dependencies - use integration tests for end-to-end testing")
}

func TestHandlers_TriggerProcessor(t *testing.T) {
	// Setup
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{})
	processor := NewProcessor(registry, market, nil)
	handlers := NewHandlers(processor, registry)

	// Create request
	req := httptest.NewRequest(http.MethodPost, "/api/work/trigger", nil)
	rec := httptest.NewRecorder()

	// Execute
	handlers.TriggerProcessor(rec, req)

	// Verify
	assert.Equal(t, http.StatusOK, rec.Code)

	var response map[string]string
	err := json.NewDecoder(rec.Body).Decode(&response)
	require.NoError(t, err)
	assert.Equal(t, "triggered", response["status"])
}

func TestHandlers_RegisterRoutes(t *testing.T) {
	// Setup
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{})
	processor := NewProcessor(registry, market, nil)
	handlers := NewHandlers(processor, registry)

	// Create router
	r := chi.NewRouter()
	handlers.RegisterRoutes(r)

	// Walk routes to verify they were registered
	routes := make(map[string]bool)
	chi.Walk(r, func(method, route string, handler http.Handler, middlewares ...func(http.Handler) http.Handler) error {
		routes[method+" "+route] = true
		return nil
	})

	// Verify routes exist
	assert.True(t, routes["GET /work/types"], "GET /work/types should be registered")
	assert.True(t, routes["POST /work/{workType}/execute"], "POST /work/{workType}/execute should be registered")
	assert.True(t, routes["POST /work/{workType}/{subject}/execute"], "POST /work/{workType}/{subject}/execute should be registered")
	assert.True(t, routes["POST /work/trigger"], "POST /work/trigger should be registered")
}
