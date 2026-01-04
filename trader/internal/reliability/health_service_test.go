package reliability

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/aristath/arduino-trader/internal/database"
	"github.com/aristath/arduino-trader/pkg/logger"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestDatabaseHealthService_CheckAndRecover(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	t.Run("healthy database passes all checks", func(t *testing.T) {
		// Create test database
		tempDir := t.TempDir()
		dbPath := filepath.Join(tempDir, "test.db")

		db, err := database.New(database.Config{
			Path:    dbPath,
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
				freelist_count INTEGER
			)
		`)
		require.NoError(t, err)

		// Create health service
		healthService := NewDatabaseHealthService(db, "test", dbPath, log)

		// Run health check
		err = healthService.CheckAndRecover()
		assert.NoError(t, err)

		// Verify health record was created
		var count int
		err = db.Conn().QueryRow("SELECT COUNT(*) FROM _database_health").Scan(&count)
		require.NoError(t, err)
		assert.Equal(t, 1, count)
	})

	t.Run("detects and records anomalous growth", func(t *testing.T) {
		// Create test database
		tempDir := t.TempDir()
		dbPath := filepath.Join(tempDir, "test.db")

		db, err := database.New(database.Config{
			Path:    dbPath,
			Profile: database.ProfileStandard,
			Name:    "test",
		})
		require.NoError(t, err)
		defer db.Close()

		// Create health tracking table with historical data
		_, err = db.Conn().Exec(`
			CREATE TABLE _database_health (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				checked_at INTEGER NOT NULL,
				integrity_check_passed INTEGER NOT NULL,
				size_bytes INTEGER NOT NULL,
				wal_size_bytes INTEGER,
				page_count INTEGER,
				freelist_count INTEGER
			)
		`)
		require.NoError(t, err)

		// Insert old health record with small size
		_, err = db.Conn().Exec(`
			INSERT INTO _database_health (checked_at, integrity_check_passed, size_bytes, page_count, freelist_count)
			VALUES (?, 1, 1000, 10, 0)
		`, time.Now().Unix()-3600)
		require.NoError(t, err)

		// Create health service
		healthService := NewDatabaseHealthService(db, "test", dbPath, log)

		// Run health check - should detect growth but not fail
		err = healthService.CheckAndRecover()
		assert.NoError(t, err)
	})
}

func TestDatabaseHealthService_GetMetrics(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	t.Run("returns current database metrics", func(t *testing.T) {
		// Create test database
		tempDir := t.TempDir()
		dbPath := filepath.Join(tempDir, "test.db")

		db, err := database.New(database.Config{
			Path:    dbPath,
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

		// Create health service
		healthService := NewDatabaseHealthService(db, "test", dbPath, log)

		// Get metrics
		metrics, err := healthService.GetMetrics()
		require.NoError(t, err)

		// Verify metrics
		assert.Equal(t, "test", metrics.Name)
		assert.True(t, metrics.SizeMB > 0)
		assert.True(t, metrics.IntegrityCheckPassed)
		assert.False(t, metrics.LastIntegrityCheck.IsZero())
	})
}

func TestDatabaseHealthService_RecordHealthMetrics(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	t.Run("records health metrics correctly", func(t *testing.T) {
		// Create test database
		tempDir := t.TempDir()
		dbPath := filepath.Join(tempDir, "test.db")

		db, err := database.New(database.Config{
			Path:    dbPath,
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
				freelist_count INTEGER
			)
		`)
		require.NoError(t, err)

		// Create health service
		healthService := NewDatabaseHealthService(db, "test", dbPath, log)

		// Record metrics
		err = healthService.recordHealthMetrics(true)
		require.NoError(t, err)

		// Verify record was created
		var count int
		err = db.Conn().QueryRow("SELECT COUNT(*) FROM _database_health").Scan(&count)
		require.NoError(t, err)
		assert.Equal(t, 1, count)

		// Verify fields
		var passed, sizeBytes int
		err = db.Conn().QueryRow(`
			SELECT integrity_check_passed, size_bytes
			FROM _database_health
			ORDER BY id DESC
			LIMIT 1
		`).Scan(&passed, &sizeBytes)
		require.NoError(t, err)
		assert.Equal(t, 1, passed)
		assert.True(t, sizeBytes > 0)
	})
}

func TestCopyFile(t *testing.T) {
	t.Run("copies file successfully", func(t *testing.T) {
		tempDir := t.TempDir()

		// Create source file
		srcPath := filepath.Join(tempDir, "source.txt")
		content := []byte("test content")
		err := os.WriteFile(srcPath, content, 0644)
		require.NoError(t, err)

		// Copy file
		dstPath := filepath.Join(tempDir, "dest.txt")
		err = CopyFile(srcPath, dstPath)
		require.NoError(t, err)

		// Verify copy
		copiedContent, err := os.ReadFile(dstPath)
		require.NoError(t, err)
		assert.Equal(t, content, copiedContent)
	})

	t.Run("returns error for non-existent source", func(t *testing.T) {
		tempDir := t.TempDir()
		srcPath := filepath.Join(tempDir, "nonexistent.txt")
		dstPath := filepath.Join(tempDir, "dest.txt")

		err := CopyFile(srcPath, dstPath)
		assert.Error(t, err)
	})
}
