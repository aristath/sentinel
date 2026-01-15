// Package opportunities provides trading opportunity identification functionality.
package opportunities

import (
	"fmt"

	"github.com/aristath/sentinel/internal/modules/opportunities/calculators"
	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/planning/progress"
	"github.com/rs/zerolog"
)

// Service provides the main API for the opportunities module.
type Service struct {
	registry *calculators.CalculatorRegistry
	log      zerolog.Logger
}

// NewService creates a new opportunities service with unified calculators.
// Tag-based optimization is controlled by the EnableTagFiltering config option.
// Requires SecurityRepository for tag queries and quality gates.
// Follows Dependency Inversion Principle - depends on interface, not concrete implementation.
func NewService(
	tagFilter calculators.TagFilter,
	securityRepo SecurityRepository,
	log zerolog.Logger,
) *Service {
	return &Service{
		registry: calculators.NewPopulatedRegistry(tagFilter, securityRepo, log),
		log:      log.With().Str("module", "opportunities").Logger(),
	}
}

// IdentifyOpportunities identifies all trading opportunities based on the configuration.
// Returns opportunities organized by category.
func (s *Service) IdentifyOpportunities(
	ctx *domain.OpportunityContext,
	config *domain.PlannerConfiguration,
) (domain.OpportunitiesByCategory, error) {
	result, err := s.IdentifyOpportunitiesWithExclusions(ctx, config)
	if err != nil {
		return nil, err
	}
	return result.ToOpportunitiesByCategory(), nil
}

// IdentifyOpportunitiesWithExclusions identifies all trading opportunities and returns
// both the opportunities and the pre-filtered securities that were excluded.
func (s *Service) IdentifyOpportunitiesWithExclusions(
	ctx *domain.OpportunityContext,
	config *domain.PlannerConfiguration,
) (domain.OpportunitiesResultByCategory, error) {
	return s.IdentifyOpportunitiesWithProgress(ctx, config, nil)
}

// IdentifyOpportunitiesWithProgress identifies all trading opportunities with detailed
// progress reporting. The callback receives updates for each calculator that runs.
func (s *Service) IdentifyOpportunitiesWithProgress(
	ctx *domain.OpportunityContext,
	config *domain.PlannerConfiguration,
	progressCallback progress.DetailedCallback,
) (domain.OpportunitiesResultByCategory, error) {
	s.log.Info().Msg("Identifying opportunities with progress")

	if ctx == nil {
		return nil, fmt.Errorf("opportunity context is nil")
	}

	if config == nil {
		return nil, fmt.Errorf("planner configuration is nil")
	}

	// Convert progress.DetailedCallback to calculators.ProgressCallback
	var registryCallback calculators.ProgressCallback
	if progressCallback != nil {
		registryCallback = func(update calculators.ProgressUpdate) {
			progressCallback(progress.Update{
				Phase:    update.Phase,
				SubPhase: update.SubPhase,
				Current:  update.Current,
				Total:    update.Total,
				Message:  update.Message,
				Details:  update.Details,
			})
		}
	}

	// Use registry to run all enabled calculators with progress
	results, err := s.registry.IdentifyOpportunitiesWithProgress(ctx, config, registryCallback)
	if err != nil {
		return nil, fmt.Errorf("failed to identify opportunities: %w", err)
	}

	// Apply max opportunities per category limit (to candidates only)
	if config.MaxOpportunitiesPerCategory > 0 {
		results = s.limitOpportunitiesPerCategoryWithExclusions(results, config.MaxOpportunitiesPerCategory)
	}

	return results, nil
}

// GetRegistry returns the calculator registry for advanced usage.
func (s *Service) GetRegistry() *calculators.CalculatorRegistry {
	return s.registry
}

// limitOpportunitiesPerCategoryWithExclusions limits the number of candidates per category,
// preserving pre-filtered securities.
func (s *Service) limitOpportunitiesPerCategoryWithExclusions(
	results domain.OpportunitiesResultByCategory,
	maxPerCategory int,
) domain.OpportunitiesResultByCategory {
	limited := make(domain.OpportunitiesResultByCategory)

	for category, result := range results {
		candidates := result.Candidates
		if len(candidates) <= maxPerCategory {
			limited[category] = result
		} else {
			// Take top N by priority
			sortByPriority(candidates)
			limited[category] = domain.CalculatorResult{
				Candidates:  candidates[:maxPerCategory],
				PreFiltered: result.PreFiltered, // Preserve all pre-filtered
			}

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
