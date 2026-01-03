package scheduler

import (
	"fmt"
	"time"

	"github.com/aristath/arduino-trader/internal/locking"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/satellites"
	"github.com/rs/zerolog"
)

// SatelliteMaintenanceJob handles daily bucket maintenance
// Faithful translation from Python: app/modules/satellites/jobs/bucket_maintenance.py
//
// Runs daily to:
// 1. Update high water marks for all active satellites
// 2. Check for severe drawdowns and trigger hibernation if needed
// 3. Update bucket status based on current conditions
// 4. Reset consecutive losses if bucket recovers
type SatelliteMaintenanceJob struct {
	log           zerolog.Logger
	lockManager   *locking.Manager
	bucketService *satellites.BucketService
	positionRepo  *portfolio.PositionRepository
}

// NewSatelliteMaintenanceJob creates a new satellite maintenance job
func NewSatelliteMaintenanceJob(
	log zerolog.Logger,
	lockManager *locking.Manager,
	bucketService *satellites.BucketService,
	positionRepo *portfolio.PositionRepository,
) *SatelliteMaintenanceJob {
	return &SatelliteMaintenanceJob{
		log:           log.With().Str("job", "satellite_maintenance").Logger(),
		lockManager:   lockManager,
		bucketService: bucketService,
		positionRepo:  positionRepo,
	}
}

// Name returns the job name
func (j *SatelliteMaintenanceJob) Name() string {
	return "satellite_maintenance"
}

// Run executes the satellite maintenance job
func (j *SatelliteMaintenanceJob) Run() error {
	// Acquire lock to prevent concurrent execution
	if err := j.lockManager.Acquire("satellite_maintenance"); err != nil {
		j.log.Warn().Err(err).Msg("Satellite maintenance job already running")
		return nil
	}
	defer j.lockManager.Release("satellite_maintenance")

	j.log.Info().Msg("=== Starting satellite maintenance ===")
	startTime := time.Now()

	// Run high water mark updates
	hwmResult, err := j.updateHighWaterMarks()
	if err != nil {
		j.log.Error().Err(err).Msg("High water mark update failed")
		return fmt.Errorf("high water mark update failed: %w", err)
	}

	// Check for consecutive losses
	lossResult, err := j.checkConsecutiveLosses()
	if err != nil {
		j.log.Error().Err(err).Msg("Consecutive loss check failed")
		return fmt.Errorf("consecutive loss check failed: %w", err)
	}

	elapsed := time.Since(startTime)

	j.log.Info().
		Int("updated", hwmResult.UpdatedCount).
		Int("hibernated", hwmResult.HibernatedCount).
		Int("recovered", hwmResult.RecoveredCount).
		Int("paused", lossResult.PausedCount).
		Float64("elapsed_seconds", elapsed.Seconds()).
		Msg("=== Satellite maintenance complete ===")

	return nil
}

// updateHighWaterMarks updates high water marks for all buckets
func (j *SatelliteMaintenanceJob) updateHighWaterMarks() (*HighWaterMarkResult, error) {
	buckets, err := j.bucketService.GetAllBuckets()
	if err != nil {
		return nil, fmt.Errorf("failed to get buckets: %w", err)
	}

	j.log.Info().Int("bucket_count", len(buckets)).Msg("Updating high water marks")

	result := &HighWaterMarkResult{
		TotalBuckets:    len(buckets),
		UpdatedCount:    0,
		HibernatedCount: 0,
		RecoveredCount:  0,
	}

	for _, bucket := range buckets {
		if err := j.processBucketMaintenanceTask(bucket, result); err != nil {
			j.log.Error().
				Err(err).
				Str("bucket_id", bucket.ID).
				Msg("Failed to process bucket")
			// Continue with other buckets
			continue
		}
	}

	return result, nil
}

// processBucketMaintenanceTask processes maintenance for a single bucket
func (j *SatelliteMaintenanceJob) processBucketMaintenanceTask(
	bucket *satellites.Bucket,
	result *HighWaterMarkResult,
) error {
	// Calculate current bucket value (positions + cash)
	currentValue, err := j.bucketService.CalculateBucketValue(bucket.ID, j.positionRepo)
	if err != nil {
		return fmt.Errorf("failed to calculate bucket value: %w", err)
	}

	// Check if this is a new high water mark
	if bucket.HighWaterMark == 0 || currentValue > bucket.HighWaterMark {
		oldHWM := bucket.HighWaterMark
		_, err := j.bucketService.UpdateHighWaterMark(bucket.ID, currentValue)
		if err != nil {
			return fmt.Errorf("failed to update high water mark: %w", err)
		}

		result.UpdatedCount++

		pctIncrease := 0.0
		if oldHWM > 0 {
			pctIncrease = ((currentValue - oldHWM) / oldHWM) * 100
		}

		j.log.Info().
			Str("bucket_id", bucket.ID).
			Float64("old_hwm", oldHWM).
			Float64("new_hwm", currentValue).
			Float64("pct_increase", pctIncrease).
			Msgf("%s: New high water mark €%.2f (+%.1f%% from €%.2f)",
				bucket.ID, currentValue, pctIncrease, oldHWM)

		// Reset consecutive losses on new high
		if bucket.ConsecutiveLosses > 0 {
			if err := j.bucketService.ResetConsecutiveLosses(bucket.ID); err != nil {
				j.log.Warn().
					Err(err).
					Str("bucket_id", bucket.ID).
					Msg("Failed to reset consecutive losses")
			} else {
				result.RecoveredCount++
				j.log.Info().
					Str("bucket_id", bucket.ID).
					Int("was_consecutive_losses", bucket.ConsecutiveLosses).
					Msg("Reset consecutive losses on new high water mark")
			}
		}
	}

	// Check for severe drawdown (>35% = hibernation threshold)
	if bucket.HighWaterMark > 0 && currentValue > 0 {
		drawdown := (bucket.HighWaterMark - currentValue) / bucket.HighWaterMark
		const hibernationThreshold = 0.35 // 35%

		if drawdown > hibernationThreshold &&
			bucket.Status != satellites.BucketStatusHibernating &&
			bucket.Status != satellites.BucketStatusRetired {

			_, err := j.bucketService.HibernateBucket(bucket.ID)
			if err != nil {
				j.log.Error().
					Err(err).
					Str("bucket_id", bucket.ID).
					Msg("Failed to hibernate bucket")
				return fmt.Errorf("failed to hibernate bucket: %w", err)
			}

			result.HibernatedCount++

			j.log.Warn().
				Str("bucket_id", bucket.ID).
				Float64("drawdown", drawdown*100).
				Float64("high_water_mark", bucket.HighWaterMark).
				Float64("current_value", currentValue).
				Msgf("%s: HIBERNATING due to %.1f%% drawdown (€%.2f → €%.2f)",
					bucket.ID, drawdown*100, bucket.HighWaterMark, currentValue)
		}
	}

	return nil
}

// checkConsecutiveLosses checks for excessive consecutive losses
func (j *SatelliteMaintenanceJob) checkConsecutiveLosses() (*ConsecutiveLossResult, error) {
	buckets, err := j.bucketService.GetAllBuckets()
	if err != nil {
		return nil, fmt.Errorf("failed to get buckets: %w", err)
	}

	result := &ConsecutiveLossResult{
		PausedCount: 0,
	}

	for _, bucket := range buckets {
		if bucket.ConsecutiveLosses >= bucket.MaxConsecutiveLosses {
			if bucket.Status != satellites.BucketStatusPaused &&
				bucket.Status != satellites.BucketStatusHibernating {
				reason := fmt.Sprintf("Consecutive losses threshold reached: %d",
					bucket.ConsecutiveLosses)

				// Pause the bucket using PauseBucket method
				if _, err := j.bucketService.PauseBucket(bucket.ID); err != nil {
					j.log.Error().
						Err(err).
						Str("bucket_id", bucket.ID).
						Msg("Failed to pause bucket")
					continue
				}

				result.PausedCount++
				j.log.Warn().
					Str("bucket_id", bucket.ID).
					Int("consecutive_losses", bucket.ConsecutiveLosses).
					Int("threshold", bucket.MaxConsecutiveLosses).
					Str("reason", reason).
					Msg("PAUSED due to consecutive losses")
			}
		}
	}

	if result.PausedCount > 0 {
		j.log.Info().
			Int("paused_count", result.PausedCount).
			Msg("Paused buckets due to consecutive losses")
	}

	return result, nil
}

// HighWaterMarkResult contains results from high water mark updates
type HighWaterMarkResult struct {
	TotalBuckets    int
	UpdatedCount    int
	HibernatedCount int
	RecoveredCount  int
}

// ConsecutiveLossResult contains results from consecutive loss checks
type ConsecutiveLossResult struct {
	PausedCount int
}
