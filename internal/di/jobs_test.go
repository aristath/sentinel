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

func TestRegisterJobs(t *testing.T) {
	tmpDir := t.TempDir()
	cfg := &config.Config{
		DataDir:            tmpDir,
		TradernetAPIKey:    "test-key",
		TradernetAPISecret: "test-secret",
	}
	log := zerolog.Nop()

	// Initialize everything first
	container, err := InitializeDatabases(cfg, log)
	require.NoError(t, err)

	// Ensure databases are closed before temp directory cleanup
	t.Cleanup(func() {
		if container != nil {
			// Stop background services first to prevent temp directory cleanup issues
			if container.WorkerPool != nil {
				container.WorkerPool.Stop()
			}
			if container.TimeScheduler != nil {
				container.TimeScheduler.Stop()
			}
			// Give goroutines time to stop before closing databases
			// This prevents "directory not empty" errors during temp cleanup
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

	err = InitializeRepositories(container, log)
	require.NoError(t, err)

	displayManager := display.NewStateManager(log)

	err = InitializeServices(container, cfg, displayManager, log)
	require.NoError(t, err)

	// Register jobs (pass nil for deployment manager in tests)
	jobInstances, err := RegisterJobs(container, cfg, displayManager, nil, log)
	require.NoError(t, err)
	require.NotNil(t, jobInstances)

	// Verify all jobs are registered
	assert.NotNil(t, jobInstances.HealthCheck)
	assert.NotNil(t, jobInstances.SyncCycle)
	assert.NotNil(t, jobInstances.DividendReinvest)
	assert.NotNil(t, jobInstances.PlannerBatch)
	assert.NotNil(t, jobInstances.EventBasedTrading)
	assert.NotNil(t, jobInstances.TagUpdate)
	assert.NotNil(t, jobInstances.HistoryCleanup)
	assert.NotNil(t, jobInstances.HourlyBackup)
	assert.NotNil(t, jobInstances.DailyBackup)
	assert.NotNil(t, jobInstances.DailyMaintenance)
	assert.NotNil(t, jobInstances.WeeklyBackup)
	assert.NotNil(t, jobInstances.WeeklyMaintenance)
	assert.NotNil(t, jobInstances.MonthlyBackup)
	assert.NotNil(t, jobInstances.MonthlyMaintenance)
	assert.NotNil(t, jobInstances.FormulaDiscovery)
	assert.NotNil(t, jobInstances.AdaptiveMarketJob)
}
