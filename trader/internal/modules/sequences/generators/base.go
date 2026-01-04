package generators

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// SequenceGenerator expands or modifies action sequences.
type SequenceGenerator interface {
	Name() string
	Generate(sequences []domain.ActionSequence, params map[string]interface{}) ([]domain.ActionSequence, error)
}

type BaseGenerator struct {
	log zerolog.Logger
}

func NewBaseGenerator(log zerolog.Logger, name string) *BaseGenerator {
	return &BaseGenerator{log: log.With().Str("generator", name).Logger()}
}
