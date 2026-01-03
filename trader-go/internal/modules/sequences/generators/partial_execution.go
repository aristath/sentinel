package generators

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/sequences/patterns"
	"github.com/rs/zerolog"
)

type PartialExecutionGenerator struct {
	*BaseGenerator
}

func NewPartialExecutionGenerator(log zerolog.Logger) *PartialExecutionGenerator {
	return &PartialExecutionGenerator{BaseGenerator: NewBaseGenerator(log, "partial_execution")}
}

func (g *PartialExecutionGenerator) Name() string {
	return "partial_execution"
}

func (g *PartialExecutionGenerator) Generate(sequences []domain.ActionSequence, params map[string]interface{}) ([]domain.ActionSequence, error) {
	result := append([]domain.ActionSequence{}, sequences...)

	for _, seq := range sequences {
		if len(seq.Actions) > 1 {
			// Create partial sequences (first N actions)
			for i := 1; i < len(seq.Actions); i++ {
				partial := patterns.CreateSequence(seq.Actions[:i], "partial_execution")
				result = append(result, partial)
			}
		}
	}

	return result, nil
}
