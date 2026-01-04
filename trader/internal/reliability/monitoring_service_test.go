package reliability

import (
	"path/filepath"
	"testing"
	"time"

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

		// Create health tracking table
		_, err = db.Conn().Exec(`
			CREATE TABLE _database_health (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				checked_at INTEGER NOT NULL,
				integrity_check_passed INTEGER NOT NULL,
				size_bytes INTEGER NOT NULL,
				wal_size_bytes INTEGER,
				page_count INTEGER,
				freelist_count INTEGER,
				vacuum_performed INTEGER DEFAULT 0
			)
		`)
		require.NoError(t, err)

		// Insert health record
		_, err = db.Conn().Exec(`
			INSERT INTO _database_health (checked_at, integrity_check_passed, size_bytes, page_count, freelist_count)
			VALUES (?, 1, 100000, 100, 10)
		`, time.Now().Unix())
		require.NoError(t, err)

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

	t.Run("generates alerts for anomalous growth", func(t *testing.T) {
		tempDir := t.TempDir()

		// Create test database
		db, err := database.New(database.Config{
			Path:    filepath.Join(tempDir, "test.db"),
			Profile: database.ProfileStandard,
			Name:    "test",
		})
		require.NoError(t, err)
		defer db.Close()

		// Create health tracking table
		_, err = db.Conn().Exec(`
			CREATE TABLE _database_health (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				checked_at INTEGER NOT NULL,
				integrity_check_passed INTEGER NOT NULL,
				size_bytes INTEGER NOT NULL,
				wal_size_bytes INTEGER,
				page_count INTEGER,
				freelist_count INTEGER,
				vacuum_performed INTEGER DEFAULT 0
			)
		`)
		require.NoError(t, err)

		// Insert old health record (24 hours ago, small size)
		_, err = db.Conn().Exec(`
			INSERT INTO _database_health (checked_at, integrity_check_passed, size_bytes, page_count, freelist_count)
			VALUES (?, 1, 1000, 10, 0)
		`, time.Now().Add(-24*time.Hour).Unix())
		require.NoError(t, err)

		// Insert current health record (large size - 80% growth)
		_, err = db.Conn().Exec(`
			INSERT INTO _database_health (checked_at, integrity_check_passed, size_bytes, page_count, freelist_count)
			VALUES (?, 1, 1800, 180, 0)
		`, time.Now().Unix())
		require.NoError(t, err)

		databases := map[string]*database.DB{"test": db}
		healthServices := map[string]*DatabaseHealthService{
			"test": NewDatabaseHealthService(db, "test", filepath.Join(tempDir, "test.db"), log),
		}

		// Create monitoring service
		monitoringService := NewMonitoringService(databases, healthServices, tempDir, filepath.Join(tempDir, "backups"), log)

		// Check alerts
		err = monitoringService.CheckAlerts()
		require.NoError(t, err)

		// Verify error alert was generated for anomalous growth (> 50%)
		alerts := monitoringService.GetAlerts()
		hasGrowthAlert := false
		for _, alert := range alerts {
			if alert.Component == "test" && alert.Level == AlertError {
				hasGrowthAlert = true
				break
			}
		}
		assert.True(t, hasGrowthAlert, "Should generate error alert for >50% growth")
	})

	t.Run("runs alert checks without error", func(t *testing.T) {
		tempDir := t.TempDir()

		// Create test database
		db, err := database.New(database.Config{
			Path:    filepath.Join(tempDir, "test.db"),
			Profile: database.ProfileStandard,
			Name:    "test",
		})
		require.NoError(t, err)
		defer db.Close()

		// Create health tracking table
		_, err = db.Conn().Exec(`
			CREATE TABLE _database_health (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				checked_at INTEGER NOT NULL,
				integrity_check_passed INTEGER NOT NULL,
				size_bytes INTEGER NOT NULL,
				wal_size_bytes INTEGER,
				page_count INTEGER,
				freelist_count INTEGER,
				vacuum_performed INTEGER DEFAULT 0
			)
		`)
		require.NoError(t, err)

		// Insert health record
		_, err = db.Conn().Exec(`
			INSERT INTO _database_health (checked_at, integrity_check_passed, size_bytes, page_count, freelist_count)
			VALUES (?, 1, 1000000, 1000, 0)
		`, time.Now().Unix())
		require.NoError(t, err)

		databases := map[string]*database.DB{"test": db}
		healthServices := map[string]*DatabaseHealthService{
			"test": NewDatabaseHealthService(db, "test", filepath.Join(tempDir, "test.db"), log),
		}

		// Create monitoring service
		monitoringService := NewMonitoringService(databases, healthServices, tempDir, filepath.Join(tempDir, "backups"), log)

		// Check alerts - should run without error
		err = monitoringService.CheckAlerts()
		assert.NoError(t, err)

		// Should have collected alerts (even if none match specific criteria)
		alerts := monitoringService.GetAlerts()
		assert.NotNil(t, alerts)
	})
}

func TestMonitoringService_HasCriticalAlerts(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	t.Run("detects critical alerts", func(t *testing.T) {
		tempDir := t.TempDir()
		databases := map[string]*database.DB{}
		healthServices := map[string]*DatabaseHealthService{}

		// Create monitoring service
		monitoringService := NewMonitoringService(databases, healthServices, tempDir, filepath.Join(tempDir, "backups"), log)

		// Add a critical alert manually
		monitoringService.addAlert(AlertCritical, "disk", "Test critical alert", map[string]interface{}{})

		// Check for critical alerts
		assert.True(t, monitoringService.HasCriticalAlerts())

		// Get critical alerts
		criticalAlerts := monitoringService.GetCriticalAlerts()
		assert.Len(t, criticalAlerts, 1)
		assert.Equal(t, AlertCritical, criticalAlerts[0].Level)
	})

	t.Run("returns false when no critical alerts", func(t *testing.T) {
		tempDir := t.TempDir()
		databases := map[string]*database.DB{}
		healthServices := map[string]*DatabaseHealthService{}

		// Create monitoring service
		monitoringService := NewMonitoringService(databases, healthServices, tempDir, filepath.Join(tempDir, "backups"), log)

		// Add a warning alert
		monitoringService.addAlert(AlertWarning, "test", "Test warning", map[string]interface{}{})

		// Check for critical alerts
		assert.False(t, monitoringService.HasCriticalAlerts())
	})
}

func TestMonitoringService_CheckConnectionPoolHealth(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	t.Run("monitors connection pool stats", func(t *testing.T) {
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
		healthServices := map[string]*DatabaseHealthService{}

		// Create monitoring service
		monitoringService := NewMonitoringService(databases, healthServices, tempDir, filepath.Join(tempDir, "backups"), log)

		// Check connection pool health
		err = monitoringService.CheckConnectionPoolHealth()
		assert.NoError(t, err)

		// Should not generate alerts for healthy pool
		alerts := monitoringService.GetAlerts()
		assert.Len(t, alerts, 0, "Healthy connection pool should not generate alerts")
	})
}

func TestMonitoringService_AnalyzeDatabaseGrowth(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	t.Run("analyzes long-term growth trends", func(t *testing.T) {
		tempDir := t.TempDir()

		// Create test database
		db, err := database.New(database.Config{
			Path:    filepath.Join(tempDir, "test.db"),
			Profile: database.ProfileStandard,
			Name:    "test",
		})
		require.NoError(t, err)
		defer db.Close()

		// Create health tracking table
		_, err = db.Conn().Exec(`
			CREATE TABLE _database_health (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				checked_at INTEGER NOT NULL,
				integrity_check_passed INTEGER NOT NULL,
				size_bytes INTEGER NOT NULL,
				wal_size_bytes INTEGER,
				page_count INTEGER,
				freelist_count INTEGER,
				vacuum_performed INTEGER DEFAULT 0
			)
		`)
		require.NoError(t, err)

		// Insert historical records (30 days ago)
		_, err = db.Conn().Exec(`
			INSERT INTO _database_health (checked_at, integrity_check_passed, size_bytes, page_count, freelist_count)
			VALUES (?, 1, 1000, 10, 0)
		`, time.Now().AddDate(0, 0, -30).Unix())
		require.NoError(t, err)

		// Insert current record
		_, err = db.Conn().Exec(`
			INSERT INTO _database_health (checked_at, integrity_check_passed, size_bytes, page_count, freelist_count)
			VALUES (?, 1, 1200, 12, 0)
		`, time.Now().Unix())
		require.NoError(t, err)

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

func TestAlert_Levels(t *testing.T) {
	t.Run("alert level constants are correct", func(t *testing.T) {
		assert.Equal(t, AlertLevel("CRITICAL"), AlertCritical)
		assert.Equal(t, AlertLevel("ERROR"), AlertError)
		assert.Equal(t, AlertLevel("WARNING"), AlertWarning)
		assert.Equal(t, AlertLevel("INFO"), AlertInfo)
	})
}
