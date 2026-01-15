package scheduler

import (
	"testing"

	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// MockRecommendationRepoForStoreTyped is a mock implementation of RecommendationRepositoryInterface with typed plan
type MockRecommendationRepoForStoreTyped struct {
	StorePlanFunc                  func(plan *planningdomain.HolisticPlan, portfolioHash string) error
	StoreRejectedOpportunitiesFunc func(rejected []planningdomain.RejectedOpportunity, portfolioHash string) error
	StorePreFilteredSecuritiesFunc func(preFiltered []planningdomain.PreFilteredSecurity, portfolioHash string) error
	StoreRejectedSequencesFunc     func(rejected []planningdomain.RejectedSequence, portfolioHash string) error
}

func (m *MockRecommendationRepoForStoreTyped) StorePlan(plan *planningdomain.HolisticPlan, portfolioHash string) error {
	if m.StorePlanFunc != nil {
		return m.StorePlanFunc(plan, portfolioHash)
	}
	return nil
}

func (m *MockRecommendationRepoForStoreTyped) StoreRejectedOpportunities(rejected []planningdomain.RejectedOpportunity, portfolioHash string) error {
	if m.StoreRejectedOpportunitiesFunc != nil {
		return m.StoreRejectedOpportunitiesFunc(rejected, portfolioHash)
	}
	return nil
}

func (m *MockRecommendationRepoForStoreTyped) StorePreFilteredSecurities(preFiltered []planningdomain.PreFilteredSecurity, portfolioHash string) error {
	if m.StorePreFilteredSecuritiesFunc != nil {
		return m.StorePreFilteredSecuritiesFunc(preFiltered, portfolioHash)
	}
	return nil
}

func (m *MockRecommendationRepoForStoreTyped) StoreRejectedSequences(rejected []planningdomain.RejectedSequence, portfolioHash string) error {
	if m.StoreRejectedSequencesFunc != nil {
		return m.StoreRejectedSequencesFunc(rejected, portfolioHash)
	}
	return nil
}

func TestStoreRecommendationsJob_SetPlan_Typed(t *testing.T) {
	job := NewStoreRecommendationsJob(nil, nil, "")

	plan := &planningdomain.HolisticPlan{
		Steps:         []planningdomain.HolisticStep{},
		CurrentScore:  75.0,
		EndStateScore: 85.0,
		Improvement:   10.0,
		Feasible:      true,
	}

	job.SetPlan(plan)

	retrievedPlan := job.GetPlan()
	require.NotNil(t, retrievedPlan)
	assert.Equal(t, plan, retrievedPlan)
}

func TestStoreRecommendationsJob_Run_Typed_Success(t *testing.T) {
	storeCalled := false
	var storedPlan *planningdomain.HolisticPlan
	var storedHash string

	mockRepo := &MockRecommendationRepoForStoreTyped{
		StorePlanFunc: func(plan *planningdomain.HolisticPlan, portfolioHash string) error {
			storeCalled = true
			storedPlan = plan
			storedHash = portfolioHash
			return nil
		},
	}

	plan := &planningdomain.HolisticPlan{
		Steps: []planningdomain.HolisticStep{
			{
				Symbol:         "AAPL",
				Side:           "BUY",
				Quantity:       10.0,
				EstimatedPrice: 150.0,
				Reason:         "Opportunity buy",
			},
		},
		CurrentScore:  75.0,
		EndStateScore: 85.0,
		Improvement:   10.0,
		Feasible:      true,
	}
	portfolioHash := "test-hash-123"

	job := NewStoreRecommendationsJob(nil, nil, portfolioHash)
	job.SetPlan(plan)

	// Update the repository interface to use typed plan
	// For now, we'll test with the interface conversion
	job.recommendationRepo = mockRepo

	err := job.Run()
	require.NoError(t, err)
	assert.True(t, storeCalled, "StorePlan should have been called")
	assert.Equal(t, plan, storedPlan)
	assert.Equal(t, portfolioHash, storedHash)
}

func TestStoreRecommendationsJob_Run_Typed_NilPlan(t *testing.T) {
	mockRepo := &MockRecommendationRepoForStoreTyped{}

	job := NewStoreRecommendationsJob(nil, nil, "test-hash")
	job.recommendationRepo = mockRepo
	// Don't set plan

	err := job.Run()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "plan not set")
}

func TestStoreRecommendationsJob_Run_Typed_RepositoryError(t *testing.T) {
	mockRepo := &MockRecommendationRepoForStoreTyped{
		StorePlanFunc: func(plan *planningdomain.HolisticPlan, portfolioHash string) error {
			return assert.AnError
		},
	}

	plan := &planningdomain.HolisticPlan{
		Steps:    []planningdomain.HolisticStep{},
		Feasible: true,
	}

	job := NewStoreRecommendationsJob(nil, nil, "test-hash")
	job.SetPlan(plan)
	job.recommendationRepo = mockRepo

	err := job.Run()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "failed to store plan")
}

func TestStoreRecommendationsJob_GetPlan_Typed(t *testing.T) {
	job := NewStoreRecommendationsJob(nil, nil, "")

	assert.Nil(t, job.GetPlan(), "Initial plan should be nil")

	plan := &planningdomain.HolisticPlan{
		Steps: []planningdomain.HolisticStep{
			{
				Symbol:         "MSFT",
				Side:           "SELL",
				Quantity:       5.0,
				EstimatedPrice: 300.0,
				Reason:         "Profit taking",
			},
		},
		CurrentScore:  80.0,
		EndStateScore: 90.0,
		Improvement:   10.0,
		Feasible:      true,
	}

	job.SetPlan(plan)

	retrievedPlan := job.GetPlan()
	require.NotNil(t, retrievedPlan)
	assert.Equal(t, plan.Steps, retrievedPlan.Steps)
	assert.Equal(t, plan.CurrentScore, retrievedPlan.CurrentScore)
	assert.Equal(t, plan.EndStateScore, retrievedPlan.EndStateScore)
	assert.Equal(t, plan.Improvement, retrievedPlan.Improvement)
	assert.Equal(t, plan.Feasible, retrievedPlan.Feasible)
}
