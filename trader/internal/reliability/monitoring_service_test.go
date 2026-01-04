package reliability

import (
	"path/filepath"
	"testing"

	"github.com/aristath/arduino-trader/internal/database"
	"github.com/aristath/arduino-trader/pkg/logger"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestMonitoringService_CollectMetrics(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	t.Run("collects metrics from all databases", func(t *testing.T) {
		tempDir := t.TempDir()

		// Create test database
		db, err := database.New(database.Config{
			Path:    filepath.Join(tempDir, "test.db"),
			Profile: database.ProfileStandard,
			Name:    "test",
		})
		require.NoError(t, err)
		defer db.Close()

		databases := map[string]*database.DB{"test": db}
		healthServices := map[string]*DatabaseHealthService{
			"test": NewDatabaseHealthService(db, "test", filepath.Join(tempDir, "test.db"), log),
		}

		// Create monitoring service
		monitoringService := NewMonitoringService(databases, healthServices, tempDir, filepath.Join(tempDir, "backups"), log)

		// Collect metrics
		metrics, err := monitoringService.CollectMetrics()
		require.NoError(t, err)

		// Verify metrics collected
		assert.Len(t, metrics, 1)
		assert.Contains(t, metrics, "test")
		assert.True(t, metrics["test"].IntegrityCheckPassed)
	})
}

func TestMonitoringService_CheckAlerts(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	t.Run("checks disk space and generates alerts", func(t *testing.T) {
		tempDir := t.TempDir()

		// Create test database
		db, err := database.New(database.Config{
			Path:    filepath.Join(tempDir, "test.db"),
			Profile: database.ProfileStandard,
			Name:    "test",
		})
		require.NoError(t, err)
		defer db.Close()

		databases := map[string]*database.DB{"test": db}
		healthServices := map[string]*DatabaseHealthService{
			"test": NewDatabaseHealthService(db, "test", filepath.Join(tempDir, "test.db"), log),
		}

		// Create monitoring service
		monitoringService := NewMonitoringService(databases, healthServices, tempDir, filepath.Join(tempDir, "backups"), log)

		// Check alerts
		err = monitoringService.CheckAlerts()
		assert.NoError(t, err)

		// Should have no critical alerts on a clean system
		alerts := monitoringService.GetAlerts()
		for _, alert := range alerts {
			assert.NotEqual(t, AlertCritical, alert.Level, "Should not have critical alerts on clean system")
		}
	})
}

func TestMonitoringService_AnalyzeDatabaseGrowth(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	t.Run("analyzes database sizes", func(t *testing.T) {
		tempDir := t.TempDir()

		// Create test database
		db, err := database.New(database.Config{
			Path:    filepath.Join(tempDir, "test.db"),
			Profile: database.ProfileStandard,
			Name:    "test",
		})
		require.NoError(t, err)
		defer db.Close()

		databases := map[string]*database.DB{"test": db}
		healthServices := map[string]*DatabaseHealthService{
			"test": NewDatabaseHealthService(db, "test", filepath.Join(tempDir, "test.db"), log),
		}

		// Create monitoring service
		monitoringService := NewMonitoringService(databases, healthServices, tempDir, filepath.Join(tempDir, "backups"), log)

		// Analyze growth
		err = monitoringService.AnalyzeDatabaseGrowth()
		assert.NoError(t, err)
	})
}
