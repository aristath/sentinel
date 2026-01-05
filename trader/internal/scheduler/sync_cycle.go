package scheduler

import (
	"fmt"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/cash_flows"
	"github.com/aristath/arduino-trader/internal/modules/display"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/trading"
	"github.com/rs/zerolog"
)

// SyncCycleJob orchestrates all data synchronization tasks
// Runs every 5 minutes to keep portfolio, cash, and prices up to date
type SyncCycleJob struct {
	log                 zerolog.Logger
	portfolioService    *portfolio.PortfolioService
	cashFlowsService    *cash_flows.CashFlowsService
	tradingService      *trading.TradingService
	universeService     UniverseServiceInterface
	balanceService      BalanceServiceInterface
	displayManager      *display.StateManager
	emergencyRebalance  func() error // Callback for emergency rebalance
	updateDisplayTicker func() error // Callback for display ticker update
}

// SyncCycleConfig holds configuration for sync cycle job
type SyncCycleConfig struct {
	Log                 zerolog.Logger
	PortfolioService    *portfolio.PortfolioService
	CashFlowsService    *cash_flows.CashFlowsService
	TradingService      *trading.TradingService
	UniverseService     UniverseServiceInterface
	BalanceService      BalanceServiceInterface
	DisplayManager      *display.StateManager
	EmergencyRebalance  func() error
	UpdateDisplayTicker func() error
}

// NewSyncCycleJob creates a new sync cycle job
func NewSyncCycleJob(cfg SyncCycleConfig) *SyncCycleJob {
	return &SyncCycleJob{
		log:                 cfg.Log.With().Str("job", "sync_cycle").Logger(),
		portfolioService:    cfg.PortfolioService,
		cashFlowsService:    cfg.CashFlowsService,
		tradingService:      cfg.TradingService,
		universeService:     cfg.UniverseService,
		balanceService:      cfg.BalanceService,
		displayManager:      cfg.DisplayManager,
		emergencyRebalance:  cfg.EmergencyRebalance,
		updateDisplayTicker: cfg.UpdateDisplayTicker,
	}
}

// Name returns the job name
func (j *SyncCycleJob) Name() string {
	return "sync_cycle"
}

// Run executes the sync cycle
// Note: Concurrent execution is prevented by the scheduler's SkipIfStillRunning wrapper
func (j *SyncCycleJob) Run() error {
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

	// Step 5: Sync prices for all securities
	j.syncPrices()

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
		return fmt.Errorf("portfolio sync from Tradernet failed: %w", err)
	}

	j.log.Debug().Msg("Portfolio sync completed")
	return nil
}

// checkNegativeBalances checks for negative cash balances
// Triggers emergency rebalance if needed
func (j *SyncCycleJob) checkNegativeBalances() {
	j.log.Debug().Msg("Checking for negative balances")

	if j.balanceService == nil {
		j.log.Warn().Msg("Balance service not available, skipping negative balance check")
		return
	}

	// Get all currencies that have balances
	currencies, err := j.balanceService.GetAllCurrencies()
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to get currencies for negative balance check")
		return
	}

	// Check each currency for negative balance
	hasNegativeBalance := false
	for _, currency := range currencies {
		total, err := j.balanceService.GetTotalByCurrency(currency)
		if err != nil {
			j.log.Error().
				Err(err).
				Str("currency", currency).
				Msg("Failed to get total balance for currency")
			continue
		}

		if total < 0 {
			hasNegativeBalance = true
			j.log.Error().
				Str("currency", currency).
				Float64("balance", total).
				Msg("CRITICAL: Negative cash balance detected")
		}
	}

	// Trigger emergency rebalance if negative balance detected
	if hasNegativeBalance {
		j.log.Error().Msg("CRITICAL: Negative balance detected, triggering emergency rebalance")

		if j.emergencyRebalance != nil {
			if err := j.emergencyRebalance(); err != nil {
				j.log.Error().Err(err).Msg("Emergency rebalance failed")
			} else {
				j.log.Info().Msg("Emergency rebalance completed successfully")
			}
		} else {
			j.log.Error().Msg("Emergency rebalance callback not configured")
		}
	}
}

// syncPrices synchronizes prices for all securities
func (j *SyncCycleJob) syncPrices() {
	j.log.Debug().Msg("Syncing prices for all securities")

	if j.universeService == nil {
		j.log.Warn().Msg("Universe service not available, skipping price sync")
		return
	}

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
