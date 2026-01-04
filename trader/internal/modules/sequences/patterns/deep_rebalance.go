package patterns

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// DeepRebalancePattern generates aggressive rebalancing sequences.
type DeepRebalancePattern struct {
	*BasePattern
}

func NewDeepRebalancePattern(log zerolog.Logger) *DeepRebalancePattern {
	return &DeepRebalancePattern{BasePattern: NewBasePattern(log, "deep_rebalance")}
}

func (p *DeepRebalancePattern) Name() string {
	return "deep_rebalance"
}

func (p *DeepRebalancePattern) Generate(
	opportunities domain.OpportunitiesByCategory,
	params map[string]interface{},
) ([]domain.ActionSequence, error) {
	maxSequences := GetIntParam(params, "max_sequences", 3)

	sells, _ := opportunities[domain.OpportunityCategoryRebalanceSells]
	buys, _ := opportunities[domain.OpportunityCategoryRebalanceBuys]

	var sequences []domain.ActionSequence
	for i := 0; i < len(sells) && i < maxSequences; i++ {
		var actions []domain.ActionCandidate
		actions = append(actions, sells[i])
		if i < len(buys) {
			actions = append(actions, buys[i])
		}
		sequence := CreateSequence(actions, "deep_rebalance")
		sequences = append(sequences, sequence)
	}

	return sequences, nil
}
