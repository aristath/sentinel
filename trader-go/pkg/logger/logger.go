package logger

import (
	"io"
	"os"
	"time"

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
)

// Config holds logger configuration
type Config struct {
	Level  string // debug, info, warn, error
	Pretty bool   // Enable pretty console output
}

// New creates a new structured logger
func New(cfg Config) zerolog.Logger {
	// Parse log level
	level := zerolog.InfoLevel
	switch cfg.Level {
	case "debug":
		level = zerolog.DebugLevel
	case "info":
		level = zerolog.InfoLevel
	case "warn":
		level = zerolog.WarnLevel
	case "error":
		level = zerolog.ErrorLevel
	}

	zerolog.SetGlobalLevel(level)
	zerolog.TimeFieldFormat = time.RFC3339

	// Configure output
	var output io.Writer = os.Stdout
	if cfg.Pretty {
		output = zerolog.ConsoleWriter{
			Out:        os.Stdout,
			TimeFormat: "15:04:05",
		}
	}

	return zerolog.New(output).
		With().
		Timestamp().
		Caller().
		Logger()
}

// SetGlobalLogger sets the package-level logger
func SetGlobalLogger(l zerolog.Logger) {
	log.Logger = l
}
