package patterns

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// MarketRegimePattern adjusts strategy based on market regime (bull/bear/neutral).
type MarketRegimePattern struct {
	*BasePattern
}

func NewMarketRegimePattern(log zerolog.Logger) *MarketRegimePattern {
	return &MarketRegimePattern{BasePattern: NewBasePattern(log, "market_regime")}
}

func (p *MarketRegimePattern) Name() string {
	return "market_regime"
}

func (p *MarketRegimePattern) Generate(
	opportunities domain.OpportunitiesByCategory,
	params map[string]interface{},
) ([]domain.ActionSequence, error) {
	regime := "neutral" // Default regime
	if r, ok := params["regime"].(string); ok {
		regime = r
	}
	maxSequences := GetIntParam(params, "max_sequences", 5)

	var sequences []domain.ActionSequence

	switch regime {
	case "bull":
		// In bull market, favor buys and averaging down
		buyOpps, _ := opportunities[domain.OpportunityCategoryOpportunityBuys]
		avgDown, _ := opportunities[domain.OpportunityCategoryAveragingDown]

		allBuys := append(buyOpps, avgDown...)
		for i := 0; i < len(allBuys) && i < maxSequences; i++ {
			sequence := CreateSequence([]domain.ActionCandidate{allBuys[i]}, "market_regime")
			sequences = append(sequences, sequence)
		}

	case "bear":
		// In bear market, favor profit-taking and cash generation
		profitTaking, _ := opportunities[domain.OpportunityCategoryProfitTaking]
		for i := 0; i < len(profitTaking) && i < maxSequences; i++ {
			sequence := CreateSequence([]domain.ActionCandidate{profitTaking[i]}, "market_regime")
			sequences = append(sequences, sequence)
		}

	default: // neutral
		// In neutral market, balance rebalancing
		sells, _ := opportunities[domain.OpportunityCategoryRebalanceSells]
		buys, _ := opportunities[domain.OpportunityCategoryRebalanceBuys]

		for i := 0; i < len(sells) && i < len(buys) && i < maxSequences; i++ {
			actions := []domain.ActionCandidate{sells[i], buys[i]}
			sequence := CreateSequence(actions, "market_regime")
			sequences = append(sequences, sequence)
		}
	}

	return sequences, nil
}

func init() {
	DefaultPatternRegistry.Register(NewMarketRegimePattern(zerolog.Nop()))
}
