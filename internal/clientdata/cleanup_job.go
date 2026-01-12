package clientdata

import (
	"github.com/aristath/sentinel/internal/scheduler/base"
	"github.com/rs/zerolog"
)

// CleanupJob removes expired entries from all client data tables.
// It should be scheduled to run daily.
type CleanupJob struct {
	base.JobBase
	repo *Repository
	log  zerolog.Logger
}

// NewCleanupJob creates a new client data cleanup job.
func NewCleanupJob(repo *Repository, log zerolog.Logger) *CleanupJob {
	return &CleanupJob{
		repo: repo,
		log:  log.With().Str("job", "client_data_cleanup").Logger(),
	}
}

// Run executes the cleanup job, removing all expired entries from all tables.
func (j *CleanupJob) Run() error {
	results, err := j.repo.DeleteAllExpired()
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to delete expired client data")
		return err
	}

	// Log cleanup results
	var totalDeleted int64
	for table, count := range results {
		if count > 0 {
			j.log.Info().
				Str("table", table).
				Int64("deleted", count).
				Msg("Cleaned up expired cache entries")
			totalDeleted += count
		}
	}

	if totalDeleted > 0 {
		j.log.Info().
			Int64("total_deleted", totalDeleted).
			Msg("Client data cleanup completed")
	}

	return nil
}

// Name returns the job name for scheduling and logging.
func (j *CleanupJob) Name() string {
	return "client_data_cleanup"
}
