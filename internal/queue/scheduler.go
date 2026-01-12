package queue

import (
	"sync"
	"time"

	"github.com/rs/zerolog"
)

// MarketStateDetectorInterface defines the interface for market state detection
type MarketStateDetectorInterface interface {
	GetSyncInterval(now time.Time) time.Duration
}

// Scheduler enqueues time-based jobs
type Scheduler struct {
	manager             *Manager
	marketStateDetector MarketStateDetectorInterface
	deploymentInterval  time.Duration // Configurable deployment check interval
	stop                chan struct{}
	log                 zerolog.Logger
	stopped             bool
	started             bool
	mu                  sync.Mutex
	wg                  sync.WaitGroup // Track goroutine lifecycle
}

// NewScheduler creates a new time-based scheduler
func NewScheduler(manager *Manager) *Scheduler {
	return &Scheduler{
		manager:            manager,
		deploymentInterval: 5 * time.Minute, // Default interval
		stop:               make(chan struct{}),
		log:                zerolog.Nop(),
	}
}

// SetMarketStateDetector sets the market state detector for market-aware scheduling
func (s *Scheduler) SetMarketStateDetector(detector MarketStateDetectorInterface) {
	s.marketStateDetector = detector
}

// SetLogger sets the logger for the scheduler
func (s *Scheduler) SetLogger(log zerolog.Logger) {
	s.log = log.With().Str("component", "time_scheduler").Logger()
}

// SetDeploymentInterval sets the deployment check interval
func (s *Scheduler) SetDeploymentInterval(interval time.Duration) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.deploymentInterval = interval
	s.log.Info().Dur("interval", interval).Msg("Deployment interval configured")
}

// Start starts the scheduler
func (s *Scheduler) Start() {
	s.mu.Lock()
	defer s.mu.Unlock()

	// Prevent multiple starts
	if s.started && !s.stopped {
		s.log.Warn().Msg("Time scheduler already started, ignoring")
		return
	}

	if s.stopped {
		// Reset stop channel if it was stopped
		s.stop = make(chan struct{})
		s.stopped = false
	}

	s.started = true
	s.log.Info().Msg("Time scheduler started")

	// Deployment check (configurable interval via settings - default: 5 minutes)
	// This runs at whatever interval is configured in job_auto_deploy_minutes setting
	deploymentTicker := time.NewTicker(1 * time.Minute) // Check every minute to respect setting changes
	s.wg.Add(1)
	go func() {
		defer s.wg.Done()
		for {
			select {
			case <-s.stop:
				deploymentTicker.Stop()
				return
			case <-deploymentTicker.C:
				// Enqueue deployment check (interval is checked by queue manager)
				s.mu.Lock()
				interval := s.deploymentInterval
				s.mu.Unlock()
				s.enqueueTimeBasedJob(JobTypeDeployment, PriorityMedium, interval)
			}
		}
	}()

	// Hourly jobs (every hour at :00)
	hourlyTicker := time.NewTicker(1 * time.Hour)
	s.wg.Add(1)
	go func() {
		defer s.wg.Done()
		// Run immediately on start, then every hour
		s.enqueueTimeBasedJob(JobTypeHourlyBackup, PriorityMedium, 1*time.Hour)
		s.enqueueTimeBasedJob(JobTypeRetryTrades, PriorityHigh, 1*time.Hour)
		s.enqueueTimeBasedJob(JobTypeRecommendationGC, PriorityMedium, 1*time.Hour)
		for {
			select {
			case <-s.stop:
				hourlyTicker.Stop()
				return
			case <-hourlyTicker.C:
				s.enqueueTimeBasedJob(JobTypeHourlyBackup, PriorityMedium, 1*time.Hour)
				s.enqueueTimeBasedJob(JobTypeRetryTrades, PriorityHigh, 1*time.Hour)
				s.enqueueTimeBasedJob(JobTypeRecommendationGC, PriorityMedium, 1*time.Hour)
			}
		}
	}()

	// Daily jobs (check every minute, enqueue at specific times)
	dailyTicker := time.NewTicker(1 * time.Minute)
	s.wg.Add(1)
	go func() {
		defer s.wg.Done()
		for {
			select {
			case <-s.stop:
				dailyTicker.Stop()
				return
			case now := <-dailyTicker.C:
				hour := now.Hour()
				minute := now.Minute()

				// Health check: Daily at 4:00 AM
				if hour == 4 && minute == 0 {
					s.enqueueTimeBasedJob(JobTypeHealthCheck, PriorityMedium, 24*time.Hour)
				}

				// Daily backup: Daily at 1:00 AM
				if hour == 1 && minute == 0 {
					s.enqueueTimeBasedJob(JobTypeDailyBackup, PriorityMedium, 24*time.Hour)
				}

				// Daily maintenance: Daily at 2:00 AM
				if hour == 2 && minute == 0 {
					s.enqueueTimeBasedJob(JobTypeDailyMaintenance, PriorityMedium, 24*time.Hour)
				}

				// R2 Backup: Daily at 3:00 AM (after local backups complete)
				if hour == 3 && minute == 0 {
					s.enqueueTimeBasedJob(JobTypeR2Backup, PriorityLow, 24*time.Hour)
				}

				// R2 Backup Rotation: Daily at 3:30 AM
				if hour == 3 && minute == 30 {
					s.enqueueTimeBasedJob(JobTypeR2BackupRotation, PriorityLow, 24*time.Hour)
				}

				// Adaptive market check: Daily at 6:00 AM
				if hour == 6 && minute == 0 {
					s.enqueueTimeBasedJob(JobTypeAdaptiveMarket, PriorityMedium, 24*time.Hour)
				}

				// History cleanup: Daily at midnight (00:00)
				if hour == 0 && minute == 0 {
					s.enqueueTimeBasedJob(JobTypeHistoryCleanup, PriorityMedium, 24*time.Hour)
				}

				// Client data cleanup: Daily at 00:30 AM (after history cleanup)
				if hour == 0 && minute == 30 {
					s.enqueueTimeBasedJob(JobTypeClientDataCleanup, PriorityMedium, 24*time.Hour)
				}

				// Dividend reinvestment: Daily at 10:00 AM
				if hour == 10 && minute == 0 {
					s.enqueueTimeBasedJob(JobTypeDividendReinvest, PriorityHigh, 24*time.Hour)
				}
			}
		}
	}()

	// Market-aware sync cycle (checks every minute, dynamic interval based on market state)
	if s.marketStateDetector != nil {
		syncTicker := time.NewTicker(1 * time.Minute)
		s.wg.Add(1)
		go func() {
			defer s.wg.Done()
			lastState := ""
			lastSyncMinute := -1 // Track last sync minute to prevent duplicates

			for {
				select {
				case <-s.stop:
					syncTicker.Stop()
					return
				case now := <-syncTicker.C:
					// Get current market state and interval
					interval := s.marketStateDetector.GetSyncInterval(now)

					// Determine state string from interval for logging
					state := "all_closed"
					if interval == 5*time.Minute {
						state = "dominant_open_or_pre_market"
					} else if interval == 10*time.Minute {
						state = "secondary_open"
					}

					// Log state changes
					if state != lastState {
						s.log.Info().
							Str("old_state", lastState).
							Str("new_state", state).
							Dur("interval", interval).
							Msg("Market state changed")
						lastState = state
					}

					// Skip if markets are closed (interval == 0)
					if interval == 0 {
						continue
					}

					// Calculate if we should sync now based on interval
					currentMinute := now.Minute()
					minutesSinceHour := currentMinute

					// Determine if this minute matches the interval
					shouldSync := false
					if interval == 5*time.Minute {
						// Every 5 minutes: 0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55
						shouldSync = minutesSinceHour%5 == 0
					} else if interval == 10*time.Minute {
						// Every 10 minutes: 0, 10, 20, 30, 40, 50
						shouldSync = minutesSinceHour%10 == 0
					}

					// Enqueue if interval matches and not already synced this minute
					if shouldSync && currentMinute != lastSyncMinute {
						enqueued := s.enqueueTimeBasedJob(JobTypeSyncCycle, PriorityHigh, interval)
						if enqueued {
							lastSyncMinute = currentMinute
							s.log.Debug().
								Str("state", state).
								Dur("interval", interval).
								Int("minute", currentMinute).
								Msg("Sync cycle enqueued (market-aware)")
						}
					}
				}
			}
		}()
	} else {
		// Fallback: Fixed 30-minute interval if no market state detector
		s.log.Warn().Msg("No market state detector configured, using fixed 30-minute sync cycle")
		fallbackSyncTicker := time.NewTicker(1 * time.Minute)
		s.wg.Add(1)
		go func() {
			defer s.wg.Done()
			for {
				select {
				case <-s.stop:
					fallbackSyncTicker.Stop()
					return
				case now := <-fallbackSyncTicker.C:
					if now.Minute()%30 == 0 {
						s.enqueueTimeBasedJob(JobTypeSyncCycle, PriorityHigh, 30*time.Minute)
					}
				}
			}
		}()
	}

	// Weekly jobs (check every minute, enqueue on Sunday at specific times)
	weeklyTicker := time.NewTicker(1 * time.Minute)
	s.wg.Add(1)
	go func() {
		defer s.wg.Done()
		for {
			select {
			case <-s.stop:
				weeklyTicker.Stop()
				return
			case now := <-weeklyTicker.C:
				if now.Weekday() == time.Sunday {
					hour := now.Hour()
					minute := now.Minute()

					// Weekly backup: Sunday at 1:00 AM
					if hour == 1 && minute == 0 {
						s.enqueueTimeBasedJob(JobTypeWeeklyBackup, PriorityMedium, 7*24*time.Hour)
					}

					// Weekly maintenance: Sunday at 3:30 AM
					if hour == 3 && minute == 30 {
						s.enqueueTimeBasedJob(JobTypeWeeklyMaintenance, PriorityMedium, 7*24*time.Hour)
					}
				}
			}
		}
	}()

	// Monthly jobs (check every minute, enqueue on 1st at specific times)
	monthlyTicker := time.NewTicker(1 * time.Minute)
	s.wg.Add(1)
	go func() {
		defer s.wg.Done()
		for {
			select {
			case <-s.stop:
				monthlyTicker.Stop()
				return
			case now := <-monthlyTicker.C:
				if now.Day() == 1 {
					hour := now.Hour()
					minute := now.Minute()

					// Monthly backup: 1st at 1:00 AM
					if hour == 1 && minute == 0 {
						s.enqueueTimeBasedJob(JobTypeMonthlyBackup, PriorityMedium, 30*24*time.Hour)
					}

					// Monthly maintenance: 1st at 4:00 AM
					if hour == 4 && minute == 0 {
						s.enqueueTimeBasedJob(JobTypeMonthlyMaintenance, PriorityMedium, 30*24*time.Hour)
					}

					// Formula discovery: 1st at 5:00 AM
					if hour == 5 && minute == 0 {
						s.enqueueTimeBasedJob(JobTypeFormulaDiscovery, PriorityMedium, 30*24*time.Hour)
					}
				}
			}
		}
	}()
}

// Stop stops the scheduler and waits for all goroutines to finish
func (s *Scheduler) Stop() {
	s.mu.Lock()
	if s.stopped {
		s.mu.Unlock()
		return
	}

	// Signal all goroutines to stop
	close(s.stop)
	s.stopped = true
	s.started = false
	s.mu.Unlock()

	// Wait for all goroutines to finish
	s.wg.Wait()
	s.log.Info().Msg("Time scheduler stopped")
}

// enqueueTimeBasedJob enqueues a job if the interval has passed
func (s *Scheduler) enqueueTimeBasedJob(jobType JobType, priority Priority, interval time.Duration) bool {
	enqueued := s.manager.EnqueueIfShouldRun(jobType, priority, interval, map[string]interface{}{})
	if enqueued {
		s.log.Info().
			Str("job_type", string(jobType)).
			Dur("interval", interval).
			Msg("Enqueued time-based job")
	} else {
		s.log.Debug().
			Str("job_type", string(jobType)).
			Dur("interval", interval).
			Msg("Skipped time-based job (interval not yet passed)")
	}
	return enqueued
}
