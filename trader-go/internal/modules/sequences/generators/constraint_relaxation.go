package generators

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

type ConstraintRelaxationGenerator struct {
	*BaseGenerator
}

func NewConstraintRelaxationGenerator(log zerolog.Logger) *ConstraintRelaxationGenerator {
	return &ConstraintRelaxationGenerator{BaseGenerator: NewBaseGenerator(log, "constraint_relaxation")}
}

func (g *ConstraintRelaxationGenerator) Name() string {
	return "constraint_relaxation"
}

func (g *ConstraintRelaxationGenerator) Generate(sequences []domain.ActionSequence, params map[string]interface{}) ([]domain.ActionSequence, error) {
	// Pass through - constraint relaxation would be applied at evaluation time
	return sequences, nil
}
