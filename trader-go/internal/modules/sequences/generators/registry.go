package generators

import (
	"fmt"
	"sync"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

type GeneratorRegistry struct {
	generators map[string]SequenceGenerator
	mu         sync.RWMutex
	log        zerolog.Logger
}

func NewGeneratorRegistry(log zerolog.Logger) *GeneratorRegistry {
	return &GeneratorRegistry{
		generators: make(map[string]SequenceGenerator),
		log:        log.With().Str("component", "generator_registry").Logger(),
	}
}

func (r *GeneratorRegistry) Register(gen SequenceGenerator) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.generators[gen.Name()] = gen
	r.log.Debug().Str("name", gen.Name()).Msg("Registered generator")
}

func (r *GeneratorRegistry) Get(name string) (SequenceGenerator, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	gen, ok := r.generators[name]
	if !ok {
		return nil, fmt.Errorf("generator not found: %s", name)
	}
	return gen, nil
}

func (r *GeneratorRegistry) GetEnabled(config *domain.PlannerConfiguration) []SequenceGenerator {
	r.mu.RLock()
	defer r.mu.RUnlock()
	enabledNames := config.GetEnabledGenerators()
	var enabled []SequenceGenerator
	for _, name := range enabledNames {
		if gen, ok := r.generators[name]; ok {
			enabled = append(enabled, gen)
		}
	}
	return enabled
}

func (r *GeneratorRegistry) ApplyGenerators(sequences []domain.ActionSequence, config *domain.PlannerConfiguration) ([]domain.ActionSequence, error) {
	enabled := r.GetEnabled(config)
	result := sequences
	for _, gen := range enabled {
		params := config.GetGeneratorParams(gen.Name())
		expanded, err := gen.Generate(result, params)
		if err != nil {
			r.log.Error().Err(err).Str("generator", gen.Name()).Msg("Generator failed")
			continue
		}
		result = expanded
	}
	return result, nil
}

// NewPopulatedGeneratorRegistry creates a new generator registry with all generators registered.
func NewPopulatedGeneratorRegistry(log zerolog.Logger) *GeneratorRegistry {
	registry := NewGeneratorRegistry(log)

	// Register all sequence generators
	registry.Register(NewCombinatorialGenerator(log))
	registry.Register(NewEnhancedCombinatorialGenerator(log))
	registry.Register(NewPartialExecutionGenerator(log))
	registry.Register(NewConstraintRelaxationGenerator(log))

	log.Info().
		Int("generators", len(registry.generators)).
		Msg("Generator registry initialized")

	return registry
}
