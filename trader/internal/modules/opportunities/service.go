package opportunities

import (
	"fmt"

	"github.com/aristath/arduino-trader/internal/modules/opportunities/calculators"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/rs/zerolog"
)

// Service provides the main API for the opportunities module.
type Service struct {
	registry *calculators.CalculatorRegistry
	log      zerolog.Logger
}

// NewService creates a new opportunities service with standard calculators.
// For tag-based optimization, use NewServiceWithHybrid instead.
func NewService(log zerolog.Logger) *Service {
	return &Service{
		registry: calculators.NewPopulatedRegistry(log),
		log:      log.With().Str("module", "opportunities").Logger(),
	}
}

// NewServiceWithHybrid creates a new opportunities service with hybrid calculators
// that use tag-based pre-filtering for improved performance (5-7x faster).
// Requires SecurityRepository for tag queries.
func NewServiceWithHybrid(securityRepo *universe.SecurityRepository, log zerolog.Logger) *Service {
	// Create tag-based filter
	tagFilter := NewTagBasedFilter(securityRepo, log)

	// Create registry with hybrid calculators
	registry := calculators.NewPopulatedRegistryWithHybrid(tagFilter, securityRepo, log)

	return &Service{
		registry: registry,
		log:      log.With().Str("module", "opportunities").Str("mode", "hybrid").Logger(),
	}
}

// IdentifyOpportunities identifies all trading opportunities based on the configuration.
// Returns opportunities organized by category.
func (s *Service) IdentifyOpportunities(
	ctx *domain.OpportunityContext,
	config *domain.PlannerConfiguration,
) (domain.OpportunitiesByCategory, error) {
	s.log.Info().Msg("Identifying opportunities")

	if ctx == nil {
		return nil, fmt.Errorf("opportunity context is nil")
	}

	if config == nil {
		return nil, fmt.Errorf("planner configuration is nil")
	}

	// Use registry to run all enabled calculators
	opportunities, err := s.registry.IdentifyOpportunities(ctx, config)
	if err != nil {
		return nil, fmt.Errorf("failed to identify opportunities: %w", err)
	}

	// Apply max opportunities per category limit
	if config.MaxOpportunitiesPerCategory > 0 {
		opportunities = s.limitOpportunitiesPerCategory(opportunities, config.MaxOpportunitiesPerCategory)
	}

	return opportunities, nil
}

// GetRegistry returns the calculator registry for advanced usage.
func (s *Service) GetRegistry() *calculators.CalculatorRegistry {
	return s.registry
}

// limitOpportunitiesPerCategory limits the number of opportunities per category.
func (s *Service) limitOpportunitiesPerCategory(
	opportunities domain.OpportunitiesByCategory,
	maxPerCategory int,
) domain.OpportunitiesByCategory {
	limited := make(domain.OpportunitiesByCategory)

	for category, candidates := range opportunities {
		if len(candidates) <= maxPerCategory {
			limited[category] = candidates
		} else {
			// Take top N by priority
			// Sort by priority descending (already done by calculators, but ensure it)
			sortByPriority(candidates)
			limited[category] = candidates[:maxPerCategory]

			s.log.Debug().
				Str("category", string(category)).
				Int("original", len(candidates)).
				Int("limited", maxPerCategory).
				Msg("Limited opportunities per category")
		}
	}

	return limited
}

// sortByPriority sorts action candidates by priority in descending order.
func sortByPriority(candidates []domain.ActionCandidate) {
	// Simple bubble sort for now (can optimize later if needed)
	for i := 0; i < len(candidates); i++ {
		for j := i + 1; j < len(candidates); j++ {
			if candidates[j].Priority > candidates[i].Priority {
				candidates[i], candidates[j] = candidates[j], candidates[i]
			}
		}
	}
}
