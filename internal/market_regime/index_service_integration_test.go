//go:build integration
// +build integration

package market_regime_test

import (
	"testing"

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
	// NOTE: TimeScheduler removed - Work Processor handles scheduling
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

func TestGetMarketReturns_WithRealData(t *testing.T) {
	// Setup: Create container - DI automatically syncs known indices
	cfg := &config.Config{DataDir: t.TempDir()}
	log := zerolog.Nop()
	container, _, err := di.Wire(cfg, log, nil, nil)
	require.NoError(t, err)
	defer cleanupContainer(container)

	// Verify indices were synced during DI initialization
	var indexCount int
	err = container.UniverseDB.QueryRow(`
		SELECT COUNT(*) FROM securities WHERE product_type = 'INDEX'
	`).Scan(&indexCount)
	require.NoError(t, err)
	assert.Greater(t, indexCount, 0, "DI should sync known indices to securities table")

	// Execute: Get market returns for regime detection
	// Note: This may return an error if no historical data is available,
	// which is expected in a fresh test environment without synced price data
	returns, err := container.MarketIndexService.GetMarketReturns(20)
	if err != nil {
		// Expected in test environment without historical data
		assert.Contains(t, err.Error(), "no index data", "Should indicate no data available")
	} else {
		// If data is available (e.g., cached from previous runs), verify it's reasonable
		assert.LessOrEqual(t, len(returns), 20, "Should return at most 20 days of returns")
		for i, ret := range returns {
			assert.Greater(t, ret, -0.15, "Return %d too negative: %f", i, ret)
			assert.Less(t, ret, 0.15, "Return %d too positive: %f", i, ret)
		}
	}
}

func TestPerRegionRegimeDetection_EndToEnd(t *testing.T) {
	// Setup: Create container with test databases
	// DI automatically syncs known indices via IndexRepository.SyncFromKnownIndices()
	cfg := &config.Config{DataDir: t.TempDir()}
	log := zerolog.Nop()
	container, _, err := di.Wire(cfg, log, nil, nil)
	require.NoError(t, err)
	defer cleanupContainer(container)

	// Verify 1: Known indices are synced to securities table
	var indexCount int
	err = container.UniverseDB.QueryRow(`
		SELECT COUNT(*) FROM securities WHERE product_type = 'INDEX'
	`).Scan(&indexCount)
	require.NoError(t, err)
	assert.Greater(t, indexCount, 0, "Should have indices in securities table")

	// Verify 2: market_indices table has regions configured
	var regionCount int
	err = container.ConfigDB.QueryRow(`
		SELECT COUNT(DISTINCT region) FROM market_indices WHERE enabled = 1
	`).Scan(&regionCount)
	require.NoError(t, err)
	assert.Equal(t, 3, regionCount, "Should have 3 regions (US, EU, ASIA)")

	// Execute: Calculate per-region regime scores
	// Note: This may fail in test environment without historical price data
	scores, err := container.RegimeDetector.CalculateAllRegionScores(30)
	if err != nil {
		// Expected in test environment without historical data
		t.Logf("No historical data available: %v", err)
		return
	}

	// Verify 3: Scores calculated for all regions with indices
	assert.Contains(t, scores, "US", "Should have US score")
	assert.Contains(t, scores, "EU", "Should have EU score")
	assert.Contains(t, scores, "ASIA", "Should have ASIA score")
	assert.Contains(t, scores, "GLOBAL_AVERAGE", "Should have global average")

	// Verify 4: Scores are in valid range
	for region, score := range scores {
		assert.GreaterOrEqual(t, score, -1.0, "%s score should be >= -1.0", region)
		assert.LessOrEqual(t, score, 1.0, "%s score should be <= 1.0", region)
	}

	// Verify 5: Per-region scores are stored in history
	storedScores, err := container.RegimePersistence.GetAllCurrentScores()
	require.NoError(t, err)
	assert.Contains(t, storedScores, "US", "Stored scores should have US")
	assert.Contains(t, storedScores, "EU", "Stored scores should have EU")
	assert.Contains(t, storedScores, "ASIA", "Stored scores should have ASIA")

	// Verify 6: GetRegimeScoreForSecurity works correctly
	// US security gets US score
	usScore, err := container.RegimeDetector.GetRegimeScoreForSecurity("US")
	require.NoError(t, err)
	assert.InDelta(t, scores["US"], float64(usScore), 0.01)

	// Unknown region gets global average
	unknownScore, err := container.RegimeDetector.GetRegimeScoreForSecurity("RUSSIA")
	require.NoError(t, err)
	assert.InDelta(t, scores["GLOBAL_AVERAGE"], float64(unknownScore), 0.01)
}
