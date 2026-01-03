package generators

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/sequences/patterns"
	"github.com/rs/zerolog"
)

type EnhancedCombinatorialGenerator struct {
	*BaseGenerator
}

func NewEnhancedCombinatorialGenerator(log zerolog.Logger) *EnhancedCombinatorialGenerator {
	return &EnhancedCombinatorialGenerator{BaseGenerator: NewBaseGenerator(log, "enhanced_combinatorial")}
}

func (g *EnhancedCombinatorialGenerator) Name() string {
	return "enhanced_combinatorial"
}

func (g *EnhancedCombinatorialGenerator) Generate(sequences []domain.ActionSequence, params map[string]interface{}) ([]domain.ActionSequence, error) {
	maxDepth := 3
	if val, ok := params["max_depth"].(float64); ok {
		maxDepth = int(val)
	}

	result := append([]domain.ActionSequence{}, sequences...)

	// Create combinations up to maxDepth
	for depth := 2; depth <= maxDepth && len(result) < 200; depth++ {
		g.generateDepth(sequences, depth, &result, 200)
	}

	return result, nil
}

func (g *EnhancedCombinatorialGenerator) generateDepth(sequences []domain.ActionSequence, depth int, result *[]domain.ActionSequence, max int) {
	if depth == 1 {
		return
	}

	for i := 0; i < len(sequences) && len(*result) < max; i++ {
		for j := i + 1; j < len(sequences) && len(*result) < max; j++ {
			combined := append(sequences[i].Actions, sequences[j].Actions...)
			seq := patterns.CreateSequence(combined, "enhanced_combinatorial")
			*result = append(*result, seq)
		}
	}
}
