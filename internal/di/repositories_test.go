package di

import (
	"testing"

	"github.com/aristath/sentinel/internal/config"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestInitializeRepositories(t *testing.T) {
	tmpDir := t.TempDir()
	cfg := &config.Config{DataDir: tmpDir}
	log := zerolog.Nop()

	// Initialize databases first
	container, err := InitializeDatabases(cfg, log)
	require.NoError(t, err)
	require.NotNil(t, container)

	// Initialize repositories
	err = InitializeRepositories(container, log)
	require.NoError(t, err)

	// Verify all repositories are created
	assert.NotNil(t, container.PositionRepo)
	assert.NotNil(t, container.SecurityRepo)
	assert.NotNil(t, container.ScoreRepo)
	assert.NotNil(t, container.DividendRepo)
	assert.NotNil(t, container.CashRepo)
	assert.NotNil(t, container.TradeRepo)
	assert.NotNil(t, container.AllocRepo)
	assert.NotNil(t, container.SettingsRepo)
	assert.NotNil(t, container.CashFlowsRepo)
	assert.NotNil(t, container.RecommendationRepo)
	assert.NotNil(t, container.PlannerConfigRepo)
	assert.NotNil(t, container.GroupingRepo)
	assert.NotNil(t, container.HistoryDBClient)

	// Cleanup
	container.UniverseDB.Close()
	container.ConfigDB.Close()
	container.LedgerDB.Close()
	container.PortfolioDB.Close()
	container.HistoryDB.Close()
	container.CacheDB.Close()
	container.ClientDataDB.Close()
}
