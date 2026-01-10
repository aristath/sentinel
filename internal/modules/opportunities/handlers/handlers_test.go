package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/opportunities"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	_ "modernc.org/sqlite"
)

// setupTestDB creates an in-memory SQLite database with minimal schema
func setupTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)

	// Minimal schema for testing (opportunities don't require much DB access)
	_, err = db.Exec(`CREATE TABLE IF NOT EXISTS securities (isin TEXT PRIMARY KEY)`)
	require.NoError(t, err)

	return db
}

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

func (m *mockSecurityRepo) GetAllActive() ([]domain.Security, error) {
	return []domain.Security{}, nil
}

func (m *mockSecurityRepo) GetByTags(tags []string) ([]domain.Security, error) {
	return []domain.Security{}, nil
}

func (m *mockSecurityRepo) GetPositionsByTags(positionSymbols []string, tags []string) ([]domain.Security, error) {
	return []domain.Security{}, nil
}

func (m *mockSecurityRepo) GetTagsForSecurity(symbol string) ([]string, error) {
	return []string{}, nil
}

func TestHandleGetAll(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/all", nil)
	w := httptest.NewRecorder()

	handler.HandleGetAll(w, req)

	assert.Equal(t, http.StatusNotImplemented, w.Code)
	assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	assert.Contains(t, response, "error")
	errorData := response["error"].(map[string]interface{})
	assert.Equal(t, "NOT_IMPLEMENTED", errorData["code"])
}

func TestHandleGetProfitTaking(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/profit-taking", nil)
	w := httptest.NewRecorder()

	handler.HandleGetProfitTaking(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "opportunities")
	assert.Contains(t, data, "category")
	assert.Equal(t, "profit_taking", data["category"])
}

func TestHandleGetAveragingDown(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/averaging-down", nil)
	w := httptest.NewRecorder()

	handler.HandleGetAveragingDown(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "opportunities")
	assert.Equal(t, "averaging_down", data["category"])
}

func TestHandleGetOpportunityBuys(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/opportunity-buys", nil)
	w := httptest.NewRecorder()

	handler.HandleGetOpportunityBuys(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "opportunities")
	assert.Equal(t, "opportunity_buys", data["category"])
}

func TestHandleGetRebalanceBuys(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/rebalance-buys", nil)
	w := httptest.NewRecorder()

	handler.HandleGetRebalanceBuys(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "opportunities")
	assert.Equal(t, "rebalance_buys", data["category"])
}

func TestHandleGetRebalanceSells(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/rebalance-sells", nil)
	w := httptest.NewRecorder()

	handler.HandleGetRebalanceSells(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "opportunities")
	assert.Equal(t, "rebalance_sells", data["category"])
}

func TestHandleGetWeightBased(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/weight-based", nil)
	w := httptest.NewRecorder()

	handler.HandleGetWeightBased(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "opportunities")
	assert.Equal(t, "weight_based", data["category"])
}

func TestHandleGetRegistry(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, logger)

	req := httptest.NewRequest("GET", "/api/opportunities/registry", nil)
	w := httptest.NewRecorder()

	handler.HandleGetRegistry(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err := json.NewDecoder(w.Body).Decode(&response)
	require.NoError(t, err)

	data := response["data"].(map[string]interface{})
	assert.Contains(t, data, "calculators")
	assert.Contains(t, data, "count")

	calculators := data["calculators"].([]interface{})
	assert.Greater(t, len(calculators), 0) // Should have registered calculators
}

func TestRouteIntegration(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	tagFilter := &mockTagFilter{}
	securityRepo := &mockSecurityRepo{}
	service := opportunities.NewService(tagFilter, securityRepo, logger)

	handler := NewHandler(service, logger)

	router := chi.NewRouter()
	handler.RegisterRoutes(router)

	tests := []struct {
		name           string
		method         string
		path           string
		expectedStatus int
	}{
		{"get all opportunities", "GET", "/opportunities/all", http.StatusOK},
		{"get profit taking", "GET", "/opportunities/profit-taking", http.StatusOK},
		{"get averaging down", "GET", "/opportunities/averaging-down", http.StatusOK},
		{"get opportunity buys", "GET", "/opportunities/opportunity-buys", http.StatusOK},
		{"get rebalance buys", "GET", "/opportunities/rebalance-buys", http.StatusOK},
		{"get rebalance sells", "GET", "/opportunities/rebalance-sells", http.StatusOK},
		{"get weight based", "GET", "/opportunities/weight-based", http.StatusOK},
		{"get registry", "GET", "/opportunities/registry", http.StatusOK},
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
