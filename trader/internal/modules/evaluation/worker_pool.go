package evaluation

import (
	"sync"
)

// WorkerPool manages a pool of worker goroutines for parallel sequence evaluation
type WorkerPool struct {
	numWorkers int
}

// NewWorkerPool creates a new worker pool with the specified number of workers
func NewWorkerPool(numWorkers int) *WorkerPool {
	if numWorkers <= 0 {
		numWorkers = 10 // Default to 10 workers
	}
	return &WorkerPool{
		numWorkers: numWorkers,
	}
}

// EvaluateBatch evaluates multiple sequences in parallel using the worker pool
//
// This is the main entry point for parallel evaluation. It distributes
// sequences across worker goroutines and collects results.
//
// Args:
//   - sequences: List of sequences to evaluate
//   - context: Evaluation context shared by all sequences
//
// Returns:
//   - List of evaluation results (same order as input sequences)
func (wp *WorkerPool) EvaluateBatch(
	sequences [][]ActionCandidate,
	context EvaluationContext,
) []SequenceEvaluationResult {
	numSequences := len(sequences)
	if numSequences == 0 {
		return []SequenceEvaluationResult{}
	}

	// Create channels for work distribution and result collection
	jobs := make(chan jobItem, numSequences)
	results := make(chan resultItem, numSequences)

	// Start workers
	var wg sync.WaitGroup
	numActualWorkers := wp.numWorkers
	if numSequences < numActualWorkers {
		numActualWorkers = numSequences // Don't spawn more workers than sequences
	}

	for i := 0; i < numActualWorkers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			worker(jobs, results, context)
		}()
	}

	// Send jobs to workers
	for idx, sequence := range sequences {
		jobs <- jobItem{
			index:    idx,
			sequence: sequence,
		}
	}
	close(jobs)

	// Wait for all workers to finish, then close results
	wg.Wait()
	close(results)

	// Collect results
	resultSlice := make([]SequenceEvaluationResult, numSequences)
	for result := range results {
		resultSlice[result.index] = result.evalResult
	}

	return resultSlice
}

// jobItem represents a single evaluation job
type jobItem struct {
	sequence []ActionCandidate
	index    int
}

// resultItem represents the result of an evaluation job
type resultItem struct {
	evalResult SequenceEvaluationResult
	index      int
}

// worker is the worker goroutine that processes evaluation jobs
func worker(
	jobs <-chan jobItem,
	results chan<- resultItem,
	context EvaluationContext,
) {
	for job := range jobs {
		// Evaluate the sequence
		evalResult := EvaluateSequence(job.sequence, context)

		// Send result
		results <- resultItem{
			index:      job.index,
			evalResult: evalResult,
		}
	}
}

// SimulateBatch simulates multiple sequences in parallel (no scoring)
//
// This is used for pre-evaluation simulation to collect end states
// for metrics pre-fetching. Much faster than Python sequential simulation.
//
// Args:
//   - sequences: List of sequences to simulate
//   - context: Evaluation context shared by all sequences
//
// Returns:
//   - List of simulation results (same order as input sequences)
func (wp *WorkerPool) SimulateBatch(
	sequences [][]ActionCandidate,
	context EvaluationContext,
) []SimulationResult {
	numSequences := len(sequences)
	if numSequences == 0 {
		return []SimulationResult{}
	}

	// Create channels for work distribution and result collection
	jobs := make(chan simJobItem, numSequences)
	results := make(chan simResultItem, numSequences)

	// Start workers
	var wg sync.WaitGroup
	numActualWorkers := wp.numWorkers
	if numSequences < numActualWorkers {
		numActualWorkers = numSequences
	}

	for i := 0; i < numActualWorkers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			simWorker(jobs, results, context)
		}()
	}

	// Send jobs to workers
	for idx, sequence := range sequences {
		jobs <- simJobItem{
			index:    idx,
			sequence: sequence,
		}
	}
	close(jobs)

	// Wait for all workers to finish, then close results
	wg.Wait()
	close(results)

	// Collect results
	resultSlice := make([]SimulationResult, numSequences)
	for result := range results {
		resultSlice[result.index] = result.simResult
	}

	return resultSlice
}

// simJobItem represents a single simulation job
type simJobItem struct {
	sequence []ActionCandidate
	index    int
}

// simResultItem represents the result of a simulation job
type simResultItem struct {
	simResult SimulationResult
	index     int
}

// simWorker is the worker goroutine that processes simulation jobs
func simWorker(
	jobs <-chan simJobItem,
	results chan<- simResultItem,
	context EvaluationContext,
) {
	for job := range jobs {
		// Check feasibility first
		feasible := CheckSequenceFeasibility(
			job.sequence,
			context.AvailableCashEUR,
			context.PortfolioContext,
		)

		if !feasible {
			results <- simResultItem{
				index: job.index,
				simResult: SimulationResult{
					Sequence:     job.sequence,
					EndPortfolio: context.PortfolioContext,
					EndCashEUR:   context.AvailableCashEUR,
					Feasible:     false,
				},
			}
			continue
		}

		// Simulate the sequence
		endContext, endCash := SimulateSequence(
			job.sequence,
			context.PortfolioContext,
			context.AvailableCashEUR,
			context.Securities,
			context.PriceAdjustments,
		)

		// Send result
		results <- simResultItem{
			index: job.index,
			simResult: SimulationResult{
				Sequence:     job.sequence,
				EndPortfolio: endContext,
				EndCashEUR:   endCash,
				Feasible:     true,
			},
		}
	}
}
