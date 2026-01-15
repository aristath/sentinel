package scheduler

import (
	"testing"

	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// MockRecommendationRepoForStore is a mock implementation of RecommendationRepositoryInterface
type MockRecommendationRepoForStore struct {
	StorePlanFunc                  func(plan *planningdomain.HolisticPlan, portfolioHash string) error
	StoreRejectedOpportunitiesFunc func(rejected []planningdomain.RejectedOpportunity, portfolioHash string) error
	StorePreFilteredSecuritiesFunc func(preFiltered []planningdomain.PreFilteredSecurity, portfolioHash string) error
	StoreRejectedSequencesFunc     func(rejected []planningdomain.RejectedSequence, portfolioHash string) error
}

func (m *MockRecommendationRepoForStore) StorePlan(plan *planningdomain.HolisticPlan, portfolioHash string) error {
	if m.StorePlanFunc != nil {
		return m.StorePlanFunc(plan, portfolioHash)
	}
	return nil
}

func (m *MockRecommendationRepoForStore) StoreRejectedOpportunities(rejected []planningdomain.RejectedOpportunity, portfolioHash string) error {
	if m.StoreRejectedOpportunitiesFunc != nil {
		return m.StoreRejectedOpportunitiesFunc(rejected, portfolioHash)
	}
	return nil
}

func (m *MockRecommendationRepoForStore) StorePreFilteredSecurities(preFiltered []planningdomain.PreFilteredSecurity, portfolioHash string) error {
	if m.StorePreFilteredSecuritiesFunc != nil {
		return m.StorePreFilteredSecuritiesFunc(preFiltered, portfolioHash)
	}
	return nil
}

func (m *MockRecommendationRepoForStore) StoreRejectedSequences(rejected []planningdomain.RejectedSequence, portfolioHash string) error {
	if m.StoreRejectedSequencesFunc != nil {
		return m.StoreRejectedSequencesFunc(rejected, portfolioHash)
	}
	return nil
}

func TestStoreRecommendationsJob_Name(t *testing.T) {
	job := NewStoreRecommendationsJob(nil, nil, "")
	assert.Equal(t, "store_recommendations", job.Name())
}

func TestStoreRecommendationsJob_Run_Success(t *testing.T) {
	storeCalled := false
	var storedPlan *planningdomain.HolisticPlan
	var storedHash string

	mockRepo := &MockRecommendationRepoForStore{
		StorePlanFunc: func(plan *planningdomain.HolisticPlan, portfolioHash string) error {
			storeCalled = true
			storedPlan = plan
			storedHash = portfolioHash
			return nil
		},
	}

	plan := &planningdomain.HolisticPlan{
		Steps:    []planningdomain.HolisticStep{},
		Feasible: true,
	}
	portfolioHash := "test-hash-123"

	job := NewStoreRecommendationsJob(mockRepo, nil, portfolioHash)
	job.SetPlan(plan)

	err := job.Run()
	require.NoError(t, err)
	assert.True(t, storeCalled, "StorePlan should have been called")
	assert.Equal(t, plan, storedPlan)
	assert.Equal(t, portfolioHash, storedHash)
}

func TestStoreRecommendationsJob_Run_NoRepository(t *testing.T) {
	job := NewStoreRecommendationsJob(nil, nil, "test-hash")
	job.SetPlan(&planningdomain.HolisticPlan{
		Steps:    []planningdomain.HolisticStep{},
		Feasible: true,
	})

	err := job.Run()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "recommendation repository not available")
}

func TestStoreRecommendationsJob_Run_NoPlan(t *testing.T) {
	mockRepo := &MockRecommendationRepoForStore{}

	job := NewStoreRecommendationsJob(mockRepo, nil, "test-hash")
	// Don't set plan

	err := job.Run()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "plan not set")
}

func TestStoreRecommendationsJob_Run_RepositoryError(t *testing.T) {
	mockRepo := &MockRecommendationRepoForStore{
		StorePlanFunc: func(plan *planningdomain.HolisticPlan, portfolioHash string) error {
			return assert.AnError
		},
	}

	job := NewStoreRecommendationsJob(mockRepo, nil, "test-hash")
	job.SetPlan(&planningdomain.HolisticPlan{
		Steps:    []planningdomain.HolisticStep{},
		Feasible: true,
	})

	err := job.Run()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "failed to store plan")
}
