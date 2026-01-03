package filters

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

type EligibilityFilter struct {
	*BaseFilter
}

func NewEligibilityFilter(log zerolog.Logger) *EligibilityFilter {
	return &EligibilityFilter{BaseFilter: NewBaseFilter(log, "eligibility")}
}

func (f *EligibilityFilter) Name() string {
	return "eligibility"
}

func (f *EligibilityFilter) Filter(sequences []domain.ActionSequence, params map[string]interface{}) ([]domain.ActionSequence, error) {
	// Filter sequences with ineligible actions
	// Would check against ineligible symbols list from context
	return sequences, nil
}
