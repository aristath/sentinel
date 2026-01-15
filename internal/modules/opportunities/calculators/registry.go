package calculators

import (
	"fmt"
	"sync"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// ProgressUpdate represents a progress update during opportunity identification.
// Used for hierarchical progress reporting in the planner pipeline.
type ProgressUpdate struct {
	Phase    string         // Phase identifier (e.g., "opportunity_identification")
	SubPhase string         // Sub-phase identifier (e.g., calculator name)
	Current  int            // Current progress count
	Total    int            // Total items to process
	Message  string         // Human-readable progress message
	Details  map[string]any // Arbitrary metrics for debugging
}

// ProgressCallback is a function type for receiving progress updates.
type ProgressCallback func(update ProgressUpdate)

// CalculatorRegistry manages all registered opportunity calculators.
type CalculatorRegistry struct {
	calculators map[string]OpportunityCalculator
	mu          sync.RWMutex
	log         zerolog.Logger
}

// NewCalculatorRegistry creates a new calculator registry.
func NewCalculatorRegistry(log zerolog.Logger) *CalculatorRegistry {
	return &CalculatorRegistry{
		calculators: make(map[string]OpportunityCalculator),
		log:         log.With().Str("component", "calculator_registry").Logger(),
	}
}

// Register registers a calculator.
func (r *CalculatorRegistry) Register(calculator OpportunityCalculator) {
	r.mu.Lock()
	defer r.mu.Unlock()

	name := calculator.Name()
	r.calculators[name] = calculator
	r.log.Debug().
		Str("name", name).
		Str("category", string(calculator.Category())).
		Msg("Registered calculator")
}

// Get retrieves a calculator by name.
func (r *CalculatorRegistry) Get(name string) (OpportunityCalculator, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	calculator, ok := r.calculators[name]
	if !ok {
		return nil, fmt.Errorf("calculator not found: %s", name)
	}
	return calculator, nil
}

// GetEnabled retrieves all enabled calculators from the configuration.
func (r *CalculatorRegistry) GetEnabled(config *domain.PlannerConfiguration) []OpportunityCalculator {
	r.mu.RLock()
	defer r.mu.RUnlock()

	enabledNames := config.GetEnabledCalculators()
	var enabled []OpportunityCalculator

	for _, name := range enabledNames {
		if calculator, ok := r.calculators[name]; ok {
			enabled = append(enabled, calculator)
		} else {
			r.log.Warn().
				Str("name", name).
				Msg("Enabled calculator not found in registry")
		}
	}

	return enabled
}

// List returns all registered calculators.
func (r *CalculatorRegistry) List() []OpportunityCalculator {
	r.mu.RLock()
	defer r.mu.RUnlock()

	calculators := make([]OpportunityCalculator, 0, len(r.calculators))
	for _, calc := range r.calculators {
		calculators = append(calculators, calc)
	}
	return calculators
}

// IdentifyOpportunities runs all enabled calculators and aggregates results by category.
// Returns OpportunitiesByCategory for backward compatibility.
func (r *CalculatorRegistry) IdentifyOpportunities(
	ctx *domain.OpportunityContext,
	config *domain.PlannerConfiguration,
) (domain.OpportunitiesByCategory, error) {
	result, err := r.IdentifyOpportunitiesWithExclusions(ctx, config)
	if err != nil {
		return nil, err
	}
	return result.ToOpportunitiesByCategory(), nil
}

// IdentifyOpportunitiesWithExclusions runs all enabled calculators and aggregates results by category,
// including both candidates and pre-filtered securities.
func (r *CalculatorRegistry) IdentifyOpportunitiesWithExclusions(
	ctx *domain.OpportunityContext,
	config *domain.PlannerConfiguration,
) (domain.OpportunitiesResultByCategory, error) {
	enabled := r.GetEnabled(config)
	results := make(domain.OpportunitiesResultByCategory)

	r.log.Info().
		Int("enabled_calculators", len(enabled)).
		Msg("Identifying opportunities")

	for _, calculator := range enabled {
		name := calculator.Name()
		category := calculator.Category()
		params := config.GetCalculatorParams(name)
		// Add full config to params so calculators can access EnableTagFiltering
		params["config"] = config

		r.log.Debug().
			Str("calculator", name).
			Str("category", string(category)).
			Msg("Running calculator")

		result, err := calculator.Calculate(ctx, params)
		if err != nil {
			r.log.Error().
				Err(err).
				Str("calculator", name).
				Msg("Calculator failed")
			continue
		}

		r.log.Debug().
			Str("calculator", name).
			Int("candidates", len(result.Candidates)).
			Int("pre_filtered", len(result.PreFiltered)).
			Msg("Calculator completed")

		// Merge into category results
		existing := results[category]
		existing.Candidates = append(existing.Candidates, result.Candidates...)
		existing.PreFiltered = append(existing.PreFiltered, result.PreFiltered...)
		results[category] = existing
	}

	// Log summary
	totalCandidates := 0
	totalPreFiltered := 0
	for category, result := range results {
		totalCandidates += len(result.Candidates)
		totalPreFiltered += len(result.PreFiltered)
		r.log.Info().
			Str("category", string(category)).
			Int("candidates", len(result.Candidates)).
			Int("pre_filtered", len(result.PreFiltered)).
			Msg("Opportunities by category")
	}

	r.log.Info().
		Int("total_candidates", totalCandidates).
		Int("total_pre_filtered", totalPreFiltered).
		Int("categories", len(results)).
		Msg("Opportunity identification complete")

	return results, nil
}

// IdentifyOpportunitiesWithProgress runs all enabled calculators with progress reporting.
// Reports progress after each calculator completes, enabling real-time UI updates.
func (r *CalculatorRegistry) IdentifyOpportunitiesWithProgress(
	ctx *domain.OpportunityContext,
	config *domain.PlannerConfiguration,
	progressCallback ProgressCallback,
) (domain.OpportunitiesResultByCategory, error) {
	enabled := r.GetEnabled(config)
	results := make(domain.OpportunitiesResultByCategory)

	total := len(enabled)
	if total == 0 {
		return results, nil
	}

	r.log.Info().
		Int("enabled_calculators", total).
		Msg("Identifying opportunities with progress reporting")

	// Track cumulative counts for progress details
	candidatesSoFar := 0
	filteredSoFar := 0

	for i, calculator := range enabled {
		name := calculator.Name()
		category := calculator.Category()
		params := config.GetCalculatorParams(name)
		params["config"] = config

		r.log.Debug().
			Str("calculator", name).
			Str("category", string(category)).
			Int("index", i+1).
			Int("total", total).
			Msg("Running calculator")

		// Report progress before running calculator
		if progressCallback != nil {
			progressCallback(ProgressUpdate{
				Phase:    "opportunity_identification",
				SubPhase: name,
				Current:  i + 1,
				Total:    total,
				Message:  fmt.Sprintf("Running %s calculator", name),
				Details: map[string]any{
					"calculators_total":  total,
					"calculators_done":   i,
					"candidates_so_far":  candidatesSoFar,
					"filtered_so_far":    filteredSoFar,
					"current_calculator": name,
				},
			})
		}

		result, err := calculator.Calculate(ctx, params)
		if err != nil {
			r.log.Error().
				Err(err).
				Str("calculator", name).
				Msg("Calculator failed")
			continue
		}

		// Update cumulative counts
		candidatesSoFar += len(result.Candidates)
		filteredSoFar += len(result.PreFiltered)

		r.log.Debug().
			Str("calculator", name).
			Int("candidates", len(result.Candidates)).
			Int("pre_filtered", len(result.PreFiltered)).
			Msg("Calculator completed")

		// Merge into category results
		existing := results[category]
		existing.Candidates = append(existing.Candidates, result.Candidates...)
		existing.PreFiltered = append(existing.PreFiltered, result.PreFiltered...)
		results[category] = existing

		// Report progress after calculator completes
		if progressCallback != nil {
			progressCallback(ProgressUpdate{
				Phase:    "opportunity_identification",
				SubPhase: name,
				Current:  i + 1,
				Total:    total,
				Message:  fmt.Sprintf("Completed %s calculator", name),
				Details: map[string]any{
					"calculators_total":        total,
					"calculators_done":         i + 1,
					"candidates_so_far":        candidatesSoFar,
					"filtered_so_far":          filteredSoFar,
					"current_calculator":       name,
					"current_candidates_found": len(result.Candidates),
					"current_filtered_count":   len(result.PreFiltered),
				},
			})
		}
	}

	// Log summary
	for category, result := range results {
		r.log.Info().
			Str("category", string(category)).
			Int("candidates", len(result.Candidates)).
			Int("pre_filtered", len(result.PreFiltered)).
			Msg("Opportunities by category")
	}

	r.log.Info().
		Int("total_candidates", candidatesSoFar).
		Int("total_pre_filtered", filteredSoFar).
		Int("categories", len(results)).
		Msg("Opportunity identification with progress complete")

	return results, nil
}

// NewPopulatedRegistry creates a new calculator registry with all calculators registered.
func NewPopulatedRegistry(
	tagFilter TagFilter,
	securityRepo SecurityRepository,
	log zerolog.Logger,
) *CalculatorRegistry {
	registry := NewCalculatorRegistry(log)

	// Register all calculators (unified implementations with tag-based optimizations)
	registry.Register(NewAveragingDownCalculator(tagFilter, securityRepo, log))
	registry.Register(NewOpportunityBuysCalculator(tagFilter, securityRepo, log))
	registry.Register(NewProfitTakingCalculator(tagFilter, securityRepo, log))
	registry.Register(NewRebalanceBuysCalculator(tagFilter, securityRepo, log))
	registry.Register(NewRebalanceSellsCalculator(tagFilter, securityRepo, log))
	registry.Register(NewWeightBasedCalculator(securityRepo, log))

	log.Info().
		Int("calculators", len(registry.calculators)).
		Msg("Calculator registry initialized with unified calculators")

	return registry
}
