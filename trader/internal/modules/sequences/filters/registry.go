package filters

import (
	"fmt"
	"sync"

	"github.com/aristath/arduino-trader/internal/modules/optimization"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

type FilterRegistry struct {
	filters map[string]SequenceFilter
	mu      sync.RWMutex
	log     zerolog.Logger
}

func NewFilterRegistry(log zerolog.Logger) *FilterRegistry {
	return &FilterRegistry{
		filters: make(map[string]SequenceFilter),
		log:     log.With().Str("component", "filter_registry").Logger(),
	}
}

func (r *FilterRegistry) Register(filter SequenceFilter) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.filters[filter.Name()] = filter
	r.log.Debug().Str("name", filter.Name()).Msg("Registered filter")
}

func (r *FilterRegistry) Get(name string) (SequenceFilter, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	filter, ok := r.filters[name]
	if !ok {
		return nil, fmt.Errorf("filter not found: %s", name)
	}
	return filter, nil
}

func (r *FilterRegistry) GetEnabled(config *domain.PlannerConfiguration) []SequenceFilter {
	r.mu.RLock()
	defer r.mu.RUnlock()
	enabledNames := config.GetEnabledFilters()
	var enabled []SequenceFilter
	for _, name := range enabledNames {
		if filter, ok := r.filters[name]; ok {
			enabled = append(enabled, filter)
		}
	}
	return enabled
}

func (r *FilterRegistry) ApplyFilters(sequences []domain.ActionSequence, config *domain.PlannerConfiguration) ([]domain.ActionSequence, error) {
	enabled := r.GetEnabled(config)
	result := sequences
	for _, filter := range enabled {
		params := config.GetFilterParams(filter.Name())
		filtered, err := filter.Filter(result, params)
		if err != nil {
			r.log.Error().Err(err).Str("filter", filter.Name()).Msg("Filter failed")
			continue
		}
		r.log.Debug().Str("filter", filter.Name()).Int("before", len(result)).Int("after", len(filtered)).Msg("Applied filter")
		result = filtered
	}
	return result, nil
}

// NewPopulatedFilterRegistry creates a new filter registry with all filters registered.
func NewPopulatedFilterRegistry(log zerolog.Logger, riskBuilder *optimization.RiskModelBuilder) *FilterRegistry {
	registry := NewFilterRegistry(log)

	// Register all filters
	registry.Register(NewCorrelationAwareFilter(log, riskBuilder))
	registry.Register(NewDiversityFilter(log))
	registry.Register(NewEligibilityFilter(log))
	registry.Register(NewRecentlyTradedFilter(log))

	log.Info().
		Int("filters", len(registry.filters)).
		Msg("Filter registry initialized")

	return registry
}
