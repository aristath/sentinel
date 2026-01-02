package scheduler

import (
	"fmt"
	"time"

	"github.com/aristath/arduino-trader/internal/locking"
	"github.com/aristath/arduino-trader/internal/modules/cash_flows"
	"github.com/aristath/arduino-trader/internal/modules/display"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/trading"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/rs/zerolog"
)

// SyncCycleJob orchestrates all data synchronization tasks
// Runs every 5 minutes to keep portfolio, cash, and prices up to date
type SyncCycleJob struct {
	log                 zerolog.Logger
	lockManager         *locking.Manager
	portfolioService    *portfolio.PortfolioService
	cashFlowsService    *cash_flows.CashFlowsService
	tradingService      *trading.TradingService
	universeService     *universe.UniverseService
	displayManager      *display.StateManager
	marketHours         *MarketHoursService
	emergencyRebalance  func() error // Callback for emergency rebalance
	updateDisplayTicker func() error // Callback for display ticker update
}

// SyncCycleConfig holds configuration for sync cycle job
type SyncCycleConfig struct {
	Log                 zerolog.Logger
	LockManager         *locking.Manager
	PortfolioService    *portfolio.PortfolioService
	CashFlowsService    *cash_flows.CashFlowsService
	TradingService      *trading.TradingService
	UniverseService     *universe.UniverseService
	DisplayManager      *display.StateManager
	MarketHours         *MarketHoursService
	EmergencyRebalance  func() error
	UpdateDisplayTicker func() error
}

// NewSyncCycleJob creates a new sync cycle job
func NewSyncCycleJob(cfg SyncCycleConfig) *SyncCycleJob {
	return &SyncCycleJob{
		log:                 cfg.Log.With().Str("job", "sync_cycle").Logger(),
		lockManager:         cfg.LockManager,
		portfolioService:    cfg.PortfolioService,
		cashFlowsService:    cfg.CashFlowsService,
		tradingService:      cfg.TradingService,
		universeService:     cfg.UniverseService,
		displayManager:      cfg.DisplayManager,
		marketHours:         cfg.MarketHours,
		emergencyRebalance:  cfg.EmergencyRebalance,
		updateDisplayTicker: cfg.UpdateDisplayTicker,
	}
}

// Name returns the job name
func (j *SyncCycleJob) Name() string {
	return "sync_cycle"
}

// Run executes the sync cycle
func (j *SyncCycleJob) Run() error {
	// Acquire lock to prevent concurrent execution
	if err := j.lockManager.Acquire("sync_cycle"); err != nil {
		j.log.Warn().Err(err).Msg("Sync cycle already running")
		return nil // Don't fail, just skip this cycle
	}
	defer j.lockManager.Release("sync_cycle")

	j.log.Info().Msg("Starting sync cycle")
	startTime := time.Now()

	// Set LED to blue (syncing indicator)
	j.setDisplaySyncing()

	// Step 1: Sync trades from Tradernet (non-critical)
	j.syncTrades()

	// Step 2: Sync cash flows from Tradernet (non-critical)
	j.syncCashFlows()

	// Step 3: Sync portfolio positions (CRITICAL)
	if err := j.syncPortfolio(); err != nil {
		j.log.Error().Err(err).Msg("CRITICAL: Portfolio sync failed")
		j.setDisplayError()
		return fmt.Errorf("portfolio sync failed: %w", err)
	}

	// Step 4: Check for negative balances and trigger emergency rebalance
	j.checkNegativeBalances()

	// Step 5: Sync prices for open markets (market-aware)
	j.syncPricesForOpenMarkets()

	// Step 6: Update LED display ticker
	j.updateTicker()

	// Clear LED syncing indicator
	j.setDisplayIdle()

	duration := time.Since(startTime)
	j.log.Info().
		Dur("duration", duration).
		Msg("Sync cycle completed successfully")

	return nil
}

// syncTrades synchronizes trade history from Tradernet
// Non-critical - errors are logged but don't stop the cycle
func (j *SyncCycleJob) syncTrades() {
	j.log.Debug().Msg("Syncing trades")

	if j.tradingService == nil {
		j.log.Warn().Msg("Trading service not available, skipping trade sync")
		return
	}

	if err := j.tradingService.SyncFromTradernet(); err != nil {
		j.log.Error().Err(err).Msg("Trade sync failed")
		// Continue - non-critical
	} else {
		j.log.Debug().Msg("Trade sync completed")
	}
}

// syncCashFlows synchronizes cash flow history from Tradernet
// Non-critical - errors are logged but don't stop the cycle
func (j *SyncCycleJob) syncCashFlows() {
	j.log.Debug().Msg("Syncing cash flows")

	if j.cashFlowsService == nil {
		j.log.Warn().Msg("Cash flows service not available, skipping cash flow sync")
		return
	}

	if err := j.cashFlowsService.SyncFromTradernet(); err != nil {
		j.log.Error().Err(err).Msg("Cash flow sync failed")
		// Continue - non-critical
	} else {
		j.log.Debug().Msg("Cash flow sync completed")
	}
}

// syncPortfolio synchronizes portfolio positions from Tradernet
// CRITICAL - errors are returned and stop the cycle
func (j *SyncCycleJob) syncPortfolio() error {
	j.log.Debug().Msg("Syncing portfolio (CRITICAL)")

	if j.portfolioService == nil {
		return fmt.Errorf("portfolio service not available")
	}

	if err := j.portfolioService.SyncFromTradernet(); err != nil {
		return fmt.Errorf("portfolio sync failed: %w", err)
	}

	j.log.Debug().Msg("Portfolio sync completed")
	return nil
}

// checkNegativeBalances checks for negative cash balances
// Triggers emergency rebalance if needed
func (j *SyncCycleJob) checkNegativeBalances() {
	j.log.Debug().Msg("Checking for negative balances")

	// This functionality requires:
	// 1. Get current cash balance for each currency
	// 2. Check if any balance is negative
	// 3. If negative, trigger emergency rebalance
	// Full implementation will depend on cash flows module

	if j.emergencyRebalance != nil {
		// Placeholder - in production this would:
		// 1. Check if any currency has negative balance
		// 2. If yes, call emergencyRebalance()
		// For now, we skip this check
		j.log.Debug().Msg("Negative balance check not yet implemented")
	}
}

// syncPricesForOpenMarkets synchronizes prices for securities in currently open markets
// Market-aware - only fetches prices during market hours
func (j *SyncCycleJob) syncPricesForOpenMarkets() {
	j.log.Debug().Msg("Syncing prices for open markets")

	if j.universeService == nil {
		j.log.Warn().Msg("Universe service not available, skipping price sync")
		return
	}

	if j.marketHours == nil {
		j.log.Warn().Msg("Market hours service not available, skipping price sync")
		return
	}

	// Get all securities grouped by exchange
	// For each exchange, check if market is open
	// Only sync prices for securities on open markets

	// Simplified version - sync all prices
	// Full implementation would:
	// 1. Get securities by exchange
	// 2. Check IsMarketOpen() for each exchange
	// 3. Only sync prices for securities on open exchanges

	if err := j.universeService.SyncPrices(); err != nil {
		j.log.Error().Err(err).Msg("Price sync failed")
		// Continue - non-critical
	} else {
		j.log.Debug().Msg("Price sync completed")
	}
}

// updateTicker updates the LED display ticker
func (j *SyncCycleJob) updateTicker() {
	j.log.Debug().Msg("Updating display ticker")

	if j.updateDisplayTicker != nil {
		if err := j.updateDisplayTicker(); err != nil {
			j.log.Error().Err(err).Msg("Failed to update display ticker")
			// Continue - non-critical
		}
	} else {
		j.log.Debug().Msg("Display ticker update not configured")
	}
}

// setDisplaySyncing sets the LED display to indicate syncing is in progress
// Blue LED = syncing
func (j *SyncCycleJob) setDisplaySyncing() {
	if j.displayManager == nil {
		return
	}

	// Set LED 3 to blue (syncing indicator)
	j.displayManager.SetLED3(0, 0, 255) // Blue
	j.log.Debug().Msg("Display set to syncing (blue)")
}

// setDisplayError sets the LED display to indicate an error occurred
// Red LED = error
func (j *SyncCycleJob) setDisplayError() {
	if j.displayManager == nil {
		return
	}

	// Set LED 3 to red (error indicator)
	j.displayManager.SetLED3(255, 0, 0) // Red
	j.log.Debug().Msg("Display set to error (red)")
}

// setDisplayIdle sets the LED display back to idle state
// LED off = idle
func (j *SyncCycleJob) setDisplayIdle() {
	if j.displayManager == nil {
		return
	}

	// Turn off LED 3 (idle state)
	j.displayManager.SetLED3(0, 0, 0) // Off
	j.log.Debug().Msg("Display set to idle (off)")
}
