package patterns

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// MixedStrategyPattern generates sequences mixing different action types.
type MixedStrategyPattern struct {
	*BasePattern
}

func NewMixedStrategyPattern(log zerolog.Logger) *MixedStrategyPattern {
	return &MixedStrategyPattern{BasePattern: NewBasePattern(log, "mixed_strategy")}
}

func (p *MixedStrategyPattern) Name() string {
	return "mixed_strategy"
}

func (p *MixedStrategyPattern) Generate(
	opportunities domain.OpportunitiesByCategory,
	params map[string]interface{},
) ([]domain.ActionSequence, error) {
	maxActions := GetIntParam(params, "max_actions", 3)
	maxSequences := GetIntParam(params, "max_sequences", 5)

	var allCandidates []domain.ActionCandidate
	for _, candidates := range opportunities {
		allCandidates = append(allCandidates, candidates...)
	}

	if len(allCandidates) == 0 {
		return nil, nil
	}

	var sequences []domain.ActionSequence
	for i := 0; i < len(allCandidates) && len(sequences) < maxSequences; i++ {
		end := i + maxActions
		if end > len(allCandidates) {
			end = len(allCandidates)
		}
		if i < end {
			sequence := CreateSequence(allCandidates[i:end], "mixed_strategy")
			sequences = append(sequences, sequence)
		}
	}

	return sequences, nil
}
