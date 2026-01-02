package scheduler

import (
	"github.com/robfig/cron/v3"
	"github.com/rs/zerolog"
)

// Job represents a scheduled job
type Job interface {
	Run() error
	Name() string
}

// Scheduler manages background jobs
type Scheduler struct {
	cron *cron.Cron
	log  zerolog.Logger
}

// New creates a new scheduler
func New(log zerolog.Logger) *Scheduler {
	return &Scheduler{
		cron: cron.New(cron.WithSeconds()),
		log:  log.With().Str("component", "scheduler").Logger(),
	}
}

// Start starts the scheduler
func (s *Scheduler) Start() {
	s.cron.Start()
	s.log.Info().Msg("Scheduler started")
}

// Stop stops the scheduler
func (s *Scheduler) Stop() {
	ctx := s.cron.Stop()
	<-ctx.Done()
	s.log.Info().Msg("Scheduler stopped")
}

// AddJob registers a new job with cron schedule
// Schedule examples:
//   - "0 */5 * * * *"      - Every 5 minutes
//   - "@hourly"            - Every hour
//   - "0 9 * * MON-FRI"    - 9 AM weekdays
//   - "@every 30s"         - Every 30 seconds
func (s *Scheduler) AddJob(schedule string, job Job) error {
	_, err := s.cron.AddFunc(schedule, func() {
		s.log.Debug().Str("job", job.Name()).Msg("Running job")

		if err := job.Run(); err != nil {
			s.log.Error().
				Err(err).
				Str("job", job.Name()).
				Msg("Job failed")
		} else {
			s.log.Debug().Str("job", job.Name()).Msg("Job completed")
		}
	})

	if err != nil {
		return err
	}

	s.log.Info().
		Str("schedule", schedule).
		Str("job", job.Name()).
		Msg("Job registered")

	return nil
}

// RunNow executes a job immediately (outside schedule)
func (s *Scheduler) RunNow(job Job) error {
	s.log.Info().Str("job", job.Name()).Msg("Running job immediately")
	return job.Run()
}
