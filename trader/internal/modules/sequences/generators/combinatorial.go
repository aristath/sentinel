package generators

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/sequences/patterns"
	"github.com/rs/zerolog"
)

type CombinatorialGenerator struct {
	*BaseGenerator
}

func NewCombinatorialGenerator(log zerolog.Logger) *CombinatorialGenerator {
	return &CombinatorialGenerator{BaseGenerator: NewBaseGenerator(log, "combinatorial")}
}

func (g *CombinatorialGenerator) Name() string {
	return "combinatorial"
}

func (g *CombinatorialGenerator) Generate(sequences []domain.ActionSequence, params map[string]interface{}) ([]domain.ActionSequence, error) {
	maxCombinations := 100
	if val, ok := params["max_combinations"].(float64); ok {
		maxCombinations = int(val)
	}

	var result []domain.ActionSequence
	result = append(result, sequences...)

	// Create pairwise combinations
	for i := 0; i < len(sequences) && len(result) < maxCombinations; i++ {
		for j := i + 1; j < len(sequences) && len(result) < maxCombinations; j++ {
			combined := append(sequences[i].Actions, sequences[j].Actions...)
			seq := patterns.CreateSequence(combined, "combinatorial")
			result = append(result, seq)
		}
	}

	return result, nil
}
