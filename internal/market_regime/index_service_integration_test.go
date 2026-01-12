package market_regime_test

import (
	"testing"
	"time"

	"github.com/aristath/sentinel/internal/clients/tradernet"
	"github.com/aristath/sentinel/internal/config"
	"github.com/aristath/sentinel/internal/di"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// cleanupContainer properly shuts down all container resources
func cleanupContainer(container *di.Container) {
	// Stop background services first
	if container.TimeScheduler != nil {
		container.TimeScheduler.Stop()
	}
	if container.WorkerPool != nil {
		container.WorkerPool.Stop()
	}
	if container.MarketStatusWS != nil {
		container.MarketStatusWS.Stop()
	}
	// Close broker client (which closes SDK client's rate limiter worker)
	if adapter, ok := container.BrokerClient.(*tradernet.TradernetBrokerAdapter); ok {
		adapter.Close()
	}

	// Close all databases
	if container.UniverseDB != nil {
		container.UniverseDB.Close()
	}
	if container.ConfigDB != nil {
		container.ConfigDB.Close()
	}
	if container.LedgerDB != nil {
		container.LedgerDB.Close()
	}
	if container.PortfolioDB != nil {
		container.PortfolioDB.Close()
	}
	if container.AgentsDB != nil {
		container.AgentsDB.Close()
	}
	if container.HistoryDB != nil {
		container.HistoryDB.Close()
	}
	if container.CacheDB != nil {
		container.CacheDB.Close()
	}
	if container.ClientDataDB != nil {
		container.ClientDataDB.Close()
	}
}

func TestInitializeMarketIndices_EndToEnd(t *testing.T) {
	// Setup: Create container with test databases
	cfg := &config.Config{DataDir: t.TempDir()}
	log := zerolog.Nop()
	container, _, err := di.Wire(cfg, log, nil, nil)
	require.NoError(t, err)
	defer cleanupContainer(container)

	// Execute: Initialize market indices
	err = container.MarketIndexService.InitializeMarketIndices(container.HistoricalSyncService)
	require.NoError(t, err)

	// Verify 1: Indices exist in securities table
	var indexCount int
	err = container.UniverseDB.QueryRow(`
		SELECT COUNT(*) FROM securities WHERE product_type = 'INDEX'
	`).Scan(&indexCount)
	require.NoError(t, err)
	assert.Equal(t, 3, indexCount, "Should create 3 market indices")

	// Verify 2: Yahoo symbols set in securities table
	var mappingCount int
	err = container.UniverseDB.QueryRow(`
		SELECT COUNT(*) FROM securities
		WHERE product_type = 'INDEX' AND yahoo_symbol IS NOT NULL
	`).Scan(&mappingCount)
	require.NoError(t, err)
	assert.Equal(t, 3, mappingCount, "Should set Yahoo symbols for all 3 indices")

	// Verify 3: Historical data populated (at least some data for each index)
	rows, err := container.HistoryDB.Query(`
		SELECT isin, COUNT(*) as record_count
		FROM daily_prices
		WHERE isin LIKE 'INDEX-%'
		GROUP BY isin
	`)
	require.NoError(t, err)
	defer rows.Close()

	indexDataCount := 0
	for rows.Next() {
		var isin string
		var recordCount int
		require.NoError(t, rows.Scan(&isin, &recordCount))
		assert.Greater(t, recordCount, 100, "Index %s should have historical data", isin)
		indexDataCount++
	}
	assert.Equal(t, 3, indexDataCount, "All 3 indices should have price data")

	// Verify 4: Idempotent - can call again without errors
	err = container.MarketIndexService.InitializeMarketIndices(container.HistoricalSyncService)
	assert.NoError(t, err, "Should be idempotent")
}

func TestGetMarketReturns_WithRealData(t *testing.T) {
	// Setup: Initialize indices with real data
	cfg := &config.Config{DataDir: t.TempDir()}
	log := zerolog.Nop()
	container, _, err := di.Wire(cfg, log, nil, nil)
	require.NoError(t, err)
	defer cleanupContainer(container)

	err = container.MarketIndexService.InitializeMarketIndices(container.HistoricalSyncService)
	require.NoError(t, err)

	// Execute: Get market returns for regime detection
	returns, err := container.MarketIndexService.GetMarketReturns(20)

	// Verify: Should return 20 days of composite returns
	require.NoError(t, err)
	assert.Len(t, returns, 20, "Should return 20 days of returns")

	// Verify: Returns should be reasonable (daily returns typically < 15%)
	for i, ret := range returns {
		assert.Greater(t, ret, -0.15, "Return %d too negative: %f", i, ret)
		assert.Less(t, ret, 0.15, "Return %d too positive: %f", i, ret)
	}
}

func TestInitializeMarketIndices_SkipsWhenDataExists(t *testing.T) {
	// Setup: Create container and initialize once
	cfg := &config.Config{DataDir: t.TempDir()}
	log := zerolog.Nop()
	container, _, err := di.Wire(cfg, log, nil, nil)
	require.NoError(t, err)
	defer cleanupContainer(container)

	// First initialization
	err = container.MarketIndexService.InitializeMarketIndices(container.HistoricalSyncService)
	require.NoError(t, err)

	// Get initial record counts
	var initialCount int
	err = container.HistoryDB.QueryRow(`
		SELECT COUNT(*) FROM daily_prices WHERE isin LIKE 'INDEX-%'
	`).Scan(&initialCount)
	require.NoError(t, err)

	// Wait a moment to ensure timestamps would differ if data was refetched
	time.Sleep(100 * time.Millisecond)

	// Second initialization (should skip fetching since data is recent)
	err = container.MarketIndexService.InitializeMarketIndices(container.HistoricalSyncService)
	require.NoError(t, err)

	// Verify record count unchanged (no duplicate fetch)
	var finalCount int
	err = container.HistoryDB.QueryRow(`
		SELECT COUNT(*) FROM daily_prices WHERE isin LIKE 'INDEX-%'
	`).Scan(&finalCount)
	require.NoError(t, err)

	assert.Equal(t, initialCount, finalCount, "Should not refetch data when recent data exists")
}
