package work

import (
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
)

// MockOptimizerService mocks the optimizer service for testing
type MockOptimizerService struct {
	mock.Mock
}

func (m *MockOptimizerService) CalculateWeights() (map[string]float64, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(map[string]float64), args.Error(1)
}

// MockOpportunityContextBuilder mocks the context builder for testing
type MockOpportunityContextBuilder struct {
	mock.Mock
}

func (m *MockOpportunityContextBuilder) Build() (interface{}, error) {
	args := m.Called()
	return args.Get(0), args.Error(1)
}

func (m *MockOpportunityContextBuilder) SetWeights(weights map[string]float64) {
	m.Called(weights)
}

// MockPlannerService mocks the planner service for testing
type MockPlannerService struct {
	mock.Mock
}

func (m *MockPlannerService) CreatePlan(ctx interface{}) (interface{}, error) {
	args := m.Called(ctx)
	return args.Get(0), args.Error(1)
}

// MockRecommendationRepo mocks the recommendation repository for testing
type MockRecommendationRepo struct {
	mock.Mock
}

func (m *MockRecommendationRepo) Store(recommendations interface{}) error {
	args := m.Called(recommendations)
	return args.Error(0)
}

// MockEventManager mocks the event manager for testing
type MockEventManager struct {
	mock.Mock
}

func (m *MockEventManager) Emit(event string, data interface{}) {
	m.Called(event, data)
}

// MockPlannerCache mocks cache operations for planner
type MockPlannerCache struct {
	mock.Mock
	data map[string]interface{}
}

func NewMockPlannerCache() *MockPlannerCache {
	return &MockPlannerCache{
		data: make(map[string]interface{}),
	}
}

func (m *MockPlannerCache) Has(key string) bool {
	_, exists := m.data[key]
	return exists
}

func (m *MockPlannerCache) Get(key string) interface{} {
	return m.data[key]
}

func (m *MockPlannerCache) Set(key string, value interface{}) {
	m.data[key] = value
}

func (m *MockPlannerCache) Delete(key string) {
	delete(m.data, key)
}

func (m *MockPlannerCache) DeletePrefix(prefix string) {
	for key := range m.data {
		if len(key) >= len(prefix) && key[:len(prefix)] == prefix {
			delete(m.data, key)
		}
	}
}

func TestRegisterPlannerWorkTypes(t *testing.T) {
	registry := NewRegistry()
	cache := NewMockPlannerCache()

	// Mock dependencies
	optimizerService := &MockOptimizerService{}
	contextBuilder := &MockOpportunityContextBuilder{}
	plannerService := &MockPlannerService{}
	recommendationRepo := &MockRecommendationRepo{}
	eventManager := &MockEventManager{}

	deps := &PlannerDeps{
		Cache:              cache,
		OptimizerService:   optimizerService,
		ContextBuilder:     contextBuilder,
		PlannerService:     plannerService,
		RecommendationRepo: recommendationRepo,
		EventManager:       eventManager,
	}

	RegisterPlannerWorkTypes(registry, deps)

	// Verify all 4 planner work types are registered
	assert.True(t, registry.Has("planner:weights"))
	assert.True(t, registry.Has("planner:context"))
	assert.True(t, registry.Has("planner:plan"))
	assert.True(t, registry.Has("planner:recommendations"))
}

func TestPlannerWorkTypes_Dependencies(t *testing.T) {
	registry := NewRegistry()
	cache := NewMockPlannerCache()
	deps := &PlannerDeps{
		Cache:              cache,
		OptimizerService:   &MockOptimizerService{},
		ContextBuilder:     &MockOpportunityContextBuilder{},
		PlannerService:     &MockPlannerService{},
		RecommendationRepo: &MockRecommendationRepo{},
		EventManager:       &MockEventManager{},
	}

	RegisterPlannerWorkTypes(registry, deps)

	// Check dependency chain
	contextWt := registry.Get("planner:context")
	require.NotNil(t, contextWt)
	assert.Contains(t, contextWt.DependsOn, "planner:weights")

	planWt := registry.Get("planner:plan")
	require.NotNil(t, planWt)
	assert.Contains(t, planWt.DependsOn, "planner:context")

	recommendationsWt := registry.Get("planner:recommendations")
	require.NotNil(t, recommendationsWt)
	assert.Contains(t, recommendationsWt.DependsOn, "planner:plan")
}

func TestPlannerWeights_Execute(t *testing.T) {
	registry := NewRegistry()
	cache := NewMockPlannerCache()

	optimizerService := &MockOptimizerService{}
	optimizerService.On("CalculateWeights").Return(map[string]float64{
		"AAPL":  0.25,
		"GOOGL": 0.25,
	}, nil)

	deps := &PlannerDeps{
		Cache:              cache,
		OptimizerService:   optimizerService,
		ContextBuilder:     &MockOpportunityContextBuilder{},
		PlannerService:     &MockPlannerService{},
		RecommendationRepo: &MockRecommendationRepo{},
		EventManager:       &MockEventManager{},
	}

	RegisterPlannerWorkTypes(registry, deps)

	wt := registry.Get("planner:weights")
	require.NotNil(t, wt)

	// Execute
	err := wt.Execute(context.Background(), "")
	require.NoError(t, err)

	// Verify optimizer was called
	optimizerService.AssertExpectations(t)

	// Verify weights were cached
	assert.True(t, cache.Has("optimizer_weights"))
}

func TestPlannerWeights_FindSubjects_NeedsWork(t *testing.T) {
	registry := NewRegistry()
	cache := NewMockPlannerCache()

	deps := &PlannerDeps{
		Cache:              cache,
		OptimizerService:   &MockOptimizerService{},
		ContextBuilder:     &MockOpportunityContextBuilder{},
		PlannerService:     &MockPlannerService{},
		RecommendationRepo: &MockRecommendationRepo{},
		EventManager:       &MockEventManager{},
	}

	RegisterPlannerWorkTypes(registry, deps)

	wt := registry.Get("planner:weights")
	require.NotNil(t, wt)

	// No cache = needs work
	subjects := wt.FindSubjects()
	assert.Equal(t, []string{""}, subjects)
}

func TestPlannerWeights_FindSubjects_Cached(t *testing.T) {
	registry := NewRegistry()
	cache := NewMockPlannerCache()
	cache.Set("optimizer_weights", map[string]float64{"AAPL": 0.5})

	deps := &PlannerDeps{
		Cache:              cache,
		OptimizerService:   &MockOptimizerService{},
		ContextBuilder:     &MockOpportunityContextBuilder{},
		PlannerService:     &MockPlannerService{},
		RecommendationRepo: &MockRecommendationRepo{},
		EventManager:       &MockEventManager{},
	}

	RegisterPlannerWorkTypes(registry, deps)

	wt := registry.Get("planner:weights")
	require.NotNil(t, wt)

	// Has cache = no work needed
	subjects := wt.FindSubjects()
	assert.Nil(t, subjects)
}

func TestPlannerContext_Execute(t *testing.T) {
	registry := NewRegistry()
	cache := NewMockPlannerCache()
	cache.Set("optimizer_weights", map[string]float64{"AAPL": 0.5})

	contextBuilder := &MockOpportunityContextBuilder{}
	contextBuilder.On("SetWeights", mock.Anything).Return()
	contextBuilder.On("Build").Return(map[string]interface{}{"test": true}, nil)

	deps := &PlannerDeps{
		Cache:              cache,
		OptimizerService:   &MockOptimizerService{},
		ContextBuilder:     contextBuilder,
		PlannerService:     &MockPlannerService{},
		RecommendationRepo: &MockRecommendationRepo{},
		EventManager:       &MockEventManager{},
	}

	RegisterPlannerWorkTypes(registry, deps)

	wt := registry.Get("planner:context")
	require.NotNil(t, wt)

	err := wt.Execute(context.Background(), "")
	require.NoError(t, err)

	contextBuilder.AssertExpectations(t)
	assert.True(t, cache.Has("opportunity_context"))
}

func TestPlannerPlan_Execute(t *testing.T) {
	registry := NewRegistry()
	cache := NewMockPlannerCache()
	cache.Set("opportunity_context", map[string]interface{}{"test": true})

	plannerService := &MockPlannerService{}
	plannerService.On("CreatePlan", mock.Anything).Return(
		[]map[string]interface{}{{"action": "buy"}}, nil,
	)

	deps := &PlannerDeps{
		Cache:              cache,
		OptimizerService:   &MockOptimizerService{},
		ContextBuilder:     &MockOpportunityContextBuilder{},
		PlannerService:     plannerService,
		RecommendationRepo: &MockRecommendationRepo{},
		EventManager:       &MockEventManager{},
	}

	RegisterPlannerWorkTypes(registry, deps)

	wt := registry.Get("planner:plan")
	require.NotNil(t, wt)

	err := wt.Execute(context.Background(), "")
	require.NoError(t, err)

	plannerService.AssertExpectations(t)
	assert.True(t, cache.Has("trade_plan"))
}

func TestPlannerRecommendations_Execute(t *testing.T) {
	registry := NewRegistry()
	cache := NewMockPlannerCache()
	plan := []map[string]interface{}{{"action": "buy"}}
	cache.Set("trade_plan", plan)

	recommendationRepo := &MockRecommendationRepo{}
	recommendationRepo.On("Store", mock.Anything).Return(nil)

	eventManager := &MockEventManager{}
	eventManager.On("Emit", "RecommendationsReady", mock.Anything).Return()

	deps := &PlannerDeps{
		Cache:              cache,
		OptimizerService:   &MockOptimizerService{},
		ContextBuilder:     &MockOpportunityContextBuilder{},
		PlannerService:     &MockPlannerService{},
		RecommendationRepo: recommendationRepo,
		EventManager:       eventManager,
	}

	RegisterPlannerWorkTypes(registry, deps)

	wt := registry.Get("planner:recommendations")
	require.NotNil(t, wt)

	err := wt.Execute(context.Background(), "")
	require.NoError(t, err)

	recommendationRepo.AssertExpectations(t)
	eventManager.AssertExpectations(t)
}

func TestPlannerWorkTypes_Priority(t *testing.T) {
	registry := NewRegistry()
	cache := NewMockPlannerCache()

	deps := &PlannerDeps{
		Cache:              cache,
		OptimizerService:   &MockOptimizerService{},
		ContextBuilder:     &MockOpportunityContextBuilder{},
		PlannerService:     &MockPlannerService{},
		RecommendationRepo: &MockRecommendationRepo{},
		EventManager:       &MockEventManager{},
	}

	RegisterPlannerWorkTypes(registry, deps)

	// All planner work should be critical priority
	for _, id := range []string{"planner:weights", "planner:context", "planner:plan", "planner:recommendations"} {
		wt := registry.Get(id)
		require.NotNil(t, wt)
		assert.Equal(t, PriorityCritical, wt.Priority, "work type %s should be critical priority", id)
	}
}

func TestPlannerWorkTypes_MarketTiming(t *testing.T) {
	registry := NewRegistry()
	cache := NewMockPlannerCache()

	deps := &PlannerDeps{
		Cache:              cache,
		OptimizerService:   &MockOptimizerService{},
		ContextBuilder:     &MockOpportunityContextBuilder{},
		PlannerService:     &MockPlannerService{},
		RecommendationRepo: &MockRecommendationRepo{},
		EventManager:       &MockEventManager{},
	}

	RegisterPlannerWorkTypes(registry, deps)

	// All planner work should be AnyTime (triggered by state changes, not market timing)
	for _, id := range []string{"planner:weights", "planner:context", "planner:plan", "planner:recommendations"} {
		wt := registry.Get(id)
		require.NotNil(t, wt)
		assert.Equal(t, AnyTime, wt.MarketTiming, "work type %s should be AnyTime", id)
	}
}
