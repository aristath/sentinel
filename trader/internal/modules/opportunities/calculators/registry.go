package calculators

import (
	"fmt"
	"sync"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

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
func (r *CalculatorRegistry) IdentifyOpportunities(
	ctx *domain.OpportunityContext,
	config *domain.PlannerConfiguration,
) (domain.OpportunitiesByCategory, error) {
	enabled := r.GetEnabled(config)
	opportunities := make(domain.OpportunitiesByCategory)

	r.log.Info().
		Int("enabled_calculators", len(enabled)).
		Msg("Identifying opportunities")

	for _, calculator := range enabled {
		name := calculator.Name()
		category := calculator.Category()
		params := config.GetCalculatorParams(name)

		r.log.Debug().
			Str("calculator", name).
			Str("category", string(category)).
			Msg("Running calculator")

		candidates, err := calculator.Calculate(ctx, params)
		if err != nil {
			r.log.Error().
				Err(err).
				Str("calculator", name).
				Msg("Calculator failed")
			continue
		}

		r.log.Debug().
			Str("calculator", name).
			Int("candidates", len(candidates)).
			Msg("Calculator completed")

		// Append to category
		opportunities[category] = append(opportunities[category], candidates...)
	}

	// Log summary
	totalCandidates := 0
	for category, candidates := range opportunities {
		totalCandidates += len(candidates)
		r.log.Info().
			Str("category", string(category)).
			Int("candidates", len(candidates)).
			Msg("Opportunities by category")
	}

	r.log.Info().
		Int("total_candidates", totalCandidates).
		Int("categories", len(opportunities)).
		Msg("Opportunity identification complete")

	return opportunities, nil
}

// NewPopulatedRegistry creates a new calculator registry with all calculators registered.
func NewPopulatedRegistry(log zerolog.Logger) *CalculatorRegistry {
	registry := NewCalculatorRegistry(log)

	// Register all calculators
	registry.Register(NewAveragingDownCalculator(log))
	registry.Register(NewOpportunityBuysCalculator(log))
	registry.Register(NewProfitTakingCalculator(log))
	registry.Register(NewRebalanceBuysCalculator(log))
	registry.Register(NewRebalanceSellsCalculator(log))
	registry.Register(NewWeightBasedCalculator(log))

	log.Info().
		Int("calculators", len(registry.calculators)).
		Msg("Calculator registry initialized")

	return registry
}
