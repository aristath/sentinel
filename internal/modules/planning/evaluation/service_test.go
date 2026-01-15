package evaluation

import (
	"context"
	"testing"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/planning/progress"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestBatchEvaluateDetailed_WithDetailedProgress(t *testing.T) {
	log := zerolog.Nop()
	service := NewService(2, log)

	sequences := []domain.ActionSequence{
		{
			Actions: []domain.ActionCandidate{
				{Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100},
			},
		},
		{
			Actions: []domain.ActionCandidate{
				{Symbol: "B", Side: "SELL", Quantity: 1, ValueEUR: 100},
			},
		},
		{
			Actions: []domain.ActionCandidate{
				{Symbol: "C", Side: "SELL", Quantity: 1, ValueEUR: 100},
			},
		},
	}

	opportunityCtx := &domain.OpportunityContext{
		AvailableCashEUR:       1000,
		TotalPortfolioValueEUR: 10000,
	}

	var progressUpdates []progress.Update

	callback := func(update progress.Update) {
		progressUpdates = append(progressUpdates, update)
	}

	results, err := service.BatchEvaluateDetailed(
		context.Background(),
		sequences,
		"test-hash",
		nil,
		opportunityCtx,
		callback,
	)

	require.NoError(t, err)
	assert.Len(t, results, 3)

	// Should have received progress updates
	assert.NotEmpty(t, progressUpdates)

	// Verify progress update structure
	for _, update := range progressUpdates {
		assert.Equal(t, "sequence_evaluation", update.Phase)
		assert.NotNil(t, update.Details)
	}
}

func TestBatchEvaluateDetailed_NilCallback(t *testing.T) {
	log := zerolog.Nop()
	service := NewService(2, log)

	sequences := []domain.ActionSequence{
		{
			Actions: []domain.ActionCandidate{
				{Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100},
			},
		},
	}

	opportunityCtx := &domain.OpportunityContext{
		AvailableCashEUR:       1000,
		TotalPortfolioValueEUR: 10000,
	}

	// Should not panic with nil callback
	assert.NotPanics(t, func() {
		_, err := service.BatchEvaluateDetailed(
			context.Background(),
			sequences,
			"test-hash",
			nil,
			opportunityCtx,
			nil,
		)
		assert.NoError(t, err)
	})
}

func TestBatchEvaluateDetailed_DetailsContent(t *testing.T) {
	log := zerolog.Nop()
	service := NewService(2, log)

	sequences := []domain.ActionSequence{
		{
			Actions: []domain.ActionCandidate{
				{Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100},
			},
		},
		{
			Actions: []domain.ActionCandidate{
				{Symbol: "B", Side: "SELL", Quantity: 1, ValueEUR: 100},
			},
		},
	}

	opportunityCtx := &domain.OpportunityContext{
		AvailableCashEUR:       1000,
		TotalPortfolioValueEUR: 10000,
	}

	var lastUpdate progress.Update

	callback := func(update progress.Update) {
		lastUpdate = update
	}

	_, err := service.BatchEvaluateDetailed(
		context.Background(),
		sequences,
		"test-hash",
		nil,
		opportunityCtx,
		callback,
	)

	require.NoError(t, err)

	// Final update should contain expected detail keys
	require.NotNil(t, lastUpdate.Details)
	assert.Contains(t, lastUpdate.Details, "workers_active")
	assert.Contains(t, lastUpdate.Details, "feasible_count")
	assert.Contains(t, lastUpdate.Details, "infeasible_count")
	assert.Contains(t, lastUpdate.Details, "best_score")
	assert.Contains(t, lastUpdate.Details, "elapsed_ms")
	assert.Contains(t, lastUpdate.Details, "sequences_per_second")
}

func TestBatchEvaluateDetailed_Empty(t *testing.T) {
	log := zerolog.Nop()
	service := NewService(2, log)

	var progressCalls int
	callback := func(update progress.Update) {
		progressCalls++
	}

	_, err := service.BatchEvaluateDetailed(
		context.Background(),
		[]domain.ActionSequence{},
		"test-hash",
		nil,
		nil,
		callback,
	)

	// Should return error for empty sequences
	assert.Error(t, err)
	assert.Equal(t, 0, progressCalls, "No progress should be reported for empty input")
}

func TestBatchEvaluateDetailed_TracksFeasibleCount(t *testing.T) {
	log := zerolog.Nop()
	service := NewService(2, log)

	// All feasible sequences (sells that don't require cash)
	sequences := []domain.ActionSequence{
		{
			Actions: []domain.ActionCandidate{
				{Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100},
			},
		},
		{
			Actions: []domain.ActionCandidate{
				{Symbol: "B", Side: "SELL", Quantity: 1, ValueEUR: 100},
			},
		},
	}

	opportunityCtx := &domain.OpportunityContext{
		AvailableCashEUR:       1000,
		TotalPortfolioValueEUR: 10000,
	}

	var lastUpdate progress.Update

	callback := func(update progress.Update) {
		lastUpdate = update
	}

	_, err := service.BatchEvaluateDetailed(
		context.Background(),
		sequences,
		"test-hash",
		nil,
		opportunityCtx,
		callback,
	)

	require.NoError(t, err)

	// Final update should have feasible count
	require.NotNil(t, lastUpdate.Details)
	feasibleCount, ok := lastUpdate.Details["feasible_count"]
	assert.True(t, ok, "Should have feasible_count in details")
	assert.GreaterOrEqual(t, feasibleCount, 0)
}

func TestBatchEvaluateDetailed_ReturnsCorrectResults(t *testing.T) {
	log := zerolog.Nop()
	service := NewService(2, log)

	sequences := []domain.ActionSequence{
		{
			SequenceHash: "hash1",
			Actions: []domain.ActionCandidate{
				{Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100},
			},
		},
		{
			SequenceHash: "hash2",
			Actions: []domain.ActionCandidate{
				{Symbol: "B", Side: "SELL", Quantity: 2, ValueEUR: 200},
			},
		},
	}

	opportunityCtx := &domain.OpportunityContext{
		AvailableCashEUR:       1000,
		TotalPortfolioValueEUR: 10000,
	}

	results, err := service.BatchEvaluateDetailed(
		context.Background(),
		sequences,
		"portfolio-hash",
		nil,
		opportunityCtx,
		nil,
	)

	require.NoError(t, err)
	assert.Len(t, results, 2)

	// Results should maintain order and have proper hashes
	assert.Equal(t, "hash1", results[0].SequenceHash)
	assert.Equal(t, "hash2", results[1].SequenceHash)
	assert.Equal(t, "portfolio-hash", results[0].PortfolioHash)
	assert.Equal(t, "portfolio-hash", results[1].PortfolioHash)
}
