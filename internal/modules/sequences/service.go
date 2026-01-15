// Package sequences provides trading sequence generation functionality.
package sequences

import (
	"github.com/aristath/sentinel/internal/modules/optimization"
	"github.com/aristath/sentinel/internal/modules/planning/constraints"
	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/planning/progress"
	"github.com/aristath/sentinel/internal/modules/sequences/filters"
	"github.com/rs/zerolog"
)

// Service generates and filters trading sequences.
// Uses an exhaustive generator to create all valid combinations of opportunities,
// then applies filters for correlation, diversity, and deduplication.
type Service struct {
	generator      *ExhaustiveGenerator
	filterRegistry *filters.FilterRegistry
	log            zerolog.Logger
}

// NewService creates a new sequences service.
func NewService(
	log zerolog.Logger,
	riskBuilder *optimization.RiskModelBuilder,
	enforcer *constraints.Enforcer,
) *Service {
	return &Service{
		generator:      NewExhaustiveGenerator(log, enforcer),
		filterRegistry: filters.NewPopulatedFilterRegistry(log, riskBuilder),
		log:            log.With().Str("module", "sequences").Logger(),
	}
}

// GenerateSequences creates all valid action sequences from opportunities.
// Steps:
// 1. Exhaustive generation: All combinations up to max_depth
// 2. Constraint filtering: During generation (cooloff, ineligibility, etc.)
// 3. Cash feasibility: Prune sequences that can't be executed
// 4. Post-filters: Correlation, diversity (if enabled)
//
// The progressCallback is called during generation to report progress.
func (s *Service) GenerateSequences(
	opportunities domain.OpportunitiesByCategory,
	ctx *domain.OpportunityContext,
	config *domain.PlannerConfiguration,
	progressCallback progress.Callback,
) ([]domain.ActionSequence, error) {
	// Build generation config from planner config
	genConfig := DefaultGenerationConfig()
	if config != nil {
		if config.MaxDepth > 0 {
			genConfig.MaxDepth = config.MaxDepth
		}
		// MaxSequences is not in PlannerConfiguration, use default (0 = unlimited)
	}
	if ctx != nil {
		genConfig.AvailableCash = ctx.AvailableCashEUR
		genConfig.PruneInfeasible = true
	}
	genConfig.ProgressCallback = progressCallback

	// Generate sequences
	sequences := s.generator.Generate(opportunities, ctx, genConfig)

	s.log.Info().
		Int("pre_filter_sequences", len(sequences)).
		Msg("Sequences generated, applying filters")

	// Apply post-generation filters (correlation, diversity)
	var err error
	sequences, err = s.filterRegistry.ApplyFilters(sequences, config)
	if err != nil {
		s.log.Error().Err(err).Msg("Filter application failed")
		// Continue with unfiltered sequences rather than failing
	}

	s.log.Info().
		Int("final_sequences", len(sequences)).
		Msg("Sequence generation complete")

	return sequences, nil
}

// GenerateSequencesWithDetailedProgress creates sequences with detailed progress reporting.
// This method provides rich progress metrics for debugging and UI display.
// The detailedCallback receives structured updates with phase, subphase, and details.
func (s *Service) GenerateSequencesWithDetailedProgress(
	opportunities domain.OpportunitiesByCategory,
	ctx *domain.OpportunityContext,
	config *domain.PlannerConfiguration,
	detailedCallback progress.DetailedCallback,
) ([]domain.ActionSequence, error) {
	// Build generation config from planner config
	genConfig := DefaultGenerationConfig()
	if config != nil {
		if config.MaxDepth > 0 {
			genConfig.MaxDepth = config.MaxDepth
		}
	}
	if ctx != nil {
		genConfig.AvailableCash = ctx.AvailableCashEUR
		genConfig.PruneInfeasible = true
	}
	genConfig.DetailedProgressCallback = detailedCallback

	// Generate sequences
	sequences := s.generator.Generate(opportunities, ctx, genConfig)

	s.log.Info().
		Int("pre_filter_sequences", len(sequences)).
		Msg("Sequences generated with detailed progress, applying filters")

	// Apply post-generation filters (correlation, diversity)
	var err error
	sequences, err = s.filterRegistry.ApplyFilters(sequences, config)
	if err != nil {
		s.log.Error().Err(err).Msg("Filter application failed")
		// Continue with unfiltered sequences rather than failing
	}

	s.log.Info().
		Int("final_sequences", len(sequences)).
		Msg("Sequence generation with detailed progress complete")

	return sequences, nil
}
