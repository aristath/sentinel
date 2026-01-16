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

func TestInitializeServices(t *testing.T) {
	tmpDir := t.TempDir()
	cfg := &config.Config{
		DataDir:            tmpDir,
		TradernetAPIKey:    "test-key",
		TradernetAPISecret: "test-secret",
	}
	log := zerolog.Nop()

	// Initialize databases and repositories first
	container, err := InitializeDatabases(cfg, log)
	require.NoError(t, err)
	require.NotNil(t, container)

	err = InitializeRepositories(container, log)
	require.NoError(t, err)

	// Initialize display manager (needed for services)
	displayManager := display.NewStateManager(log)

	// Initialize services
	err = InitializeServices(container, cfg, displayManager, log)
	require.NoError(t, err)

	// Verify core services are created
	assert.NotNil(t, container.BrokerClient)
	assert.NotNil(t, container.CurrencyExchangeService)
	assert.NotNil(t, container.CashManager)
	assert.NotNil(t, container.TradeSafetyService)
	assert.NotNil(t, container.TradingService)
	assert.NotNil(t, container.PortfolioService)
	assert.NotNil(t, container.CashFlowsService)
	assert.NotNil(t, container.UniverseService)
	assert.NotNil(t, container.TagAssigner)
	assert.NotNil(t, container.TradeExecutionService)
	assert.NotNil(t, container.SettingsService)
	assert.NotNil(t, container.MarketHoursService)
	assert.NotNil(t, container.EventManager)
	assert.NotNil(t, container.TickerContentService)

	// Cleanup
	t.Cleanup(func() {
		// Stop WebSocket client if running
		if container.MarketStatusWS != nil {
			_ = container.MarketStatusWS.Stop()
		}

		// Give goroutines time to stop before closing databases
		time.Sleep(100 * time.Millisecond)

		container.UniverseDB.Close()
		container.ConfigDB.Close()
		container.LedgerDB.Close()
		container.PortfolioDB.Close()
		container.HistoryDB.Close()
		container.CacheDB.Close()
		container.ClientDataDB.Close()
	})
}

func TestInitializeServices_DependencyOrder(t *testing.T) {
	// This test verifies that services are created in the correct dependency order
	// Services that depend on other services should be created after their dependencies
	tmpDir := t.TempDir()
	cfg := &config.Config{
		DataDir:            tmpDir,
		TradernetAPIKey:    "test-key",
		TradernetAPISecret: "test-secret",
	}
	log := zerolog.Nop()

	container, err := InitializeDatabases(cfg, log)
	require.NoError(t, err)

	err = InitializeRepositories(container, log)
	require.NoError(t, err)

	displayManager := display.NewStateManager(log)

	// This should not panic or error due to dependency order
	err = InitializeServices(container, cfg, displayManager, log)
	require.NoError(t, err)

	// Verify that dependent services exist
	// PortfolioService depends on CashManager, so CashManager should exist
	assert.NotNil(t, container.CashManager)
	assert.NotNil(t, container.PortfolioService)

	// Cleanup
	t.Cleanup(func() {
		// Stop WebSocket client if running
		if container.MarketStatusWS != nil {
			_ = container.MarketStatusWS.Stop()
		}

		// Give goroutines time to stop before closing databases
		time.Sleep(100 * time.Millisecond)

		container.UniverseDB.Close()
		container.ConfigDB.Close()
		container.LedgerDB.Close()
		container.PortfolioDB.Close()
		container.HistoryDB.Close()
		container.CacheDB.Close()
		container.ClientDataDB.Close()
	})
}
