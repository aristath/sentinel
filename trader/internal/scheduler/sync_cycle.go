package scheduler

import (
	"fmt"
	"time"

	"github.com/aristath/sentinel/internal/events"
	"github.com/aristath/sentinel/internal/modules/display"
	"github.com/rs/zerolog"
)

// SyncCycleJob orchestrates all data synchronization tasks by running individual sync jobs
// Runs every 5 minutes to keep portfolio, cash, and prices up to date
type SyncCycleJob struct {
	log            zerolog.Logger
	displayManager *display.StateManager
	eventManager   EventManagerInterface
	// Individual sync jobs
	syncTradesJob            Job
	syncCashFlowsJob         Job
	syncPortfolioJob         Job
	syncPricesJob            Job
	checkNegativeBalancesJob Job
	updateDisplayTickerJob   Job
}

// SyncCycleConfig holds configuration for sync cycle job
type SyncCycleConfig struct {
	Log            zerolog.Logger
	DisplayManager *display.StateManager
	EventManager   EventManagerInterface
	// Individual sync jobs
	SyncTradesJob            Job
	SyncCashFlowsJob         Job
	SyncPortfolioJob         Job
	SyncPricesJob            Job
	CheckNegativeBalancesJob Job
	UpdateDisplayTickerJob   Job
}

// NewSyncCycleJob creates a new sync cycle job
func NewSyncCycleJob(cfg SyncCycleConfig) *SyncCycleJob {
	return &SyncCycleJob{
		log:                      cfg.Log.With().Str("job", "sync_cycle").Logger(),
		displayManager:           cfg.DisplayManager,
		eventManager:             cfg.EventManager,
		syncTradesJob:            cfg.SyncTradesJob,
		syncCashFlowsJob:         cfg.SyncCashFlowsJob,
		syncPortfolioJob:         cfg.SyncPortfolioJob,
		syncPricesJob:            cfg.SyncPricesJob,
		checkNegativeBalancesJob: cfg.CheckNegativeBalancesJob,
		updateDisplayTickerJob:   cfg.UpdateDisplayTickerJob,
	}
}

// Name returns the job name
func (j *SyncCycleJob) Name() string {
	return "sync_cycle"
}

// Run executes the sync cycle by orchestrating individual sync jobs
// Note: Concurrent execution is prevented by the scheduler's SkipIfStillRunning wrapper
func (j *SyncCycleJob) Run() error {
	j.log.Info().Msg("Starting sync cycle")
	startTime := time.Now()

	// Set LED to blue (syncing indicator)
	j.setDisplaySyncing()

	// Step 1: Sync trades from Tradernet (non-critical)
	if j.syncTradesJob != nil {
		if err := j.syncTradesJob.Run(); err != nil {
			j.log.Error().Err(err).Msg("Trade sync failed (non-critical)")
			// Continue - non-critical
		}
	}

	// Step 2: Sync cash flows from Tradernet (non-critical)
	if j.syncCashFlowsJob != nil {
		if err := j.syncCashFlowsJob.Run(); err != nil {
			j.log.Error().Err(err).Msg("Cash flow sync failed (non-critical)")
			// Continue - non-critical
		}
	}

	// Step 3: Sync portfolio positions (CRITICAL)
	if j.syncPortfolioJob != nil {
		if err := j.syncPortfolioJob.Run(); err != nil {
			j.log.Error().Err(err).Msg("CRITICAL: Portfolio sync failed")
			j.setDisplayError()
			return fmt.Errorf("portfolio sync failed: %w", err)
		}
	} else {
		j.log.Error().Msg("CRITICAL: Portfolio sync job not available")
		j.setDisplayError()
		return fmt.Errorf("portfolio sync job not available")
	}

	// Step 4: Check for negative balances and trigger emergency rebalance
	if j.checkNegativeBalancesJob != nil {
		if err := j.checkNegativeBalancesJob.Run(); err != nil {
			j.log.Error().Err(err).Msg("Negative balance check failed (non-critical)")
			// Continue - non-critical
		}
	}

	// Step 5: Sync prices for all securities
	if j.syncPricesJob != nil {
		if err := j.syncPricesJob.Run(); err != nil {
			j.log.Error().Err(err).Msg("Price sync failed (non-critical)")
			// Continue - non-critical
		}
	}

	// Step 6: Update LED display ticker
	if j.updateDisplayTickerJob != nil {
		if err := j.updateDisplayTickerJob.Run(); err != nil {
			j.log.Error().Err(err).Msg("Display ticker update failed (non-critical)")
			// Continue - non-critical
		}
	}

	// Clear LED syncing indicator
	j.setDisplayIdle()

	// Emit PortfolioChanged event after successful sync
	if j.eventManager != nil {
		j.eventManager.EmitTyped(events.PortfolioChanged, "sync_cycle", &events.PortfolioChangedData{
			SyncCompleted: true,
		})
	}

	// Emit PriceUpdated event after price sync
	if j.eventManager != nil {
		j.eventManager.EmitTyped(events.PriceUpdated, "sync_cycle", &events.PriceUpdatedData{
			PricesSynced: true,
		})
	}

	duration := time.Since(startTime)
	j.log.Info().
		Dur("duration", duration).
		Msg("Sync cycle completed successfully")

	return nil
}

// setDisplaySyncing sets the LED display to indicate syncing is in progress
// Blue LED = syncing
func (j *SyncCycleJob) setDisplaySyncing() {
	if j.displayManager == nil {
		return
	}
	j.displayManager.SetLED3(0, 0, 255) // Blue
	j.log.Debug().Msg("Display set to syncing (blue)")
}

// setDisplayError sets the LED display to indicate an error occurred
// Red LED = error
func (j *SyncCycleJob) setDisplayError() {
	if j.displayManager == nil {
		return
	}
	j.displayManager.SetLED3(255, 0, 0) // Red
	j.log.Debug().Msg("Display set to error (red)")
}

// setDisplayIdle sets the LED display back to idle state
// LED off = idle
func (j *SyncCycleJob) setDisplayIdle() {
	if j.displayManager == nil {
		return
	}
	j.displayManager.SetLED3(0, 0, 0) // Off
	j.log.Debug().Msg("Display set to idle (off)")
}
