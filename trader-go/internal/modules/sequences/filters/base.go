package filters

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

type SequenceFilter interface {
	Name() string
	Filter(sequences []domain.ActionSequence, params map[string]interface{}) ([]domain.ActionSequence, error)
}

type BaseFilter struct {
	log zerolog.Logger
}

func NewBaseFilter(log zerolog.Logger, name string) *BaseFilter {
	return &BaseFilter{log: log.With().Str("filter", name).Logger()}
}
