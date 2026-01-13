package di

import (
	"path/filepath"
	"testing"

	"github.com/aristath/sentinel/internal/config"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestInitializeDatabases(t *testing.T) {
	// Create temporary directory for test databases
	tmpDir := t.TempDir()

	cfg := &config.Config{
		DataDir: tmpDir,
	}

	log := zerolog.Nop()

	container, err := InitializeDatabases(cfg, log)
	require.NoError(t, err)
	require.NotNil(t, container)

	// Verify all 7 databases are initialized
	assert.NotNil(t, container.UniverseDB)
	assert.NotNil(t, container.ConfigDB)
	assert.NotNil(t, container.LedgerDB)
	assert.NotNil(t, container.PortfolioDB)
	assert.NotNil(t, container.HistoryDB)
	assert.NotNil(t, container.CacheDB)
	assert.NotNil(t, container.ClientDataDB)

	// Verify database files are created
	assert.FileExists(t, filepath.Join(tmpDir, "universe.db"))
	assert.FileExists(t, filepath.Join(tmpDir, "config.db"))
	assert.FileExists(t, filepath.Join(tmpDir, "ledger.db"))
	assert.FileExists(t, filepath.Join(tmpDir, "portfolio.db"))
	assert.FileExists(t, filepath.Join(tmpDir, "history.db"))
	assert.FileExists(t, filepath.Join(tmpDir, "cache.db"))
	assert.FileExists(t, filepath.Join(tmpDir, "client_data.db"))

	// Cleanup
	container.UniverseDB.Close()
	container.ConfigDB.Close()
	container.LedgerDB.Close()
	container.PortfolioDB.Close()
	container.HistoryDB.Close()
	container.CacheDB.Close()
	container.ClientDataDB.Close()
}

func TestInitializeDatabases_InvalidPath(t *testing.T) {
	cfg := &config.Config{
		DataDir: "/nonexistent/path/that/does/not/exist",
	}

	log := zerolog.Nop()

	container, err := InitializeDatabases(cfg, log)
	assert.Error(t, err)
	assert.Nil(t, container)
}

func TestInitializeDatabases_SchemaMigration(t *testing.T) {
	tmpDir := t.TempDir()

	cfg := &config.Config{
		DataDir: tmpDir,
	}

	log := zerolog.Nop()

	container, err := InitializeDatabases(cfg, log)
	require.NoError(t, err)
	require.NotNil(t, container)

	// Verify schemas are applied by checking that we can query
	// This is a basic smoke test - full schema tests are in database package
	_, err = container.UniverseDB.Conn().Exec("SELECT 1")
	assert.NoError(t, err)

	// Cleanup
	container.UniverseDB.Close()
	container.ConfigDB.Close()
	container.LedgerDB.Close()
	container.PortfolioDB.Close()
	container.HistoryDB.Close()
	container.CacheDB.Close()
	container.ClientDataDB.Close()
}
