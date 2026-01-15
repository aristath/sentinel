package di

import (
	"testing"
	"time"

	"github.com/aristath/sentinel/internal/config"
	"github.com/aristath/sentinel/internal/modules/display"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestWire(t *testing.T) {
	tmpDir := t.TempDir()
	cfg := &config.Config{
		DataDir:            tmpDir,
		TradernetAPIKey:    "test-key",
		TradernetAPISecret: "test-secret",
	}
	log := zerolog.Nop()

	// Create display manager
	displayManager := display.NewStateManager(log)

	// Wire everything (pass nil for deployment manager in tests)
	container, jobs, err := Wire(cfg, log, displayManager, nil)
	require.NoError(t, err)
	require.NotNil(t, container)
	require.NotNil(t, jobs)

	// Verify container is fully populated
	assert.NotNil(t, container.UniverseDB)
	assert.NotNil(t, container.PortfolioService)
	assert.NotNil(t, container.TradingService)
	assert.NotNil(t, container.CashManager)

	// Verify jobs are registered
	// NOTE: Composite jobs (SyncCycle, PlannerBatch) removed - work processor handles orchestration
	assert.NotNil(t, jobs.HealthCheck)
	assert.NotNil(t, jobs.DividendReinvest)

	// Cleanup - stop background services first
	t.Cleanup(func() {
		if container != nil {
			// Stop background services first to prevent temp directory cleanup issues
			if container.WorkerPool != nil {
				container.WorkerPool.Stop()
			}
			// NOTE: TimeScheduler removed - Work Processor handles scheduling
			// Give goroutines time to stop before closing databases
			time.Sleep(50 * time.Millisecond)

			// Close databases
			container.UniverseDB.Close()
			container.ConfigDB.Close()
			container.LedgerDB.Close()
			container.PortfolioDB.Close()
			container.HistoryDB.Close()
			container.CacheDB.Close()
			container.ClientDataDB.Close()
		}
	})
}
