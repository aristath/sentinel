package planner

import (
	"context"
	"fmt"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// IncrementalPlanner handles batch generation and incremental evaluation of sequences.
type IncrementalPlanner struct {
	planner    *Planner
	repository Repository
	log        zerolog.Logger
}

// Repository interface defines operations needed for persistence.
type Repository interface {
	InsertSequence(portfolioHash string, sequence domain.ActionSequence) (int, error)
	InsertEvaluation(result domain.EvaluationResult) error
	UpsertBestResult(portfolioHash string, result domain.EvaluationResult, sequence domain.ActionSequence) error
}

// NewIncrementalPlanner creates a new incremental planner.
func NewIncrementalPlanner(planner *Planner, repository Repository, log zerolog.Logger) *IncrementalPlanner {
	return &IncrementalPlanner{
		planner:    planner,
		repository: repository,
		log:        log.With().Str("component", "incremental_planner").Logger(),
	}
}

// BatchGenerationConfig configures batch generation behavior.
type BatchGenerationConfig struct {
	BatchSize          int           // Number of sequences to evaluate per batch
	MaxBatches         int           // Maximum number of batches (0 = unlimited)
	BatchDelay         time.Duration // Delay between batches
	SaveProgress       bool          // Save progress to database after each batch
	StopOnBestFound    bool          // Stop if best sequence exceeds threshold
	BestScoreThreshold float64       // Threshold for early stopping
}

// DefaultBatchConfig returns sensible defaults for batch generation.
func DefaultBatchConfig() BatchGenerationConfig {
	return BatchGenerationConfig{
		BatchSize:          100, // 100 sequences per batch
		MaxBatches:         0,   // Unlimited batches
		BatchDelay:         1 * time.Second,
		SaveProgress:       true,
		StopOnBestFound:    false,
		BestScoreThreshold: 0.9,
	}
}

// GenerateBatch generates and evaluates sequences incrementally in batches.
func (ip *IncrementalPlanner) GenerateBatch(
	ctx *domain.OpportunityContext,
	config *domain.PlannerConfiguration,
	batchConfig BatchGenerationConfig,
) (*BatchResult, error) {
	ip.log.Info().Msg("Starting batch generation")

	startTime := time.Now()
	result := &BatchResult{
		PortfolioHash:      ip.planner.generatePortfolioHash(ctx),
		StartTime:          startTime,
		SequencesTotal:     0,
		SequencesEvaluated: 0,
		Batches:            []BatchInfo{},
	}

	// Step 1: Identify opportunities
	opportunities, err := ip.planner.opportunitiesService.IdentifyOpportunities(ctx, config)
	if err != nil {
		return nil, fmt.Errorf("failed to identify opportunities: %w", err)
	}

	ip.log.Info().Int("opportunities", countOpportunities(opportunities)).Msg("Opportunities identified")

	// Step 2: Generate all sequences upfront
	sequences, err := ip.planner.sequencesService.GenerateSequences(opportunities, config)
	if err != nil {
		return nil, fmt.Errorf("failed to generate sequences: %w", err)
	}

	result.SequencesTotal = len(sequences)
	ip.log.Info().Int("sequences", len(sequences)).Msg("Sequences generated")

	if len(sequences) == 0 {
		result.EndTime = time.Now()
		result.Elapsed = result.EndTime.Sub(result.StartTime)
		return result, nil
	}

	// Persist all sequences to database for tracking
	if batchConfig.SaveProgress && ip.repository != nil {
		for _, seq := range sequences {
			if _, err := ip.repository.InsertSequence(result.PortfolioHash, seq); err != nil {
				ip.log.Warn().
					Err(err).
					Str("pattern", seq.PatternType).
					Msg("Failed to persist sequence")
			}
		}
		ip.log.Info().
			Int("sequences_persisted", len(sequences)).
			Msg("All sequences persisted to database")
	}

	// Step 3: Evaluate sequences in batches
	batchNum := 0
	offset := 0

	for offset < len(sequences) {
		batchNum++

		// Check if we've hit max batches limit
		if batchConfig.MaxBatches > 0 && batchNum > batchConfig.MaxBatches {
			ip.log.Info().Int("batch_num", batchNum).Msg("Reached max batches limit")
			break
		}

		// Determine batch end index
		batchEnd := offset + batchConfig.BatchSize
		if batchEnd > len(sequences) {
			batchEnd = len(sequences)
		}

		batchSequences := sequences[offset:batchEnd]
		batchStartTime := time.Now()

		ip.log.Info().
			Int("batch_num", batchNum).
			Int("batch_size", len(batchSequences)).
			Int("offset", offset).
			Int("total", len(sequences)).
			Msg("Evaluating batch")

		// Evaluate batch
		evalCtx := context.Background()
		batchResults, err := ip.planner.evaluationService.BatchEvaluate(
			evalCtx,
			batchSequences,
			result.PortfolioHash,
		)
		if err != nil {
			ip.log.Error().Err(err).Int("batch_num", batchNum).Msg("Batch evaluation failed")
			// Continue to next batch on error
			offset = batchEnd
			continue
		}

		batchElapsed := time.Since(batchStartTime)

		// Find best in this batch
		var batchBestScore float64
		for _, res := range batchResults {
			if res.Feasible && res.EndScore > batchBestScore {
				batchBestScore = res.EndScore
			}
		}

		// Record batch info
		batchInfo := BatchInfo{
			BatchNumber: batchNum,
			Size:        len(batchSequences),
			Evaluated:   len(batchResults),
			BestScore:   batchBestScore,
			Elapsed:     batchElapsed,
		}
		result.Batches = append(result.Batches, batchInfo)

		result.SequencesEvaluated += len(batchResults)

		// Update overall best score
		if batchBestScore > result.BestScore {
			result.BestScore = batchBestScore
			ip.log.Info().
				Float64("best_score", result.BestScore).
				Int("batch_num", batchNum).
				Msg("New best score found")
		}

		ip.log.Info().
			Int("batch_num", batchNum).
			Int("evaluated", len(batchResults)).
			Float64("batch_best", batchBestScore).
			Float64("overall_best", result.BestScore).
			Float64("elapsed_seconds", batchElapsed.Seconds()).
			Msg("Batch complete")

		// Save progress to database if enabled
		if batchConfig.SaveProgress && ip.repository != nil {
			// Persist evaluation results and update best if improved
			for i, evalResult := range batchResults {
				// Set portfolio hash on evaluation result
				evalResult.PortfolioHash = result.PortfolioHash

				// Insert evaluation result
				if err := ip.repository.InsertEvaluation(evalResult); err != nil {
					ip.log.Warn().
						Err(err).
						Str("sequence_hash", evalResult.SequenceHash).
						Msg("Failed to persist evaluation result")
					continue
				}

				// Update best result if this is better
				if evalResult.Feasible && evalResult.EndScore > result.BestScore {
					if err := ip.repository.UpsertBestResult(
						result.PortfolioHash,
						evalResult,
						batchSequences[i],
					); err != nil {
						ip.log.Warn().
							Err(err).
							Float64("score", evalResult.EndScore).
							Msg("Failed to update best result")
					} else {
						ip.log.Info().
							Float64("new_best_score", evalResult.EndScore).
							Msg("Best result updated in database")
					}
				}
			}

			ip.log.Debug().
				Int("batch_num", batchNum).
				Int("persisted", len(batchResults)).
				Msg("Batch results persisted to database")
		}

		// Check early stopping condition
		if batchConfig.StopOnBestFound && result.BestScore >= batchConfig.BestScoreThreshold {
			ip.log.Info().
				Float64("best_score", result.BestScore).
				Float64("threshold", batchConfig.BestScoreThreshold).
				Msg("Best score threshold reached, stopping early")
			break
		}

		// Move to next batch
		offset = batchEnd

		// Delay before next batch
		if offset < len(sequences) && batchConfig.BatchDelay > 0 {
			time.Sleep(batchConfig.BatchDelay)
		}
	}

	result.EndTime = time.Now()
	result.Elapsed = result.EndTime.Sub(result.StartTime)
	result.Complete = (offset >= len(sequences))

	ip.log.Info().
		Int("sequences_total", result.SequencesTotal).
		Int("sequences_evaluated", result.SequencesEvaluated).
		Float64("best_score", result.BestScore).
		Int("batches", len(result.Batches)).
		Float64("elapsed_seconds", result.Elapsed.Seconds()).
		Bool("complete", result.Complete).
		Msg("Batch generation complete")

	return result, nil
}

// BatchResult contains the results of batch generation.
type BatchResult struct {
	PortfolioHash      string        `json:"portfolio_hash"`
	StartTime          time.Time     `json:"start_time"`
	EndTime            time.Time     `json:"end_time"`
	Elapsed            time.Duration `json:"elapsed"`
	SequencesTotal     int           `json:"sequences_total"`
	SequencesEvaluated int           `json:"sequences_evaluated"`
	BestScore          float64       `json:"best_score"`
	Complete           bool          `json:"complete"`
	Batches            []BatchInfo   `json:"batches"`
}

// BatchInfo contains information about a single batch.
type BatchInfo struct {
	BatchNumber int           `json:"batch_number"`
	Size        int           `json:"size"`
	Evaluated   int           `json:"evaluated"`
	BestScore   float64       `json:"best_score"`
	Elapsed     time.Duration `json:"elapsed"`
}

// countOpportunities counts total opportunities across all categories.
func countOpportunities(opportunities domain.OpportunitiesByCategory) int {
	count := 0
	for _, candidates := range opportunities {
		count += len(candidates)
	}
	return count
}

// Progress calculates the current progress percentage.
func (br *BatchResult) Progress() float64 {
	if br.SequencesTotal == 0 {
		return 0.0
	}
	return float64(br.SequencesEvaluated) / float64(br.SequencesTotal)
}

// AverageTimePerBatch calculates average time spent per batch.
func (br *BatchResult) AverageTimePerBatch() time.Duration {
	if len(br.Batches) == 0 {
		return 0
	}
	return br.Elapsed / time.Duration(len(br.Batches))
}

// EstimatedTimeRemaining estimates time remaining based on current progress.
func (br *BatchResult) EstimatedTimeRemaining() time.Duration {
	if br.SequencesEvaluated == 0 || br.SequencesTotal == 0 {
		return 0
	}

	avgTimePerSequence := br.Elapsed / time.Duration(br.SequencesEvaluated)
	remaining := br.SequencesTotal - br.SequencesEvaluated
	return avgTimePerSequence * time.Duration(remaining)
}
