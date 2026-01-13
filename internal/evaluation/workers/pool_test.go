package workers

import (
	"testing"

	"github.com/aristath/sentinel/internal/evaluation/models"
	"github.com/stretchr/testify/assert"
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
