package patterns

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// PatternGenerator is the interface that all pattern generators must implement.
// Each generator creates action sequences from identified opportunities using
// different strategic patterns (direct buy, rebalance, profit-taking, etc.).
type PatternGenerator interface {
	// Name returns the unique identifier for this pattern generator.
	Name() string

	// Generate creates action sequences from the given opportunities.
	// Returns a list of sequences with associated metadata.
	Generate(opportunities domain.OpportunitiesByCategory, params map[string]interface{}) ([]domain.ActionSequence, error)
}

// BasePattern provides common functionality for all pattern generators.
type BasePattern struct {
	log zerolog.Logger
}

// NewBasePattern creates a new base pattern with logging.
func NewBasePattern(log zerolog.Logger, name string) *BasePattern {
	return &BasePattern{
		log: log.With().Str("pattern", name).Logger(),
	}
}

// GetFloatParam retrieves a float parameter with a default value.
func GetFloatParam(params map[string]interface{}, key string, defaultValue float64) float64 {
	if params == nil {
		return defaultValue
	}
	if val, ok := params[key]; ok {
		if floatVal, ok := val.(float64); ok {
			return floatVal
		}
		if intVal, ok := val.(int); ok {
			return float64(intVal)
		}
	}
	return defaultValue
}

// GetIntParam retrieves an int parameter with a default value.
func GetIntParam(params map[string]interface{}, key string, defaultValue int) int {
	if params == nil {
		return defaultValue
	}
	if val, ok := params[key]; ok {
		if intVal, ok := val.(int); ok {
			return intVal
		}
		if floatVal, ok := val.(float64); ok {
			return int(floatVal)
		}
	}
	return defaultValue
}

// GetBoolParam retrieves a bool parameter with a default value.
func GetBoolParam(params map[string]interface{}, key string, defaultValue bool) bool {
	if params == nil {
		return defaultValue
	}
	if val, ok := params[key]; ok {
		if boolVal, ok := val.(bool); ok {
			return boolVal
		}
	}
	return defaultValue
}

// CreateSequence is a helper to create an ActionSequence from a list of actions.
func CreateSequence(actions []domain.ActionCandidate, patternType string) domain.ActionSequence {
	// Calculate aggregate priority (average)
	priority := 0.0
	if len(actions) > 0 {
		for _, action := range actions {
			priority += action.Priority
		}
		priority /= float64(len(actions))
	}

	// Generate sequence hash (simple implementation for now)
	sequenceHash := generateSequenceHash(actions)

	return domain.ActionSequence{
		Actions:      actions,
		Priority:     priority,
		Depth:        len(actions),
		PatternType:  patternType,
		SequenceHash: sequenceHash,
	}
}

// generateSequenceHash creates a hash for the sequence (simplified).
// In production, this would use MD5 or similar.
func generateSequenceHash(actions []domain.ActionCandidate) string {
	// For now, just concatenate symbol-side-quantity
	hash := ""
	for _, action := range actions {
		hash += action.Symbol + "-" + action.Side + "-"
	}
	return hash
}
