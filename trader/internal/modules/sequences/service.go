package sequences

import (
	"github.com/aristath/arduino-trader/internal/modules/optimization"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/sequences/filters"
	"github.com/aristath/arduino-trader/internal/modules/sequences/generators"
	"github.com/aristath/arduino-trader/internal/modules/sequences/patterns"
	"github.com/rs/zerolog"
)

type Service struct {
	patternRegistry   *patterns.PatternRegistry
	generatorRegistry *generators.GeneratorRegistry
	filterRegistry    *filters.FilterRegistry
	log               zerolog.Logger
}

func NewService(log zerolog.Logger, riskBuilder *optimization.RiskModelBuilder) *Service {
	return &Service{
		patternRegistry:   patterns.NewPopulatedPatternRegistry(log),
		generatorRegistry: generators.NewPopulatedGeneratorRegistry(log),
		filterRegistry:    filters.NewPopulatedFilterRegistry(log, riskBuilder),
		log:               log.With().Str("module", "sequences").Logger(),
	}
}

func (s *Service) GenerateSequences(
	opportunities domain.OpportunitiesByCategory,
	config *domain.PlannerConfiguration,
) ([]domain.ActionSequence, error) {
	// Generate from patterns
	sequences, err := s.patternRegistry.GenerateSequences(opportunities, config)
	if err != nil {
		return nil, err
	}

	// Apply generators
	sequences, err = s.generatorRegistry.ApplyGenerators(sequences, config)
	if err != nil {
		return nil, err
	}

	// Apply filters
	sequences, err = s.filterRegistry.ApplyFilters(sequences, config)
	if err != nil {
		return nil, err
	}

	s.log.Info().Int("final_sequences", len(sequences)).Msg("Sequence generation complete")
	return sequences, nil
}
