package workers

import (
	"testing"

	"github.com/aristath/sentinel/internal/evaluation/models"
	"github.com/aristath/sentinel/internal/modules/planning/progress"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewWorkerPool(t *testing.T) {
	tests := []struct {
		name            string
		numWorkers      int
		expectedWorkers int
	}{
		{"positive workers", 5, 5},
		{"zero workers defaults to 10", 0, 10},
		{"negative workers defaults to 10", -1, 10},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			pool := NewWorkerPool(tt.numWorkers)
			assert.Equal(t, tt.expectedWorkers, pool.numWorkers)
		})
	}
}

func TestEvaluateBatch_EmptySequences(t *testing.T) {
	pool := NewWorkerPool(2)
	results := pool.EvaluateBatch(nil, models.EvaluationContext{}, nil)
	assert.Empty(t, results)
}

func TestEvaluateBatch_WithProgress(t *testing.T) {
	pool := NewWorkerPool(2)

	// Create simple test sequences
	sequences := [][]models.ActionCandidate{
		{{Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100}},
		{{Symbol: "B", Side: "SELL", Quantity: 1, ValueEUR: 100}},
		{{Symbol: "C", Side: "SELL", Quantity: 1, ValueEUR: 100}},
	}

	context := models.EvaluationContext{
		AvailableCashEUR: 1000,
		PortfolioContext: models.PortfolioContext{
			TotalValue: 10000,
			Positions: map[string]float64{
				"A": 100,
				"B": 100,
				"C": 100,
			},
		},
	}

	// Track progress calls
	var progressCalls []struct {
		current int
		total   int
		message string
	}

	callback := func(current, total int, message string) {
		progressCalls = append(progressCalls, struct {
			current int
			total   int
			message string
		}{current, total, message})
	}

	results := pool.EvaluateBatch(sequences, context, callback)

	// Should have results for all sequences
	assert.Len(t, results, 3)

	// Progress should be called once per sequence
	assert.Len(t, progressCalls, 3, "Progress should be called for each completed evaluation")

	// Verify progress values (order may vary due to parallelism)
	for _, call := range progressCalls {
		assert.Equal(t, 3, call.total, "Total should equal number of sequences")
		assert.GreaterOrEqual(t, call.current, 1, "Current should be >= 1")
		assert.LessOrEqual(t, call.current, 3, "Current should be <= 3")
		assert.Contains(t, call.message, "Evaluating", "Message should describe evaluation")
	}
}

func TestEvaluateBatch_NilProgress(t *testing.T) {
	pool := NewWorkerPool(2)

	sequences := [][]models.ActionCandidate{
		{{Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100}},
	}

	context := models.EvaluationContext{
		AvailableCashEUR: 1000,
		PortfolioContext: models.PortfolioContext{
			TotalValue: 10000,
			Positions:  map[string]float64{"A": 100},
		},
	}

	// Should not panic with nil callback
	assert.NotPanics(t, func() {
		pool.EvaluateBatch(sequences, context, nil)
	})
}

func TestEvaluateBatch_PreservesOrder(t *testing.T) {
	pool := NewWorkerPool(4)

	// Create sequences that can be identified
	sequences := [][]models.ActionCandidate{
		{{Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100}},
		{{Symbol: "B", Side: "SELL", Quantity: 2, ValueEUR: 200}},
		{{Symbol: "C", Side: "SELL", Quantity: 3, ValueEUR: 300}},
		{{Symbol: "D", Side: "SELL", Quantity: 4, ValueEUR: 400}},
	}

	context := models.EvaluationContext{
		AvailableCashEUR: 1000,
		PortfolioContext: models.PortfolioContext{
			TotalValue: 10000,
			Positions: map[string]float64{
				"A": 100, "B": 200, "C": 300, "D": 400,
			},
		},
	}

	results := pool.EvaluateBatch(sequences, context, nil)

	// Results should be in the same order as input sequences
	assert.Len(t, results, 4)
	for i, result := range results {
		assert.Len(t, result.Sequence, 1)
		assert.Equal(t, sequences[i][0].Symbol, result.Sequence[0].Symbol,
			"Result %d should correspond to sequence %d", i, i)
	}
}

// Tests for EvaluateBatchDetailed with detailed progress reporting

func TestEvaluateBatchDetailed_WithDetailedProgress(t *testing.T) {
	pool := NewWorkerPool(2)

	sequences := [][]models.ActionCandidate{
		{{Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100}},
		{{Symbol: "B", Side: "SELL", Quantity: 1, ValueEUR: 100}},
		{{Symbol: "C", Side: "SELL", Quantity: 1, ValueEUR: 100}},
	}

	context := models.EvaluationContext{
		AvailableCashEUR: 1000,
		PortfolioContext: models.PortfolioContext{
			TotalValue: 10000,
			Positions: map[string]float64{
				"A": 100, "B": 100, "C": 100,
			},
		},
	}

	var progressUpdates []progress.Update

	callback := func(update progress.Update) {
		progressUpdates = append(progressUpdates, update)
	}

	results := pool.EvaluateBatchDetailed(sequences, context, callback)

	// Should have results for all sequences
	assert.Len(t, results, 3)

	// Should have received progress updates
	assert.NotEmpty(t, progressUpdates)

	// Verify progress update structure
	for _, update := range progressUpdates {
		assert.Equal(t, "sequence_evaluation", update.Phase)
		assert.NotNil(t, update.Details)
	}
}

func TestEvaluateBatchDetailed_DetailsContent(t *testing.T) {
	pool := NewWorkerPool(2)

	sequences := [][]models.ActionCandidate{
		{{Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100}},
		{{Symbol: "B", Side: "SELL", Quantity: 1, ValueEUR: 100}},
	}

	context := models.EvaluationContext{
		AvailableCashEUR: 1000,
		PortfolioContext: models.PortfolioContext{
			TotalValue: 10000,
			Positions:  map[string]float64{"A": 100, "B": 100},
		},
	}

	var lastUpdate progress.Update

	callback := func(update progress.Update) {
		lastUpdate = update
	}

	pool.EvaluateBatchDetailed(sequences, context, callback)

	// Final update should contain expected detail keys
	require.NotNil(t, lastUpdate.Details)
	assert.Contains(t, lastUpdate.Details, "workers_active")
	assert.Contains(t, lastUpdate.Details, "feasible_count")
	assert.Contains(t, lastUpdate.Details, "infeasible_count")
	assert.Contains(t, lastUpdate.Details, "best_score")
}

func TestEvaluateBatchDetailed_NilCallback(t *testing.T) {
	pool := NewWorkerPool(2)

	sequences := [][]models.ActionCandidate{
		{{Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100}},
	}

	context := models.EvaluationContext{
		AvailableCashEUR: 1000,
		PortfolioContext: models.PortfolioContext{
			TotalValue: 10000,
			Positions:  map[string]float64{"A": 100},
		},
	}

	// Should not panic with nil callback
	assert.NotPanics(t, func() {
		pool.EvaluateBatchDetailed(sequences, context, nil)
	})
}

func TestEvaluateBatchDetailed_TracksFeasibleCount(t *testing.T) {
	pool := NewWorkerPool(2)

	// Mix of feasible and potentially infeasible sequences
	sequences := [][]models.ActionCandidate{
		{{Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100}}, // Feasible
		{{Symbol: "B", Side: "SELL", Quantity: 1, ValueEUR: 100}}, // Feasible
	}

	context := models.EvaluationContext{
		AvailableCashEUR: 1000,
		PortfolioContext: models.PortfolioContext{
			TotalValue: 10000,
			Positions:  map[string]float64{"A": 100, "B": 100},
		},
	}

	var lastUpdate progress.Update

	callback := func(update progress.Update) {
		lastUpdate = update
	}

	pool.EvaluateBatchDetailed(sequences, context, callback)

	// Final update should have feasible count
	require.NotNil(t, lastUpdate.Details)
	feasibleCount, ok := lastUpdate.Details["feasible_count"]
	assert.True(t, ok, "Should have feasible_count in details")
	assert.GreaterOrEqual(t, feasibleCount, 0)
}

func TestEvaluateBatchDetailed_TracksElapsedTime(t *testing.T) {
	pool := NewWorkerPool(2)

	sequences := [][]models.ActionCandidate{
		{{Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100}},
	}

	context := models.EvaluationContext{
		AvailableCashEUR: 1000,
		PortfolioContext: models.PortfolioContext{
			TotalValue: 10000,
			Positions:  map[string]float64{"A": 100},
		},
	}

	var lastUpdate progress.Update

	callback := func(update progress.Update) {
		lastUpdate = update
	}

	pool.EvaluateBatchDetailed(sequences, context, callback)

	// Final update should have elapsed_ms
	require.NotNil(t, lastUpdate.Details)
	assert.Contains(t, lastUpdate.Details, "elapsed_ms")
}

func TestEvaluateBatchDetailed_TracksBestScore(t *testing.T) {
	pool := NewWorkerPool(2)

	sequences := [][]models.ActionCandidate{
		{{Symbol: "A", Side: "SELL", Quantity: 1, ValueEUR: 100}},
		{{Symbol: "B", Side: "SELL", Quantity: 1, ValueEUR: 100}},
	}

	context := models.EvaluationContext{
		AvailableCashEUR: 1000,
		PortfolioContext: models.PortfolioContext{
			TotalValue: 10000,
			Positions:  map[string]float64{"A": 100, "B": 100},
		},
	}

	var lastUpdate progress.Update

	callback := func(update progress.Update) {
		lastUpdate = update
	}

	pool.EvaluateBatchDetailed(sequences, context, callback)

	// Final update should have best_score
	require.NotNil(t, lastUpdate.Details)
	assert.Contains(t, lastUpdate.Details, "best_score")
}

func TestEvaluateBatchDetailed_Empty(t *testing.T) {
	pool := NewWorkerPool(2)

	var progressCalls int
	callback := func(update progress.Update) {
		progressCalls++
	}

	results := pool.EvaluateBatchDetailed(nil, models.EvaluationContext{}, callback)
	assert.Empty(t, results)
	assert.Equal(t, 0, progressCalls, "No progress should be reported for empty input")
}
