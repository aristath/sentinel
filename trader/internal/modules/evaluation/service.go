package evaluation

import (
	"runtime"

	"github.com/rs/zerolog"
)

// Service provides evaluation business logic
type Service struct {
	workerPool *WorkerPool
	log        zerolog.Logger
}

// NewService creates a new evaluation service
func NewService(numWorkers int, log zerolog.Logger) *Service {
	// Auto-detect number of workers if not specified
	if numWorkers == 0 {
		numWorkers = runtime.NumCPU()
		if numWorkers < 2 {
			numWorkers = 2
		}
	}

	return &Service{
		workerPool: NewWorkerPool(numWorkers),
		log:        log.With().Str("service", "evaluation").Logger(),
	}
}

// EvaluateBatch evaluates multiple sequences in parallel
func (s *Service) EvaluateBatch(
	sequences [][]ActionCandidate,
	context EvaluationContext,
) ([]SequenceEvaluationResult, error) {
	s.log.Debug().
		Int("sequences", len(sequences)).
		Int("workers", s.workerPool.numWorkers).
		Msg("Starting batch evaluation")

	results := s.workerPool.EvaluateBatch(sequences, context)

	s.log.Debug().
		Int("results", len(results)).
		Msg("Batch evaluation complete")

	return results, nil
}

// SimulateBatch simulates multiple sequences in parallel (no scoring)
func (s *Service) SimulateBatch(
	sequences [][]ActionCandidate,
	context EvaluationContext,
) ([]SimulationResult, error) {
	s.log.Debug().
		Int("sequences", len(sequences)).
		Int("workers", s.workerPool.numWorkers).
		Msg("Starting batch simulation")

	results := s.workerPool.SimulateBatch(sequences, context)

	s.log.Debug().
		Int("results", len(results)).
		Msg("Batch simulation complete")

	return results, nil
}

// EvaluateMonteCarlo performs Monte Carlo simulation
func (s *Service) EvaluateMonteCarlo(req MonteCarloRequest) (MonteCarloResult, error) {
	s.log.Debug().
		Int("paths", req.Paths).
		Int("sequence_length", len(req.Sequence)).
		Msg("Starting Monte Carlo evaluation")

	result := EvaluateMonteCarlo(req)

	s.log.Debug().
		Float64("final_score", result.FinalScore).
		Float64("avg_score", result.AvgScore).
		Msg("Monte Carlo evaluation complete")

	return result, nil
}

// EvaluateStochastic performs stochastic scenario evaluation
func (s *Service) EvaluateStochastic(req StochasticRequest) (StochasticResult, error) {
	s.log.Debug().
		Int("scenarios", len(req.Shifts)).
		Int("sequence_length", len(req.Sequence)).
		Msg("Starting stochastic evaluation")

	result := EvaluateStochastic(req)

	s.log.Debug().
		Float64("weighted_score", result.WeightedScore).
		Float64("base_score", result.BaseScore).
		Msg("Stochastic evaluation complete")

	return result, nil
}
