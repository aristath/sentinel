package patterns

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// MultiSellPattern generates sequences with multiple sell actions.
type MultiSellPattern struct {
	*BasePattern
}

func NewMultiSellPattern(log zerolog.Logger) *MultiSellPattern {
	return &MultiSellPattern{BasePattern: NewBasePattern(log, "multi_sell")}
}

func (p *MultiSellPattern) Name() string {
	return "multi_sell"
}

func (p *MultiSellPattern) Generate(
	opportunities domain.OpportunitiesByCategory,
	params map[string]interface{},
) ([]domain.ActionSequence, error) {
	maxSells := GetIntParam(params, "max_sells", 3)
	maxSequences := GetIntParam(params, "max_sequences", 5)

	var allSells []domain.ActionCandidate
	for _, candidates := range opportunities {
		for _, c := range candidates {
			if c.Side == "SELL" {
				allSells = append(allSells, c)
			}
		}
	}

	if len(allSells) == 0 {
		return nil, nil
	}

	var sequences []domain.ActionSequence
	for i := 0; i < len(allSells) && i < maxSequences; i++ {
		end := i + maxSells
		if end > len(allSells) {
			end = len(allSells)
		}
		if i < end {
			sequence := CreateSequence(allSells[i:end], "multi_sell")
			sequences = append(sequences, sequence)
		}
	}

	return sequences, nil
}
