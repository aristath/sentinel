package filters

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

type DiversityFilter struct {
	*BaseFilter
}

func NewDiversityFilter(log zerolog.Logger) *DiversityFilter {
	return &DiversityFilter{BaseFilter: NewBaseFilter(log, "diversity")}
}

func (f *DiversityFilter) Name() string {
	return "diversity"
}

func (f *DiversityFilter) Filter(sequences []domain.ActionSequence, params map[string]interface{}) ([]domain.ActionSequence, error) {
	minDiversity := 0.5
	if val, ok := params["min_diversity_score"].(float64); ok {
		minDiversity = val
	}

	var result []domain.ActionSequence
	for _, seq := range sequences {
		// Simple diversity check: count unique symbols
		symbols := make(map[string]bool)
		for _, action := range seq.Actions {
			symbols[action.Symbol] = true
		}
		diversity := float64(len(symbols)) / float64(len(seq.Actions))
		if diversity >= minDiversity {
			result = append(result, seq)
		}
	}

	return result, nil
}
