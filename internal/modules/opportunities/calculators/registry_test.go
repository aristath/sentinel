package calculators

import (
	"testing"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// mockCalculator implements OpportunityCalculator for testing
type mockCalculator struct {
	name      string
	category  domain.OpportunityCategory
	result    domain.CalculatorResult
	calcError error
}

func (m *mockCalculator) Name() string {
	return m.name
}

func (m *mockCalculator) Category() domain.OpportunityCategory {
	return m.category
}

func (m *mockCalculator) Calculate(ctx *domain.OpportunityContext, params map[string]interface{}) (domain.CalculatorResult, error) {
	if m.calcError != nil {
		return domain.CalculatorResult{}, m.calcError
	}
	return m.result, nil
}

func TestCalculatorRegistry_NewCalculatorRegistry(t *testing.T) {
	log := zerolog.Nop()
	registry := NewCalculatorRegistry(log)

	assert.NotNil(t, registry)
	assert.NotNil(t, registry.calculators)
	assert.Empty(t, registry.calculators)
}

func TestCalculatorRegistry_Register(t *testing.T) {
	log := zerolog.Nop()
	registry := NewCalculatorRegistry(log)

	calc := &mockCalculator{
		name:     "test_calc",
		category: domain.OpportunityCategoryProfitTaking,
	}

	registry.Register(calc)

	registered, err := registry.Get("test_calc")
	require.NoError(t, err)
	assert.Equal(t, "test_calc", registered.Name())
}

func TestCalculatorRegistry_GetNotFound(t *testing.T) {
	log := zerolog.Nop()
	registry := NewCalculatorRegistry(log)

	_, err := registry.Get("nonexistent")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "calculator not found")
}

func TestCalculatorRegistry_List(t *testing.T) {
	log := zerolog.Nop()
	registry := NewCalculatorRegistry(log)

	calc1 := &mockCalculator{name: "calc1", category: domain.OpportunityCategoryProfitTaking}
	calc2 := &mockCalculator{name: "calc2", category: domain.OpportunityCategoryAveragingDown}

	registry.Register(calc1)
	registry.Register(calc2)

	list := registry.List()
	assert.Len(t, list, 2)
}

func TestCalculatorRegistry_IdentifyOpportunitiesWithProgress(t *testing.T) {
	log := zerolog.Nop()
	registry := NewCalculatorRegistry(log)

	// Register 3 calculators with mock results
	calc1 := &mockCalculator{
		name:     "profit_taking",
		category: domain.OpportunityCategoryProfitTaking,
		result: domain.CalculatorResult{
			Candidates: []domain.ActionCandidate{
				{Symbol: "AAPL", Side: "SELL", Priority: 0.8},
			},
			PreFiltered: []domain.PreFilteredSecurity{},
		},
	}
	calc2 := &mockCalculator{
		name:     "opportunity_buys",
		category: domain.OpportunityCategoryOpportunityBuys,
		result: domain.CalculatorResult{
			Candidates: []domain.ActionCandidate{
				{Symbol: "MSFT", Side: "BUY", Priority: 0.7},
				{Symbol: "GOOGL", Side: "BUY", Priority: 0.6},
			},
			PreFiltered: []domain.PreFilteredSecurity{
				{Symbol: "TSLA", Calculator: "opportunity_buys"},
			},
		},
	}
	calc3 := &mockCalculator{
		name:     "averaging_down",
		category: domain.OpportunityCategoryAveragingDown,
		result: domain.CalculatorResult{
			Candidates: []domain.ActionCandidate{
				{Symbol: "NVDA", Side: "BUY", Priority: 0.9},
			},
			PreFiltered: []domain.PreFilteredSecurity{},
		},
	}

	registry.Register(calc1)
	registry.Register(calc2)
	registry.Register(calc3)

	// Create config enabling all three calculators
	config := &domain.PlannerConfiguration{
		EnableProfitTakingCalc:    true,
		EnableOpportunityBuysCalc: true,
		EnableAveragingDownCalc:   true,
	}

	// Track progress callbacks
	var progressCalls []ProgressUpdate

	callback := func(update ProgressUpdate) {
		progressCalls = append(progressCalls, update)
	}

	ctx := &domain.OpportunityContext{}
	result, err := registry.IdentifyOpportunitiesWithProgress(ctx, config, callback)

	require.NoError(t, err)
	require.NotNil(t, result)

	// Verify we got progress updates for each calculator
	assert.GreaterOrEqual(t, len(progressCalls), 3, "Should have at least 3 progress updates")

	// Verify total candidates and pre-filtered counts
	totalCandidates := 0
	totalPreFiltered := 0
	for _, r := range result {
		totalCandidates += len(r.Candidates)
		totalPreFiltered += len(r.PreFiltered)
	}
	assert.Equal(t, 4, totalCandidates, "Should have 4 total candidates")
	assert.Equal(t, 1, totalPreFiltered, "Should have 1 pre-filtered security")

	// Verify progress update structure
	for _, call := range progressCalls {
		assert.NotEmpty(t, call.Phase, "Phase should be set")
		assert.NotEmpty(t, call.SubPhase, "SubPhase (calculator name) should be set")
		assert.LessOrEqual(t, call.Current, call.Total, "Current should not exceed total")
		assert.NotNil(t, call.Details, "Details should not be nil")
	}
}

func TestCalculatorRegistry_IdentifyOpportunitiesWithProgress_NilCallback(t *testing.T) {
	log := zerolog.Nop()
	registry := NewCalculatorRegistry(log)

	calc := &mockCalculator{
		name:     "profit_taking",
		category: domain.OpportunityCategoryProfitTaking,
		result: domain.CalculatorResult{
			Candidates: []domain.ActionCandidate{
				{Symbol: "AAPL", Side: "SELL"},
			},
		},
	}
	registry.Register(calc)

	config := &domain.PlannerConfiguration{
		EnableProfitTakingCalc: true,
	}

	// Should not panic with nil callback
	result, err := registry.IdentifyOpportunitiesWithProgress(&domain.OpportunityContext{}, config, nil)

	require.NoError(t, err)
	assert.Len(t, result[domain.OpportunityCategoryProfitTaking].Candidates, 1)
}

func TestCalculatorRegistry_IdentifyOpportunitiesWithProgress_EmptyEnabled(t *testing.T) {
	log := zerolog.Nop()
	registry := NewCalculatorRegistry(log)

	calc := &mockCalculator{
		name:     "profit_taking",
		category: domain.OpportunityCategoryProfitTaking,
	}
	registry.Register(calc)

	// All calculators disabled
	config := &domain.PlannerConfiguration{
		EnableProfitTakingCalc:    false,
		EnableAveragingDownCalc:   false,
		EnableOpportunityBuysCalc: false,
		EnableRebalanceSellsCalc:  false,
		EnableRebalanceBuysCalc:   false,
		EnableWeightBasedCalc:     false,
	}

	var progressCalls []ProgressUpdate
	callback := func(update ProgressUpdate) {
		progressCalls = append(progressCalls, update)
	}

	result, err := registry.IdentifyOpportunitiesWithProgress(&domain.OpportunityContext{}, config, callback)

	require.NoError(t, err)
	assert.Empty(t, result)
	assert.Empty(t, progressCalls, "No progress calls expected when no calculators enabled")
}

func TestCalculatorRegistry_IdentifyOpportunitiesWithProgress_DetailsContent(t *testing.T) {
	log := zerolog.Nop()
	registry := NewCalculatorRegistry(log)

	calc := &mockCalculator{
		name:     "profit_taking",
		category: domain.OpportunityCategoryProfitTaking,
		result: domain.CalculatorResult{
			Candidates: []domain.ActionCandidate{
				{Symbol: "AAPL", Side: "SELL"},
				{Symbol: "MSFT", Side: "SELL"},
			},
			PreFiltered: []domain.PreFilteredSecurity{
				{Symbol: "TSLA"},
			},
		},
	}
	registry.Register(calc)

	config := &domain.PlannerConfiguration{
		EnableProfitTakingCalc: true,
	}

	var progressCalls []ProgressUpdate
	callback := func(update ProgressUpdate) {
		progressCalls = append(progressCalls, update)
	}

	_, err := registry.IdentifyOpportunitiesWithProgress(&domain.OpportunityContext{}, config, callback)
	require.NoError(t, err)

	// Find the final progress update (after calculation)
	require.NotEmpty(t, progressCalls)
	lastCall := progressCalls[len(progressCalls)-1]

	// Verify details contain expected keys
	assert.Contains(t, lastCall.Details, "calculators_total")
	assert.Contains(t, lastCall.Details, "calculators_done")
	assert.Contains(t, lastCall.Details, "candidates_so_far")
	assert.Contains(t, lastCall.Details, "filtered_so_far")

	// Verify values
	assert.Equal(t, 1, lastCall.Details["calculators_done"])
	assert.Equal(t, 2, lastCall.Details["candidates_so_far"])
	assert.Equal(t, 1, lastCall.Details["filtered_so_far"])
}

func TestProgressUpdate_Structure(t *testing.T) {
	update := ProgressUpdate{
		Phase:    "opportunity_identification",
		SubPhase: "profit_taking",
		Current:  1,
		Total:    6,
		Message:  "Running profit_taking calculator",
		Details: map[string]any{
			"calculators_total":  6,
			"calculators_done":   0,
			"candidates_so_far":  0,
			"filtered_so_far":    0,
			"current_calculator": "profit_taking",
		},
	}

	assert.Equal(t, "opportunity_identification", update.Phase)
	assert.Equal(t, "profit_taking", update.SubPhase)
	assert.Equal(t, 1, update.Current)
	assert.Equal(t, 6, update.Total)
	assert.NotEmpty(t, update.Message)
	assert.NotNil(t, update.Details)
}
