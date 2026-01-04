package reliability

import (
	"os"
	"path/filepath"
	"testing"

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

		// Create health service
		healthService := NewDatabaseHealthService(db, "test", dbPath, log)

		// Run health check
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
