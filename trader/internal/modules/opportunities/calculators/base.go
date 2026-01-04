package calculators

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// OpportunityCalculator is the interface that all opportunity calculators must implement.
// Each calculator identifies trading opportunities of a specific type (profit taking,
// averaging down, rebalancing, etc.) based on current portfolio state.
type OpportunityCalculator interface {
	// Name returns the unique identifier for this calculator.
	Name() string

	// Calculate identifies trading opportunities based on the opportunity context.
	// Returns a list of action candidates with priorities and reasons.
	Calculate(ctx *domain.OpportunityContext, params map[string]interface{}) ([]domain.ActionCandidate, error)

	// Category returns the opportunity category this calculator produces.
	Category() domain.OpportunityCategory
}

// BaseCalculator provides common functionality for all calculators.
type BaseCalculator struct {
	log zerolog.Logger
}

// NewBaseCalculator creates a new base calculator with logging.
func NewBaseCalculator(log zerolog.Logger, name string) *BaseCalculator {
	return &BaseCalculator{
		log: log.With().Str("calculator", name).Logger(),
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
