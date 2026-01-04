package scheduler

import (
	"fmt"
	"math"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/satellites"
	"github.com/rs/zerolog"
)

// SatelliteEvaluationJob handles quarterly satellite performance evaluation
// Faithful translation from Python: app/modules/satellites/jobs/quarterly_evaluation.py
//
// Runs every 3 months (quarterly) to:
// 1. Evaluate satellite performance over the past quarter
// 2. Calculate performance scores (Sharpe, Sortino, win rate, etc.)
// 3. Adjust target allocations based on relative performance
// 4. Apply dampening to avoid excessive churn
// 5. Log results and notify if significant changes
type SatelliteEvaluationJob struct {
	log           zerolog.Logger
	metaAllocator *satellites.MetaAllocator
}

// NewSatelliteEvaluationJob creates a new satellite evaluation job
func NewSatelliteEvaluationJob(
	log zerolog.Logger,
	metaAllocator *satellites.MetaAllocator,
) *SatelliteEvaluationJob {
	return &SatelliteEvaluationJob{
		log:           log.With().Str("job", "satellite_evaluation").Logger(),
		metaAllocator: metaAllocator,
	}
}

// Name returns the job name
func (j *SatelliteEvaluationJob) Name() string {
	return "satellite_evaluation"
}

// Run executes the satellite evaluation job
func (j *SatelliteEvaluationJob) Run() error {
	return j.RunWithOptions(3, 0.5, false)
}

// RunWithOptions executes the satellite evaluation job with custom options
// evaluationMonths: Months of history to evaluate (default 3)
// dampeningFactor: How much to move toward target (default 0.5 = 50%)
// dryRun: If true, preview changes without applying (default false)
// Note: Concurrent execution is prevented by the scheduler's SkipIfStillRunning wrapper
func (j *SatelliteEvaluationJob) RunWithOptions(
	evaluationMonths int,
	dampeningFactor float64,
	dryRun bool,
) error {
	j.log.Info().
		Int("evaluation_months", evaluationMonths).
		Float64("dampening_factor", dampeningFactor).
		Bool("dry_run", dryRun).
		Msg("=== Starting quarterly evaluation ===")

	startTime := time.Now()

	// Run evaluation
	var result *satellites.ReallocationResult
	var err error

	if dryRun {
		result, err = j.metaAllocator.PreviewReallocation(evaluationMonths)
		if err != nil {
			j.log.Error().Err(err).Msg("Preview failed")
			return fmt.Errorf("preview failed: %w", err)
		}
		j.log.Info().Msg("DRY RUN: Changes not applied")
	} else {
		result, err = j.metaAllocator.ApplyReallocation(evaluationMonths, dampeningFactor)
		if err != nil {
			j.log.Error().Err(err).Msg("Reallocation failed")
			return fmt.Errorf("reallocation failed: %w", err)
		}
		j.log.Info().Msg("Changes applied to satellite allocations")
	}

	elapsed := time.Since(startTime)

	// Log summary
	j.log.Info().
		Int("satellites_evaluated", result.SatellitesEvaluated).
		Int("satellites_improved", result.SatellitesImproved).
		Int("satellites_reduced", result.SatellitesReduced).
		Float64("elapsed_seconds", elapsed.Seconds()).
		Msg("Quarterly evaluation complete")

	// Log individual recommendations
	for _, rec := range result.Recommendations {
		if math.Abs(rec.AdjustmentPct) > 0.005 { // Only log significant changes (>0.5%)
			j.log.Info().
				Str("bucket_id", rec.BucketID).
				Float64("current_allocation_pct", rec.CurrentAllocationPct).
				Float64("new_allocation_pct", rec.NewAllocationPct).
				Float64("adjustment_pct", rec.AdjustmentPct).
				Str("reason", rec.Reason).
				Msgf("%s: %.2f%% → %.2f%% (%+.2f%%) - %s",
					rec.BucketID,
					rec.CurrentAllocationPct*100,
					rec.NewAllocationPct*100,
					rec.AdjustmentPct*100,
					rec.Reason)
		}
	}

	// Check for major reallocations (>2% change)
	majorChanges := 0
	for _, rec := range result.Recommendations {
		if math.Abs(rec.AdjustmentPct) > 0.02 {
			majorChanges++
		}
	}

	if majorChanges > 0 {
		j.log.Warn().
			Int("major_changes", majorChanges).
			Msg("Major allocation changes detected")

		for _, rec := range result.Recommendations {
			if math.Abs(rec.AdjustmentPct) > 0.02 {
				j.log.Warn().
					Str("bucket_id", rec.BucketID).
					Float64("adjustment_pct", rec.AdjustmentPct*100).
					Float64("performance_score", rec.PerformanceScore).
					Msgf("  %s: %+.2f%% (score: %.2f)",
						rec.BucketID,
						rec.AdjustmentPct*100,
						rec.PerformanceScore)
			}
		}
	}

	return nil
}

// Preview runs a dry-run evaluation without applying changes
func (j *SatelliteEvaluationJob) Preview(evaluationMonths int) error {
	return j.RunWithOptions(evaluationMonths, 0.5, true)
}
