package evaluation

import (
	"context"
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"time"

	"github.com/aristath/arduino-trader/internal/evaluation"
	"github.com/aristath/arduino-trader/internal/evaluation/models"
	"github.com/aristath/arduino-trader/internal/evaluation/workers"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// Service provides direct evaluation using worker pool (replaces HTTP client).
type Service struct {
	workerPool *workers.WorkerPool
	log        zerolog.Logger
}

// NewService creates a new evaluation service that calls worker pool directly.
func NewService(numWorkers int, log zerolog.Logger) *Service {
	return &Service{
		workerPool: workers.NewWorkerPool(numWorkers),
		log:        log.With().Str("component", "evaluation_service").Logger(),
	}
}

// hashSequence generates a deterministic MD5 hash for a sequence
// Matches legacy Python implementation: (symbol, side, quantity) tuples, order-dependent
// Based on legacy/app/modules/planning/domain/calculations/utils.py:43-60
func hashSequence(actions []domain.ActionCandidate) string {
	type tuple struct {
		Symbol   string `json:"symbol"`
		Side     string `json:"side"`
		Quantity int    `json:"quantity"`
	}

	// Create tuples matching Python: [(c.symbol, c.side, c.quantity) for c in sequence]
	tuples := make([]tuple, len(actions))
	for i, action := range actions {
		tuples[i] = tuple{
			Symbol:   action.Symbol,
			Side:     action.Side,
			Quantity: action.Quantity,
		}
	}

	// JSON marshal (Go's json.Marshal preserves order by default, like sort_keys=False)
	jsonBytes, err := json.Marshal(tuples)
	if err != nil {
		// Fallback: should not happen, but handle gracefully
		return ""
	}

	// MD5 hash and return hex digest (matches hashlib.md5().hexdigest())
	hash := md5.Sum(jsonBytes)
	return hex.EncodeToString(hash[:])
}

// BatchEvaluate evaluates a batch of sequences directly (no HTTP overhead).
func (s *Service) BatchEvaluate(ctx context.Context, sequences []domain.ActionSequence, portfolioHash string) ([]domain.EvaluationResult, error) {
	if len(sequences) == 0 {
		return nil, fmt.Errorf("no sequences to evaluate")
	}

	s.log.Debug().
		Int("sequence_count", len(sequences)).
		Str("portfolio_hash", portfolioHash).
		Msg("Starting batch evaluation")

	// Convert domain sequences to evaluation models
	evalSequences := make([][]models.ActionCandidate, len(sequences))
	for i, seq := range sequences {
		evalActions := make([]models.ActionCandidate, len(seq.Actions))
		for j, action := range seq.Actions {
			evalActions[j] = models.ActionCandidate{
				Side:     models.TradeSide(action.Side),
				Symbol:   action.Symbol,
				Name:     action.Name,
				Quantity: action.Quantity,
				Price:    action.Price,
				ValueEUR: action.ValueEUR,
				Currency: action.Currency,
				Priority: action.Priority,
				Reason:   action.Reason,
				Tags:     action.Tags,
			}
		}
		evalSequences[i] = evalActions
	}

	// Create evaluation context with default values
	// TODO: These should be configurable or passed from the planner
	evalContext := models.EvaluationContext{
		TransactionCostFixed:   0.0,
		TransactionCostPercent: 0.001, // 0.1% default
		// Portfolio context would need to be passed in for full evaluation
		// For now, worker pool will handle basic evaluation
	}

	// Evaluate using worker pool
	startTime := time.Now()
	results := s.workerPool.EvaluateBatch(evalSequences, evalContext)
	elapsed := time.Since(startTime)

	s.log.Info().
		Int("sequence_count", len(sequences)).
		Int("result_count", len(results)).
		Float64("elapsed_seconds", elapsed.Seconds()).
		Float64("ms_per_sequence", float64(elapsed.Milliseconds())/float64(len(sequences))).
		Msg("Batch evaluation complete")

	// Convert results back to domain models
	domainResults := make([]domain.EvaluationResult, len(results))
	for i, result := range results {
		// Get sequence hash - use pre-computed hash if available, otherwise compute it
		sequenceHash := sequences[i].SequenceHash
		if sequenceHash == "" {
			// Fallback: compute hash from actions
			sequenceHash = hashSequence(sequences[i].Actions)
		}

		// Calculate diversification score for breakdown
		divScore := evaluation.CalculateDiversificationScore(result.EndPortfolio)

		// Build score breakdown map
		breakdown := make(map[string]float64)
		breakdown["diversification"] = divScore
		breakdown["transaction_cost"] = result.TransactionCosts
		breakdown["final_score"] = result.Score

		// Extract positions from end portfolio (ensure we have a map even if nil)
		endPositions := make(map[string]float64)
		if result.EndPortfolio.Positions != nil {
			// Copy positions to avoid sharing the same map reference
			for symbol, value := range result.EndPortfolio.Positions {
				endPositions[symbol] = value
			}
		}

		domainResults[i] = domain.EvaluationResult{
			SequenceHash:         sequenceHash,
			PortfolioHash:        portfolioHash,
			EndScore:             result.Score,
			ScoreBreakdown:       breakdown,
			EndCash:              result.EndCashEUR,
			EndContextPositions:  endPositions,
			DiversificationScore: divScore,
			TotalValue:           result.EndPortfolio.TotalValue,
			Feasible:             result.Feasible,
		}
	}

	return domainResults, nil
}

// EvaluateSingleSequence evaluates a single sequence.
func (s *Service) EvaluateSingleSequence(ctx context.Context, sequence domain.ActionSequence, portfolioHash string) (*domain.EvaluationResult, error) {
	results, err := s.BatchEvaluate(ctx, []domain.ActionSequence{sequence}, portfolioHash)
	if err != nil {
		return nil, err
	}

	if len(results) == 0 {
		return nil, fmt.Errorf("no evaluation result returned")
	}

	return &results[0], nil
}

// BatchEvaluateWithOptions provides more control over evaluation parameters.
func (s *Service) BatchEvaluateWithOptions(ctx context.Context, sequences []domain.ActionSequence, portfolioHash string, opts EvaluationOptions) ([]domain.EvaluationResult, error) {
	// TODO: Implement Monte Carlo and stochastic when worker pool supports it
	if opts.UseMonteCarlo || opts.UseStochastic {
		s.log.Warn().Msg("Monte Carlo and stochastic evaluation not yet implemented in direct mode")
	}

	// For now, just use standard batch evaluation
	return s.BatchEvaluate(ctx, sequences, portfolioHash)
}

// HealthCheck is no longer needed (no external service) but kept for interface compatibility.
func (s *Service) HealthCheck(ctx context.Context) error {
	// Always healthy - it's in-process
	s.log.Debug().Msg("Evaluation service health check (in-process, always healthy)")
	return nil
}

// EvaluationOptions configures evaluation behavior.
type EvaluationOptions struct {
	UseMonteCarlo   bool
	UseStochastic   bool
	ParallelWorkers int
}

// DefaultEvaluationOptions returns sensible defaults for evaluation.
func DefaultEvaluationOptions() EvaluationOptions {
	return EvaluationOptions{
		UseMonteCarlo:   false, // Faster without Monte Carlo
		UseStochastic:   false, // Faster without stochastic scenarios
		ParallelWorkers: 4,     // 4 workers for good parallelism
	}
}
