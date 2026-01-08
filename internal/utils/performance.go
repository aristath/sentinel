package utils

import (
	"time"

	"github.com/rs/zerolog"
)

// Timer is a simple performance timer for measuring operation duration
type Timer struct {
	start   time.Time
	name    string
	log     zerolog.Logger
	enabled bool
}

// NewTimer creates a new timer with the given name
func NewTimer(name string, log zerolog.Logger) *Timer {
	return &Timer{
		start:   time.Now(),
		name:    name,
		log:     log,
		enabled: true,
	}
}

// Stop stops the timer and logs the duration
func (t *Timer) Stop() time.Duration {
	if !t.enabled {
		return 0
	}

	duration := time.Since(t.start)

	// Log performance metrics
	t.log.Debug().
		Str("operation", t.name).
		Dur("duration_ms", duration).
		Float64("duration_seconds", duration.Seconds()).
		Msg("Performance measurement")

	// Warn if operation took longer than expected thresholds
	if duration > 30*time.Second {
		t.log.Warn().
			Str("operation", t.name).
			Dur("duration", duration).
			Msg("Slow operation detected (>30s)")
	} else if duration > 10*time.Second {
		t.log.Info().
			Str("operation", t.name).
			Dur("duration", duration).
			Msg("Operation took longer than expected (>10s)")
	}

	return duration
}

// StopWithContext stops the timer and logs with additional context
func (t *Timer) StopWithContext(context map[string]interface{}) time.Duration {
	if !t.enabled {
		return 0
	}

	duration := time.Since(t.start)

	// Build log event with context
	event := t.log.Debug().
		Str("operation", t.name).
		Dur("duration_ms", duration).
		Float64("duration_seconds", duration.Seconds())

	// Add context fields
	for key, value := range context {
		switch v := value.(type) {
		case string:
			event = event.Str(key, v)
		case int:
			event = event.Int(key, v)
		case int64:
			event = event.Int64(key, v)
		case float64:
			event = event.Float64(key, v)
		case bool:
			event = event.Bool(key, v)
		default:
			event = event.Interface(key, v)
		}
	}

	event.Msg("Performance measurement")

	return duration
}

// Disable disables the timer (useful for production)
func (t *Timer) Disable() {
	t.enabled = false
}

// OperationTimer provides a defer-friendly way to measure operation duration
//
// Usage:
//
//	func MyFunction() {
//	    defer utils.OperationTimer("my_function", log)()
//	}
func OperationTimer(operation string, log zerolog.Logger) func() {
	start := time.Now()

	return func() {
		duration := time.Since(start)

		log.Debug().
			Str("operation", operation).
			Dur("duration_ms", duration).
			Msg("Operation completed")

		// Warn on slow operations
		if duration > 30*time.Second {
			log.Warn().
				Str("operation", operation).
				Dur("duration", duration).
				Msg("Slow operation detected")
		}
	}
}

// MeasureDBQuery measures database query performance
func MeasureDBQuery(queryName string, log zerolog.Logger) func(rowsAffected int64) {
	start := time.Now()

	return func(rowsAffected int64) {
		duration := time.Since(start)

		log.Debug().
			Str("query", queryName).
			Dur("duration_ms", duration).
			Int64("rows_affected", rowsAffected).
			Msg("Database query completed")

		// Warn on slow queries
		if duration > 5*time.Second {
			log.Warn().
				Str("query", queryName).
				Dur("duration", duration).
				Int64("rows_affected", rowsAffected).
				Msg("Slow database query detected")
		}
	}
}

// PerformanceMetrics holds aggregated performance metrics
type PerformanceMetrics struct {
	OperationName string
	CallCount     int64
	TotalDuration time.Duration
	MinDuration   time.Duration
	MaxDuration   time.Duration
	AvgDuration   time.Duration
}

// LogMetrics logs the aggregated performance metrics
func (pm *PerformanceMetrics) LogMetrics(log zerolog.Logger) {
	if pm.CallCount == 0 {
		return
	}

	log.Info().
		Str("operation", pm.OperationName).
		Int64("call_count", pm.CallCount).
		Dur("total_duration", pm.TotalDuration).
		Dur("avg_duration", pm.AvgDuration).
		Dur("min_duration", pm.MinDuration).
		Dur("max_duration", pm.MaxDuration).
		Msg("Performance metrics summary")
}
