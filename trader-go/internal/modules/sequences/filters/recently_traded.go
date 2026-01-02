package filters

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

type RecentlyTradedFilter struct {
	*BaseFilter
}

func NewRecentlyTradedFilter(log zerolog.Logger) *RecentlyTradedFilter {
	return &RecentlyTradedFilter{BaseFilter: NewBaseFilter(log, "recently_traded")}
}

func (f *RecentlyTradedFilter) Name() string {
	return "recently_traded"
}

func (f *RecentlyTradedFilter) Filter(sequences []domain.ActionSequence, params map[string]interface{}) ([]domain.ActionSequence, error) {
	// Filter sequences with recently traded symbols
	// Would check against recently bought/sold maps from context
	return sequences, nil
}

func init() {
	DefaultFilterRegistry.Register(NewRecentlyTradedFilter(zerolog.Nop()))
}
