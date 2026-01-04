package reliability

import (
	"database/sql"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/aristath/arduino-trader/internal/database"
	"github.com/aristath/arduino-trader/pkg/logger"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	_ "modernc.org/sqlite" // SQLite driver
)

func TestBackupService_HourlyBackup(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	t.Run("creates hourly backup for ledger database", func(t *testing.T) {
		tempDir := t.TempDir()
		dataDir := filepath.Join(tempDir, "data")
		backupDir := filepath.Join(tempDir, "backups")
		require.NoError(t, os.MkdirAll(dataDir, 0755))

		// Create ledger database
		ledgerDB, err := database.New(database.Config{
			Path:    filepath.Join(dataDir, "ledger.db"),
			Profile: database.ProfileLedger,
			Name:    "ledger",
		})
		require.NoError(t, err)
		defer ledgerDB.Close()

		// Create test table with data
		_, err = ledgerDB.Conn().Exec("CREATE TABLE trades (id INTEGER PRIMARY KEY, symbol TEXT)")
		require.NoError(t, err)
		_, err = ledgerDB.Conn().Exec("INSERT INTO trades (symbol) VALUES ('AAPL'), ('GOOGL')")
		require.NoError(t, err)

		databases := map[string]*database.DB{
			"ledger": ledgerDB,
		}

		// Create backup service
		backupService := NewBackupService(databases, dataDir, backupDir, log)

		// Run hourly backup
		err = backupService.HourlyBackup()
		require.NoError(t, err)

		// Verify backup exists
		hourlyDir := filepath.Join(backupDir, "hourly")
		entries, err := os.ReadDir(hourlyDir)
		require.NoError(t, err)
		assert.Greater(t, len(entries), 0, "Should have created backup file")

		// Verify backup integrity
		backupPath := filepath.Join(hourlyDir, entries[0].Name())
		backupDB, err := sql.Open("sqlite", backupPath)
		require.NoError(t, err)
		defer backupDB.Close()

		var result string
		err = backupDB.QueryRow("PRAGMA integrity_check").Scan(&result)
		require.NoError(t, err)
		assert.Equal(t, "ok", result)

		// Verify data was backed up
		var count int
		err = backupDB.QueryRow("SELECT COUNT(*) FROM trades").Scan(&count)
		require.NoError(t, err)
		assert.Equal(t, 2, count)
	})
}

func TestBackupService_DailyBackup(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	t.Run("creates daily backup for all databases except cache", func(t *testing.T) {
		tempDir := t.TempDir()
		dataDir := filepath.Join(tempDir, "data")
		backupDir := filepath.Join(tempDir, "backups")
		require.NoError(t, os.MkdirAll(dataDir, 0755))

		// Create test databases
		universeDB, err := database.New(database.Config{
			Path:    filepath.Join(dataDir, "universe.db"),
			Profile: database.ProfileStandard,
			Name:    "universe",
		})
		require.NoError(t, err)
		defer universeDB.Close()

		ledgerDB, err := database.New(database.Config{
			Path:    filepath.Join(dataDir, "ledger.db"),
			Profile: database.ProfileLedger,
			Name:    "ledger",
		})
		require.NoError(t, err)
		defer ledgerDB.Close()

		databases := map[string]*database.DB{
			"universe": universeDB,
			"ledger":   ledgerDB,
		}

		// Create backup service
		backupService := NewBackupService(databases, dataDir, backupDir, log)

		// Run daily backup
		err = backupService.DailyBackup()
		require.NoError(t, err)

		// Verify backups exist
		date := time.Now().Format("2006-01-02")
		dailyDir := filepath.Join(backupDir, "daily", date)
		entries, err := os.ReadDir(dailyDir)
		require.NoError(t, err)
		assert.Equal(t, 2, len(entries), "Should have 2 backup files")

		// Verify both databases were backed up
		backupNames := []string{}
		for _, entry := range entries {
			backupNames = append(backupNames, entry.Name())
		}
		assert.Contains(t, backupNames, "universe.db")
		assert.Contains(t, backupNames, "ledger.db")
	})
}

func TestBackupService_RotateHourlyBackups(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	t.Run("deletes backups older than 24 hours", func(t *testing.T) {
		tempDir := t.TempDir()
		hourlyDir := filepath.Join(tempDir, "hourly")
		require.NoError(t, os.MkdirAll(hourlyDir, 0755))

		// Create old backup file (25 hours old)
		oldBackup := filepath.Join(hourlyDir, "ledger_old.db")
		err := os.WriteFile(oldBackup, []byte("old"), 0644)
		require.NoError(t, err)
		oldTime := time.Now().Add(-25 * time.Hour)
		err = os.Chtimes(oldBackup, oldTime, oldTime)
		require.NoError(t, err)

		// Create recent backup file (1 hour old)
		recentBackup := filepath.Join(hourlyDir, "ledger_recent.db")
		err = os.WriteFile(recentBackup, []byte("recent"), 0644)
		require.NoError(t, err)

		// Create empty backup service (just for rotation)
		databases := map[string]*database.DB{}
		backupService := NewBackupService(databases, tempDir, tempDir, log)

		// Run rotation
		err = backupService.rotateHourlyBackups(hourlyDir)
		require.NoError(t, err)

		// Verify old backup was deleted
		_, err = os.Stat(oldBackup)
		assert.True(t, os.IsNotExist(err), "Old backup should be deleted")

		// Verify recent backup still exists
		_, err = os.Stat(recentBackup)
		assert.NoError(t, err, "Recent backup should still exist")
	})
}

func TestBackupService_RestoreFromBackup(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	t.Run("finds and returns most recent backup", func(t *testing.T) {
		tempDir := t.TempDir()
		backupDir := filepath.Join(tempDir, "backups")

		// Create daily backup structure
		dailyDir := filepath.Join(backupDir, "daily", "2026-01-01")
		require.NoError(t, os.MkdirAll(dailyDir, 0755))

		// Create backup file
		backupPath := filepath.Join(dailyDir, "universe.db")
		err := os.WriteFile(backupPath, []byte("backup data"), 0644)
		require.NoError(t, err)

		// Create backup service
		databases := map[string]*database.DB{}
		backupService := NewBackupService(databases, tempDir, backupDir, log)

		// Find backup
		foundBackup, err := backupService.RestoreFromBackup("universe")
		require.NoError(t, err)
		assert.Contains(t, foundBackup, "universe.db")
	})

	t.Run("returns error when no backup found", func(t *testing.T) {
		tempDir := t.TempDir()
		backupDir := filepath.Join(tempDir, "backups")

		// Create backup service with empty backup directory
		databases := map[string]*database.DB{}
		backupService := NewBackupService(databases, tempDir, backupDir, log)

		// Try to find non-existent backup
		_, err := backupService.RestoreFromBackup("nonexistent")
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "no backup found")
	})
}

func TestBackupService_VerifyBackup(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	t.Run("verifies valid backup", func(t *testing.T) {
		tempDir := t.TempDir()
		backupPath := filepath.Join(tempDir, "test.db")

		// Create valid database
		db, err := database.New(database.Config{
			Path:    backupPath,
			Profile: database.ProfileStandard,
			Name:    "test",
		})
		require.NoError(t, err)
		db.Close()

		// Create backup service
		databases := map[string]*database.DB{}
		backupService := NewBackupService(databases, tempDir, tempDir, log)

		// Verify backup
		err = backupService.verifyBackup(backupPath)
		assert.NoError(t, err)
	})

	t.Run("detects corrupted backup", func(t *testing.T) {
		tempDir := t.TempDir()
		backupPath := filepath.Join(tempDir, "corrupted.db")

		// Create corrupted file
		err := os.WriteFile(backupPath, []byte("not a valid sqlite database"), 0644)
		require.NoError(t, err)

		// Create backup service
		databases := map[string]*database.DB{}
		backupService := NewBackupService(databases, tempDir, tempDir, log)

		// Verify backup - should fail
		err = backupService.verifyBackup(backupPath)
		assert.Error(t, err)
	})
}
