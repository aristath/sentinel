package patterns

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// RebalancePattern generates sequences that rebalance the portfolio by selling overweight
// and buying underweight positions.
type RebalancePattern struct {
	*BasePattern
}

// NewRebalancePattern creates a new rebalance pattern generator.
func NewRebalancePattern(log zerolog.Logger) *RebalancePattern {
	return &RebalancePattern{
		BasePattern: NewBasePattern(log, "rebalance"),
	}
}

// Name returns the pattern name.
func (p *RebalancePattern) Name() string {
	return "rebalance"
}

// Generate creates rebalancing sequences.
func (p *RebalancePattern) Generate(
	opportunities domain.OpportunitiesByCategory,
	params map[string]interface{},
) ([]domain.ActionSequence, error) {
	// Parameters
	maxSequences := GetIntParam(params, "max_sequences", 5)
	sellFirst := GetBoolParam(params, "sell_first", true) // Sell before buy for cash generation

	p.log.Debug().
		Int("max_sequences", maxSequences).
		Bool("sell_first", sellFirst).
		Msg("Generating rebalance sequences")

	var sequences []domain.ActionSequence

	// Get rebalance opportunities
	rebalanceSells, hasSells := opportunities[domain.OpportunityCategoryRebalanceSells]
	rebalanceBuys, hasBuys := opportunities[domain.OpportunityCategoryRebalanceBuys]

	if !hasSells && !hasBuys {
		p.log.Debug().Msg("No rebalance opportunities found")
		return sequences, nil
	}

	p.log.Debug().
		Int("sells", len(rebalanceSells)).
		Int("buys", len(rebalanceBuys)).
		Msg("Rebalance opportunities")

	// Create sell-only sequences
	for i, sellCandidate := range rebalanceSells {
		if maxSequences > 0 && i >= maxSequences {
			break
		}
		sequence := CreateSequence([]domain.ActionCandidate{sellCandidate}, "rebalance")
		sequences = append(sequences, sequence)
	}

	// Create buy-only sequences
	for i, buyCandidate := range rebalanceBuys {
		if maxSequences > 0 && i >= maxSequences {
			break
		}
		sequence := CreateSequence([]domain.ActionCandidate{buyCandidate}, "rebalance")
		sequences = append(sequences, sequence)
	}

	// Create combined sell-then-buy sequences
	if hasSells && hasBuys {
		count := 0
		for _, sellCandidate := range rebalanceSells {
			for _, buyCandidate := range rebalanceBuys {
				if maxSequences > 0 && count >= maxSequences {
					break
				}

				var actions []domain.ActionCandidate
				if sellFirst {
					actions = []domain.ActionCandidate{sellCandidate, buyCandidate}
				} else {
					actions = []domain.ActionCandidate{buyCandidate, sellCandidate}
				}

				sequence := CreateSequence(actions, "rebalance")
				sequences = append(sequences, sequence)
				count++
			}
			if maxSequences > 0 && count >= maxSequences {
				break
			}
		}
	}

	p.log.Info().
		Int("sequences", len(sequences)).
		Msg("Rebalance sequences generated")

	return sequences, nil
}
