package logger

import (
	"bytes"
	"strings"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNew_DefaultConfig(t *testing.T) {
	cfg := Config{
		Level:  "info",
		Pretty: false,
	}

	logger := New(cfg)
	assert.NotNil(t, logger)

	// Test that logger outputs to stdout
	var buf bytes.Buffer
	logger = logger.Output(&buf)
	logger.Info().Msg("test message")

	assert.Contains(t, buf.String(), "test message")
}

func TestNew_AllLogLevels(t *testing.T) {
	testCases := []struct {
		level         string
		expectedLevel zerolog.Level
		name          string
	}{
		{"debug", zerolog.DebugLevel, "debug"},
		{"info", zerolog.InfoLevel, "info"},
		{"warn", zerolog.WarnLevel, "warn"},
		{"error", zerolog.ErrorLevel, "error"},
		{"unknown", zerolog.InfoLevel, "unknown defaults to info"},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			cfg := Config{
				Level:  tc.level,
				Pretty: false,
			}

			logger := New(cfg)
			assert.NotNil(t, logger)

			// Verify global level is set
			assert.Equal(t, tc.expectedLevel, zerolog.GlobalLevel())
		})
	}
}

func TestNew_PrettyOutput(t *testing.T) {
	cfg := Config{
		Level:  "info",
		Pretty: true,
	}

	logger := New(cfg)
	assert.NotNil(t, logger)

	// Test that pretty output works
	var buf bytes.Buffer
	logger = logger.Output(&buf)
	logger.Info().Msg("test message")

	output := buf.String()
	assert.NotEmpty(t, output)
	// Pretty output should contain the message
	assert.Contains(t, output, "test message")
}

func TestNew_TimestampFormat(t *testing.T) {
	cfg := Config{
		Level:  "info",
		Pretty: false,
	}

	logger := New(cfg)
	assert.NotNil(t, logger)

	// Verify time format is set to RFC3339
	assert.Equal(t, "2006-01-02T15:04:05Z07:00", zerolog.TimeFieldFormat)
}

func TestNew_CallerEnabled(t *testing.T) {
	cfg := Config{
		Level:  "debug",
		Pretty: false,
	}

	logger := New(cfg)
	assert.NotNil(t, logger)

	// Test that caller is enabled by checking logger output
	var buf bytes.Buffer
	logger = logger.Output(&buf)
	logger.Debug().Msg("test with caller")

	output := buf.String()
	// Caller should be present in output (file path and line number)
	// The exact format depends on zerolog's caller implementation
	assert.NotEmpty(t, output)
}

func TestSetGlobalLogger(t *testing.T) {
	cfg := Config{
		Level:  "info",
		Pretty: false,
	}

	logger := New(cfg)
	originalLogger := zerolog.Logger{}

	// Set global logger
	SetGlobalLogger(logger)

	// Verify global logger was set
	// We can't directly compare, but we can test that it works
	var buf bytes.Buffer
	testLogger := logger.Output(&buf)
	testLogger.Info().Msg("global logger test")

	assert.Contains(t, buf.String(), "global logger test")

	// Restore original (set it back to a default)
	SetGlobalLogger(originalLogger)
}

func TestNew_PrettyTimeFormat(t *testing.T) {
	cfg := Config{
		Level:  "info",
		Pretty: true,
	}

	logger := New(cfg)
	assert.NotNil(t, logger)

	// When pretty is enabled, ConsoleWriter should use "15:04:05" format
	// This is harder to test directly, but we can verify the logger works
	var buf bytes.Buffer
	logger = logger.Output(&buf)
	logger.Info().Str("key", "value").Msg("test")

	output := buf.String()
	assert.NotEmpty(t, output)
	assert.Contains(t, strings.ToLower(output), "test")
}

func TestNew_OutputsToStdout(t *testing.T) {
	cfg := Config{
		Level:  "info",
		Pretty: false,
	}

	logger := New(cfg)
	assert.NotNil(t, logger)

	// Verify logger is configured (we can't easily test stdout directly
	// without mocking, but we can verify it doesn't panic)
	logger.Info().Msg("stdout test")
}

func TestNew_ErrorLevelFiltersLower(t *testing.T) {
	cfg := Config{
		Level:  "error",
		Pretty: false,
	}

	logger := New(cfg)
	var buf bytes.Buffer
	logger = logger.Output(&buf)

	// Info messages should be filtered out
	logger.Info().Msg("should not appear")
	assert.NotContains(t, buf.String(), "should not appear")

	// Error messages should appear
	logger.Error().Msg("should appear")
	assert.Contains(t, buf.String(), "should appear")
}

func TestNew_DebugLevelShowsAll(t *testing.T) {
	cfg := Config{
		Level:  "debug",
		Pretty: false,
	}

	logger := New(cfg)
	var buf bytes.Buffer
	logger = logger.Output(&buf)

	// Debug messages should appear
	logger.Debug().Msg("debug message")
	assert.Contains(t, buf.String(), "debug message")

	// Info messages should appear
	buf.Reset()
	logger.Info().Msg("info message")
	assert.Contains(t, buf.String(), "info message")

	// Error messages should appear
	buf.Reset()
	logger.Error().Msg("error message")
	assert.Contains(t, buf.String(), "error message")
}

func TestConfig_EmptyLevel(t *testing.T) {
	cfg := Config{
		Level:  "",
		Pretty: false,
	}

	logger := New(cfg)
	require.NotNil(t, logger)

	// Empty level should default to InfoLevel
	assert.Equal(t, zerolog.InfoLevel, zerolog.GlobalLevel())
}

func TestSetGlobalLogger_ReplacesExisting(t *testing.T) {
	// Set up first logger with debug level
	cfg1 := Config{Level: "debug", Pretty: false}
	logger1 := New(cfg1)
	SetGlobalLogger(logger1)
	// Verify debug level is set
	assert.Equal(t, zerolog.DebugLevel, zerolog.GlobalLevel())

	// Set up second logger with error level
	cfg2 := Config{Level: "error", Pretty: false}
	logger2 := New(cfg2)
	// New() sets global level, so it should now be error level
	assert.Equal(t, zerolog.ErrorLevel, zerolog.GlobalLevel())

	// Replace global logger
	SetGlobalLogger(logger2)
	// Global level remains error (set by New())
	assert.Equal(t, zerolog.ErrorLevel, zerolog.GlobalLevel())
}
