package config

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestLoad_DataDir_DefaultWhenNotSet(t *testing.T) {
	// Save original environment
	originalTraderDataDir := os.Getenv("TRADER_DATA_DIR")
	originalDataDir := os.Getenv("DATA_DIR")
	defer func() {
		if originalTraderDataDir != "" {
			os.Setenv("TRADER_DATA_DIR", originalTraderDataDir)
		} else {
			os.Unsetenv("TRADER_DATA_DIR")
		}
		if originalDataDir != "" {
			os.Setenv("DATA_DIR", originalDataDir)
		} else {
			os.Unsetenv("DATA_DIR")
		}
	}()

	// Clear environment variables
	os.Unsetenv("TRADER_DATA_DIR")
	os.Unsetenv("DATA_DIR")

	// Use a temporary directory that we can actually create
	// This tests the default behavior without requiring /home/arduino to exist
	tmpDir := t.TempDir()
	os.Setenv("TRADER_DATA_DIR", tmpDir)

	cfg, err := Load()
	require.NoError(t, err)
	require.NotNil(t, cfg)

	// Should use the temporary directory, resolved to absolute
	absPath, err := filepath.Abs(tmpDir)
	require.NoError(t, err)
	assert.Equal(t, absPath, cfg.DataDir)

	// Now test the actual default by clearing TRADER_DATA_DIR
	// On macOS, this will fail to create /home/arduino/data, which is expected
	os.Unsetenv("TRADER_DATA_DIR")

	// This will fail on macOS but succeed on Linux (target system)
	_, err = Load()
	// On macOS, we expect this to fail because /home/arduino doesn't exist
	// On Linux, it should succeed
	if err != nil {
		// Verify the error is about directory creation (expected on macOS)
		assert.Contains(t, err.Error(), "failed to create data directory")
	} else {
		// On Linux, verify the default path is used
		cfg, err := Load()
		require.NoError(t, err)
		assert.Equal(t, "/home/arduino/data", cfg.DataDir)
	}
}

func TestLoad_DataDir_FromTRADER_DATA_DIR(t *testing.T) {
	// Save original environment
	originalTraderDataDir := os.Getenv("TRADER_DATA_DIR")
	originalDataDir := os.Getenv("DATA_DIR")
	defer func() {
		if originalTraderDataDir != "" {
			os.Setenv("TRADER_DATA_DIR", originalTraderDataDir)
		} else {
			os.Unsetenv("TRADER_DATA_DIR")
		}
		if originalDataDir != "" {
			os.Setenv("DATA_DIR", originalDataDir)
		} else {
			os.Unsetenv("DATA_DIR")
		}
	}()

	// Set TRADER_DATA_DIR to a test path
	testPath := "/tmp/test-trader-data"
	os.Setenv("TRADER_DATA_DIR", testPath)
	os.Unsetenv("DATA_DIR")

	cfg, err := Load()
	require.NoError(t, err)
	require.NotNil(t, cfg)

	// Should use the value from TRADER_DATA_DIR, resolved to absolute
	absPath, err := filepath.Abs(testPath)
	require.NoError(t, err)
	assert.Equal(t, absPath, cfg.DataDir)
}

func TestLoad_DataDir_IgnoresOldDATA_DIR(t *testing.T) {
	// Save original environment
	originalTraderDataDir := os.Getenv("TRADER_DATA_DIR")
	originalDataDir := os.Getenv("DATA_DIR")
	defer func() {
		if originalTraderDataDir != "" {
			os.Setenv("TRADER_DATA_DIR", originalTraderDataDir)
		} else {
			os.Unsetenv("TRADER_DATA_DIR")
		}
		if originalDataDir != "" {
			os.Setenv("DATA_DIR", originalDataDir)
		} else {
			os.Unsetenv("DATA_DIR")
		}
	}()

	// Set old DATA_DIR but not TRADER_DATA_DIR
	// Use a temporary directory that we can actually create
	tmpDir := t.TempDir()
	os.Setenv("DATA_DIR", tmpDir)
	os.Unsetenv("TRADER_DATA_DIR")

	// On macOS, this will fail to create /home/arduino/data, which is expected
	_, err := Load()
	// On macOS, we expect this to fail because /home/arduino doesn't exist
	// On Linux, it should succeed
	if err != nil {
		// Verify the error is about directory creation (expected on macOS)
		assert.Contains(t, err.Error(), "failed to create data directory")
		// Verify that DATA_DIR was ignored (the error is about /home/arduino/data, not the tmp dir)
		assert.NotContains(t, err.Error(), tmpDir)
	} else {
		// On Linux, verify the default path is used and DATA_DIR is ignored
		cfg, err := Load()
		require.NoError(t, err)
		assert.Equal(t, "/home/arduino/data", cfg.DataDir)
		assert.NotEqual(t, tmpDir, cfg.DataDir)
	}
}

func TestLoad_DataDir_TRADER_DATA_DIRTakesPrecedence(t *testing.T) {
	// Save original environment
	originalTraderDataDir := os.Getenv("TRADER_DATA_DIR")
	originalDataDir := os.Getenv("DATA_DIR")
	defer func() {
		if originalTraderDataDir != "" {
			os.Setenv("TRADER_DATA_DIR", originalTraderDataDir)
		} else {
			os.Unsetenv("TRADER_DATA_DIR")
		}
		if originalDataDir != "" {
			os.Setenv("DATA_DIR", originalDataDir)
		} else {
			os.Unsetenv("DATA_DIR")
		}
	}()

	// Set both, TRADER_DATA_DIR should take precedence
	traderDataDir := "/tmp/trader-data-dir"
	oldDataDir := "/tmp/old-data-dir"
	os.Setenv("TRADER_DATA_DIR", traderDataDir)
	os.Setenv("DATA_DIR", oldDataDir)

	cfg, err := Load()
	require.NoError(t, err)
	require.NotNil(t, cfg)

	// Should use TRADER_DATA_DIR, not DATA_DIR
	absPath, err := filepath.Abs(traderDataDir)
	require.NoError(t, err)
	assert.Equal(t, absPath, cfg.DataDir)
	assert.NotEqual(t, oldDataDir, cfg.DataDir)
}

func TestLoad_DataDir_ResolvesRelativeToAbsolute(t *testing.T) {
	// Save original environment
	originalTraderDataDir := os.Getenv("TRADER_DATA_DIR")
	originalDataDir := os.Getenv("DATA_DIR")
	defer func() {
		if originalTraderDataDir != "" {
			os.Setenv("TRADER_DATA_DIR", originalTraderDataDir)
		} else {
			os.Unsetenv("TRADER_DATA_DIR")
		}
		if originalDataDir != "" {
			os.Setenv("DATA_DIR", originalDataDir)
		} else {
			os.Unsetenv("DATA_DIR")
		}
	}()

	// Set relative path
	os.Setenv("TRADER_DATA_DIR", "./relative/path")
	os.Unsetenv("DATA_DIR")

	cfg, err := Load()
	require.NoError(t, err)
	require.NotNil(t, cfg)

	// Should be resolved to absolute path
	assert.True(t, filepath.IsAbs(cfg.DataDir), "DataDir should be absolute")

	// Verify it resolves correctly
	expectedAbs, err := filepath.Abs("./relative/path")
	require.NoError(t, err)
	assert.Equal(t, expectedAbs, cfg.DataDir)
}

func TestLoad_DataDir_ResolvesAbsolutePath(t *testing.T) {
	// Save original environment
	originalTraderDataDir := os.Getenv("TRADER_DATA_DIR")
	originalDataDir := os.Getenv("DATA_DIR")
	defer func() {
		if originalTraderDataDir != "" {
			os.Setenv("TRADER_DATA_DIR", originalTraderDataDir)
		} else {
			os.Unsetenv("TRADER_DATA_DIR")
		}
		if originalDataDir != "" {
			os.Setenv("DATA_DIR", originalDataDir)
		} else {
			os.Unsetenv("DATA_DIR")
		}
	}()

	// Set absolute path
	absPath := "/tmp/absolute-test-path"
	os.Setenv("TRADER_DATA_DIR", absPath)
	os.Unsetenv("DATA_DIR")

	cfg, err := Load()
	require.NoError(t, err)
	require.NotNil(t, cfg)

	// Should remain absolute (already absolute)
	assert.True(t, filepath.IsAbs(cfg.DataDir), "DataDir should be absolute")
	assert.Equal(t, absPath, cfg.DataDir)
}

func TestLoad_DataDir_CreatesDirectoryIfNeeded(t *testing.T) {
	// Save original environment
	originalTraderDataDir := os.Getenv("TRADER_DATA_DIR")
	originalDataDir := os.Getenv("DATA_DIR")
	defer func() {
		if originalTraderDataDir != "" {
			os.Setenv("TRADER_DATA_DIR", originalTraderDataDir)
		} else {
			os.Unsetenv("TRADER_DATA_DIR")
		}
		if originalDataDir != "" {
			os.Setenv("DATA_DIR", originalDataDir)
		} else {
			os.Unsetenv("DATA_DIR")
		}
	}()

	// Use temporary directory that doesn't exist
	tmpDir := filepath.Join(t.TempDir(), "new-data-dir")
	os.Setenv("TRADER_DATA_DIR", tmpDir)
	os.Unsetenv("DATA_DIR")

	cfg, err := Load()
	require.NoError(t, err)
	require.NotNil(t, cfg)

	// Directory should be created
	absPath, err := filepath.Abs(tmpDir)
	require.NoError(t, err)
	assert.Equal(t, absPath, cfg.DataDir)

	// Verify directory exists
	info, err := os.Stat(cfg.DataDir)
	require.NoError(t, err, "Directory should be created")
	assert.True(t, info.IsDir(), "Should be a directory")
}

func TestLoad_DataDir_WithTemporaryDirectory(t *testing.T) {
	// Save original environment
	originalTraderDataDir := os.Getenv("TRADER_DATA_DIR")
	originalDataDir := os.Getenv("DATA_DIR")
	defer func() {
		if originalTraderDataDir != "" {
			os.Setenv("TRADER_DATA_DIR", originalTraderDataDir)
		} else {
			os.Unsetenv("TRADER_DATA_DIR")
		}
		if originalDataDir != "" {
			os.Setenv("DATA_DIR", originalDataDir)
		} else {
			os.Unsetenv("DATA_DIR")
		}
	}()

	// Use temporary directory
	tmpDir := t.TempDir()
	os.Setenv("TRADER_DATA_DIR", tmpDir)
	os.Unsetenv("DATA_DIR")

	cfg, err := Load()
	require.NoError(t, err)
	require.NotNil(t, cfg)

	// Should use the temporary directory, resolved to absolute
	absPath, err := filepath.Abs(tmpDir)
	require.NoError(t, err)
	assert.Equal(t, absPath, cfg.DataDir)
}
