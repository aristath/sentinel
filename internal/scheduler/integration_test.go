package scheduler

import (
	"testing"

	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Note: Comprehensive EUR conversion and context building tests have been moved to
// internal/services/opportunity_context_builder_test.go
//
// This file only tests scheduler-specific integration patterns.

// TestBuildOpportunityContextJob_Integration_WeightsApplication tests that
// optimizer weights are correctly applied to the context
func TestBuildOpportunityContextJob_Integration_WeightsApplication(t *testing.T) {
	// Create a job
	job := &BuildOpportunityContextJob{}

	// Set optimizer target weights
	weights := map[string]float64{
		"US0378331005": 0.25, // AAPL
		"US5949181045": 0.35, // MSFT
		"GB0031348658": 0.40, // BARC
	}
	job.SetOptimizerTargetWeights(weights)

	// Simulate a successful build by setting the context
	job.opportunityContext = &planningdomain.OpportunityContext{
		EnrichedPositions:      []planningdomain.EnrichedPosition{},
		AvailableCashEUR:       10000.0,
		TotalPortfolioValueEUR: 50000.0,
		TargetWeights:          map[string]float64{}, // Will be overwritten
	}

	// Apply optimizer weights (as Run() does)
	if len(job.optimizerTargetWeights) > 0 {
		job.opportunityContext.TargetWeights = job.optimizerTargetWeights
	}

	// Verify
	ctx := job.GetOpportunityContext()
	require.NotNil(t, ctx)
	assert.Equal(t, weights, ctx.TargetWeights, "Optimizer weights should be applied to context")
	assert.Equal(t, 0.25, ctx.TargetWeights["US0378331005"])
	assert.Equal(t, 0.35, ctx.TargetWeights["US5949181045"])
	assert.Equal(t, 0.40, ctx.TargetWeights["GB0031348658"])
}

// TestBuildOpportunityContextJob_Integration_JobFlow tests the overall job execution flow
func TestBuildOpportunityContextJob_Integration_JobFlow(t *testing.T) {
	t.Run("job_name_is_consistent", func(t *testing.T) {
		job := NewBuildOpportunityContextJob(nil)
		assert.Equal(t, "build_opportunity_context", job.Name())
	})

	t.Run("initial_state_is_clean", func(t *testing.T) {
		job := NewBuildOpportunityContextJob(nil)
		assert.Nil(t, job.GetOpportunityContext())
		assert.Nil(t, job.optimizerTargetWeights)
	})

	t.Run("weights_can_be_set_before_run", func(t *testing.T) {
		job := NewBuildOpportunityContextJob(nil)

		weights := map[string]float64{"TEST": 1.0}
		job.SetOptimizerTargetWeights(weights)

		assert.Equal(t, weights, job.optimizerTargetWeights)
	})

	t.Run("nil_builder_returns_error", func(t *testing.T) {
		job := NewBuildOpportunityContextJob(nil)
		err := job.Run()

		require.Error(t, err)
		assert.Contains(t, err.Error(), "context builder is nil")
	})
}

// TestBuildOpportunityContextJob_Integration_ContextRetrieval tests context retrieval patterns
func TestBuildOpportunityContextJob_Integration_ContextRetrieval(t *testing.T) {
	t.Run("get_context_returns_nil_before_run", func(t *testing.T) {
		job := NewBuildOpportunityContextJob(nil)
		assert.Nil(t, job.GetOpportunityContext())
	})

	t.Run("get_context_returns_context_after_successful_build", func(t *testing.T) {
		job := &BuildOpportunityContextJob{}

		// Simulate successful build
		job.opportunityContext = &planningdomain.OpportunityContext{
			EnrichedPositions: []planningdomain.EnrichedPosition{
				{ISIN: "US0378331005", Symbol: "AAPL", Quantity: 100},
				{ISIN: "US5949181045", Symbol: "MSFT", Quantity: 50},
			},
			AvailableCashEUR:       5000.0,
			TotalPortfolioValueEUR: 25000.0,
			RecentlySoldISINs:      map[string]bool{"SOLD123": true},
			RecentlyBoughtISINs:    map[string]bool{"BOUGHT456": true},
		}

		ctx := job.GetOpportunityContext()
		require.NotNil(t, ctx)
		assert.Len(t, ctx.EnrichedPositions, 2)
		assert.Equal(t, 5000.0, ctx.AvailableCashEUR)
		assert.True(t, ctx.RecentlySoldISINs["SOLD123"])
		assert.True(t, ctx.RecentlyBoughtISINs["BOUGHT456"])
	})
}

// TestBuildOpportunityContextJob_Integration_PlannerContextPassing demonstrates how
// BuildOpportunityContextJob provides context for the planner workflow.
// NOTE: The Work Processor now handles orchestration (formerly PlannerBatchJob).
func TestBuildOpportunityContextJob_Integration_PlannerContextPassing(t *testing.T) {
	// This test demonstrates the expected data flow:
	// 1. BuildOpportunityContextJob.Run() builds context
	// 2. GetOpportunityContext() retrieves it
	// 3. Work Processor's planner work types use it for planning

	t.Run("context_flows_to_planner", func(t *testing.T) {
		// Setup build job
		buildJob := &BuildOpportunityContextJob{}

		// Simulate successful build
		buildJob.opportunityContext = &planningdomain.OpportunityContext{
			EnrichedPositions: []planningdomain.EnrichedPosition{
				{ISIN: "US0378331005", Symbol: "AAPL", CurrentPrice: 150.0, Quantity: 100},
			},
			AvailableCashEUR:       10000.0,
			TotalPortfolioValueEUR: 25000.0,
			RecentlySoldISINs:      map[string]bool{},
			RecentlyBoughtISINs:    map[string]bool{},
		}

		// Retrieve context (as Work Processor's planner work types would)
		ctx := buildJob.GetOpportunityContext()

		// Verify context is available for planning
		require.NotNil(t, ctx)
		assert.Greater(t, len(ctx.EnrichedPositions), 0)
		assert.Greater(t, ctx.AvailableCashEUR, 0.0)
		assert.Greater(t, ctx.TotalPortfolioValueEUR, 0.0)
	})

	t.Run("optimizer_weights_integrated", func(t *testing.T) {
		// Setup with optimizer weights
		buildJob := &BuildOpportunityContextJob{}

		// Set optimizer weights (from GetOptimizerWeightsJob)
		optimizerWeights := map[string]float64{
			"US0378331005": 0.6,
			"US5949181045": 0.4,
		}
		buildJob.SetOptimizerTargetWeights(optimizerWeights)

		// Simulate build with context
		buildJob.opportunityContext = &planningdomain.OpportunityContext{
			EnrichedPositions:      []planningdomain.EnrichedPosition{},
			AvailableCashEUR:       10000.0,
			TotalPortfolioValueEUR: 50000.0,
			TargetWeights:          map[string]float64{},
		}

		// Apply weights (as Run() does)
		buildJob.opportunityContext.TargetWeights = buildJob.optimizerTargetWeights

		// Verify weights are in context
		ctx := buildJob.GetOpportunityContext()
		require.NotNil(t, ctx)
		assert.Equal(t, 0.6, ctx.TargetWeights["US0378331005"])
		assert.Equal(t, 0.4, ctx.TargetWeights["US5949181045"])
	})
}

// TestBuildOpportunityContextJob_Integration_CooloffData tests cooloff data is preserved in context
func TestBuildOpportunityContextJob_Integration_CooloffData(t *testing.T) {
	job := &BuildOpportunityContextJob{}

	// Simulate build with cooloff data (as OpportunityContextBuilder would produce)
	job.opportunityContext = &planningdomain.OpportunityContext{
		EnrichedPositions:      []planningdomain.EnrichedPosition{},
		AvailableCashEUR:       10000.0,
		TotalPortfolioValueEUR: 50000.0,
		RecentlySoldISINs: map[string]bool{
			"US0378331005": true, // AAPL sold recently
			"GB0031348658": true, // BARC sold recently
		},
		RecentlyBoughtISINs: map[string]bool{
			"US5949181045": true, // MSFT bought recently
		},
		IneligibleISINs: map[string]bool{
			"INACTIVE123": true, // Inactive security
		},
	}

	ctx := job.GetOpportunityContext()
	require.NotNil(t, ctx)

	// Verify cooloff maps are populated
	assert.True(t, ctx.RecentlySoldISINs["US0378331005"], "AAPL should be in cooloff")
	assert.True(t, ctx.RecentlySoldISINs["GB0031348658"], "BARC should be in cooloff")
	assert.True(t, ctx.RecentlyBoughtISINs["US5949181045"], "MSFT should be in buy cooloff")
	assert.True(t, ctx.IneligibleISINs["INACTIVE123"], "Inactive should be ineligible")

	// Verify not in maps
	assert.False(t, ctx.RecentlySoldISINs["NOTINCOOLOFF"])
	assert.False(t, ctx.RecentlyBoughtISINs["NOTINCOOLOFF"])
}
