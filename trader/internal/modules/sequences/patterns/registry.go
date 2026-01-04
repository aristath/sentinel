package patterns

import (
	"fmt"
	"sync"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// PatternRegistry manages all registered pattern generators.
type PatternRegistry struct {
	patterns map[string]PatternGenerator
	mu       sync.RWMutex
	log      zerolog.Logger
}

// NewPatternRegistry creates a new pattern registry.
func NewPatternRegistry(log zerolog.Logger) *PatternRegistry {
	return &PatternRegistry{
		patterns: make(map[string]PatternGenerator),
		log:      log.With().Str("component", "pattern_registry").Logger(),
	}
}

// Register registers a pattern generator.
func (r *PatternRegistry) Register(pattern PatternGenerator) {
	r.mu.Lock()
	defer r.mu.Unlock()

	name := pattern.Name()
	r.patterns[name] = pattern
	r.log.Debug().
		Str("name", name).
		Msg("Registered pattern generator")
}

// Get retrieves a pattern generator by name.
func (r *PatternRegistry) Get(name string) (PatternGenerator, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	pattern, ok := r.patterns[name]
	if !ok {
		return nil, fmt.Errorf("pattern generator not found: %s", name)
	}
	return pattern, nil
}

// GetEnabled retrieves all enabled pattern generators from the configuration.
func (r *PatternRegistry) GetEnabled(config *domain.PlannerConfiguration) []PatternGenerator {
	r.mu.RLock()
	defer r.mu.RUnlock()

	enabledNames := config.GetEnabledPatterns()
	var enabled []PatternGenerator

	for _, name := range enabledNames {
		if pattern, ok := r.patterns[name]; ok {
			enabled = append(enabled, pattern)
		} else {
			r.log.Warn().
				Str("name", name).
				Msg("Enabled pattern generator not found in registry")
		}
	}

	return enabled
}

// List returns all registered pattern generators.
func (r *PatternRegistry) List() []PatternGenerator {
	r.mu.RLock()
	defer r.mu.RUnlock()

	patterns := make([]PatternGenerator, 0, len(r.patterns))
	for _, pattern := range r.patterns {
		patterns = append(patterns, pattern)
	}
	return patterns
}

// GenerateSequences runs all enabled pattern generators and aggregates results.
func (r *PatternRegistry) GenerateSequences(
	opportunities domain.OpportunitiesByCategory,
	config *domain.PlannerConfiguration,
) ([]domain.ActionSequence, error) {
	enabled := r.GetEnabled(config)

	r.log.Info().
		Int("enabled_patterns", len(enabled)).
		Msg("Generating sequences from patterns")

	var allSequences []domain.ActionSequence

	for _, pattern := range enabled {
		name := pattern.Name()
		params := config.GetPatternParams(name)

		r.log.Debug().
			Str("pattern", name).
			Msg("Running pattern generator")

		sequences, err := pattern.Generate(opportunities, params)
		if err != nil {
			r.log.Error().
				Err(err).
				Str("pattern", name).
				Msg("Pattern generator failed")
			continue
		}

		r.log.Debug().
			Str("pattern", name).
			Int("sequences", len(sequences)).
			Msg("Pattern generator completed")

		allSequences = append(allSequences, sequences...)
	}

	r.log.Info().
		Int("total_sequences", len(allSequences)).
		Int("patterns_run", len(enabled)).
		Msg("Sequence generation complete")

	return allSequences, nil
}

// NewPopulatedPatternRegistry creates a new pattern registry with all patterns registered.
func NewPopulatedPatternRegistry(log zerolog.Logger) *PatternRegistry {
	registry := NewPatternRegistry(log)

	// Register all pattern generators
	registry.Register(NewAdaptivePattern(log))
	registry.Register(NewAveragingDownPattern(log))
	registry.Register(NewCashGenerationPattern(log))
	registry.Register(NewCostOptimizedPattern(log))
	registry.Register(NewDeepRebalancePattern(log))
	registry.Register(NewDirectBuyPattern(log))
	registry.Register(NewMarketRegimePattern(log))
	registry.Register(NewMixedStrategyPattern(log))
	registry.Register(NewMultiSellPattern(log))
	registry.Register(NewOpportunityFirstPattern(log))
	registry.Register(NewProfitTakingPattern(log))
	registry.Register(NewRebalancePattern(log))
	registry.Register(NewSingleBestPattern(log))

	log.Info().
		Int("patterns", len(registry.patterns)).
		Msg("Pattern registry initialized")

	return registry
}
