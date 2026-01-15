package sequences

import (
	"testing"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/planning/progress"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestExhaustiveGenerator_GenerateWithDetailedProgress(t *testing.T) {
	log := zerolog.Nop()
	generator := NewExhaustiveGenerator(log, nil)

	opportunities := domain.OpportunitiesByCategory{
		domain.OpportunityCategoryProfitTaking: []domain.ActionCandidate{
			{ISIN: "US1", Symbol: "AAPL", Side: "SELL", Quantity: 5, ValueEUR: 500, Priority: 0.8},
			{ISIN: "US2", Symbol: "MSFT", Side: "SELL", Quantity: 3, ValueEUR: 300, Priority: 0.7},
		},
		domain.OpportunityCategoryOpportunityBuys: []domain.ActionCandidate{
			{ISIN: "US3", Symbol: "GOOGL", Side: "BUY", Quantity: 2, ValueEUR: 400, Priority: 0.6},
		},
	}

	ctx := &domain.OpportunityContext{}

	var progressUpdates []progress.Update

	config := GenerationConfig{
		MaxDepth:        3,
		AvailableCash:   1000,
		PruneInfeasible: false,
		DetailedProgressCallback: func(update progress.Update) {
			progressUpdates = append(progressUpdates, update)
		},
	}

	sequences := generator.Generate(opportunities, ctx, config)

	// Should generate sequences
	require.NotEmpty(t, sequences)

	// Should have received progress updates
	require.NotEmpty(t, progressUpdates, "Should receive progress updates")

	// Verify progress update structure
	for _, update := range progressUpdates {
		assert.Equal(t, "sequence_generation", update.Phase)
		assert.NotEmpty(t, update.SubPhase, "SubPhase should be set")
		assert.LessOrEqual(t, update.Current, update.Total)
		assert.NotNil(t, update.Details)
	}
}

func TestExhaustiveGenerator_ProgressReportsEachDepth(t *testing.T) {
	log := zerolog.Nop()
	generator := NewExhaustiveGenerator(log, nil)

	opportunities := domain.OpportunitiesByCategory{
		domain.OpportunityCategoryProfitTaking: []domain.ActionCandidate{
			{ISIN: "US1", Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100, Priority: 0.9},
			{ISIN: "US2", Symbol: "B", Side: "SELL", Quantity: 1, ValueEUR: 100, Priority: 0.8},
			{ISIN: "US3", Symbol: "C", Side: "SELL", Quantity: 1, ValueEUR: 100, Priority: 0.7},
		},
	}

	ctx := &domain.OpportunityContext{}

	var progressUpdates []progress.Update
	config := GenerationConfig{
		MaxDepth:        3,
		AvailableCash:   1000,
		PruneInfeasible: false,
		DetailedProgressCallback: func(update progress.Update) {
			progressUpdates = append(progressUpdates, update)
		},
	}

	generator.Generate(opportunities, ctx, config)

	// Should have at least one progress update per depth level
	depthsSeen := make(map[string]bool)
	for _, update := range progressUpdates {
		depthsSeen[update.SubPhase] = true
	}

	assert.True(t, depthsSeen["depth_1"], "Should report progress for depth 1")
	assert.True(t, depthsSeen["depth_2"], "Should report progress for depth 2")
	assert.True(t, depthsSeen["depth_3"], "Should report progress for depth 3")
}

func TestExhaustiveGenerator_ProgressDetailsContent(t *testing.T) {
	log := zerolog.Nop()
	generator := NewExhaustiveGenerator(log, nil)

	opportunities := domain.OpportunitiesByCategory{
		domain.OpportunityCategoryProfitTaking: []domain.ActionCandidate{
			{ISIN: "US1", Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100, Priority: 0.9},
			{ISIN: "US2", Symbol: "B", Side: "SELL", Quantity: 1, ValueEUR: 100, Priority: 0.8},
		},
	}

	ctx := &domain.OpportunityContext{}

	var lastUpdate progress.Update
	config := GenerationConfig{
		MaxDepth:        2,
		AvailableCash:   1000,
		PruneInfeasible: false,
		DetailedProgressCallback: func(update progress.Update) {
			lastUpdate = update
		},
	}

	generator.Generate(opportunities, ctx, config)

	// Final update should contain expected detail keys
	require.NotNil(t, lastUpdate.Details)
	assert.Contains(t, lastUpdate.Details, "candidates_count")
	assert.Contains(t, lastUpdate.Details, "current_depth")
	assert.Contains(t, lastUpdate.Details, "combinations_at_depth")
	assert.Contains(t, lastUpdate.Details, "sequences_generated")
}

func TestExhaustiveGenerator_NilDetailedCallback(t *testing.T) {
	log := zerolog.Nop()
	generator := NewExhaustiveGenerator(log, nil)

	opportunities := domain.OpportunitiesByCategory{
		domain.OpportunityCategoryProfitTaking: []domain.ActionCandidate{
			{ISIN: "US1", Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100, Priority: 0.9},
		},
	}

	ctx := &domain.OpportunityContext{}

	config := GenerationConfig{
		MaxDepth:                 2,
		AvailableCash:            1000,
		DetailedProgressCallback: nil, // nil callback
	}

	// Should not panic with nil callback
	assert.NotPanics(t, func() {
		generator.Generate(opportunities, ctx, config)
	})
}

func TestExhaustiveGenerator_ProgressReportsInfeasiblePruning(t *testing.T) {
	log := zerolog.Nop()
	generator := NewExhaustiveGenerator(log, nil)

	// Set up opportunities where BUY exceeds available cash
	opportunities := domain.OpportunitiesByCategory{
		domain.OpportunityCategoryOpportunityBuys: []domain.ActionCandidate{
			{ISIN: "US1", Symbol: "A", Side: "BUY", Quantity: 10, ValueEUR: 5000, Priority: 0.9}, // Too expensive
			{ISIN: "US2", Symbol: "B", Side: "BUY", Quantity: 1, ValueEUR: 100, Priority: 0.8},   // Affordable
		},
	}

	ctx := &domain.OpportunityContext{}

	var updates []progress.Update
	config := GenerationConfig{
		MaxDepth:        2,
		AvailableCash:   500, // Limited cash
		PruneInfeasible: true,
		DetailedProgressCallback: func(update progress.Update) {
			updates = append(updates, update)
		},
	}

	sequences := generator.Generate(opportunities, ctx, config)

	// With pruning, the expensive sequence should be excluded
	// Only affordable combinations should remain
	require.NotEmpty(t, sequences)

	// Check that progress updates include infeasible_pruned metric
	var hasInfeasibleMetric bool
	for _, u := range updates {
		if u.Details != nil {
			if _, ok := u.Details["infeasible_pruned"]; ok {
				hasInfeasibleMetric = true
				break
			}
		}
	}
	assert.True(t, hasInfeasibleMetric, "Progress should include infeasible_pruned metric")
}

func TestExhaustiveGenerator_BackwardCompatibility(t *testing.T) {
	log := zerolog.Nop()
	generator := NewExhaustiveGenerator(log, nil)

	opportunities := domain.OpportunitiesByCategory{
		domain.OpportunityCategoryProfitTaking: []domain.ActionCandidate{
			{ISIN: "US1", Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100, Priority: 0.9},
		},
	}

	ctx := &domain.OpportunityContext{}

	// Test that old-style callback still works
	var oldCallbackCalls int
	config := GenerationConfig{
		MaxDepth:      2,
		AvailableCash: 1000,
		ProgressCallback: func(current, total int, message string) {
			oldCallbackCalls++
		},
	}

	generator.Generate(opportunities, ctx, config)

	// Old callback should still be called
	assert.Greater(t, oldCallbackCalls, 0, "Old-style callback should still work")
}

func TestExhaustiveGenerator_BothCallbacksWork(t *testing.T) {
	log := zerolog.Nop()
	generator := NewExhaustiveGenerator(log, nil)

	opportunities := domain.OpportunitiesByCategory{
		domain.OpportunityCategoryProfitTaking: []domain.ActionCandidate{
			{ISIN: "US1", Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100, Priority: 0.9},
		},
	}

	ctx := &domain.OpportunityContext{}

	var oldCalls int
	var detailedCalls int

	config := GenerationConfig{
		MaxDepth:      2,
		AvailableCash: 1000,
		ProgressCallback: func(current, total int, message string) {
			oldCalls++
		},
		DetailedProgressCallback: func(update progress.Update) {
			detailedCalls++
		},
	}

	generator.Generate(opportunities, ctx, config)

	// Both callbacks should work simultaneously
	assert.Greater(t, oldCalls, 0, "Old-style callback should be called")
	assert.Greater(t, detailedCalls, 0, "Detailed callback should be called")
}
