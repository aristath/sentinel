package patterns

import (
	"math"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// MarketRegimePattern adjusts strategy continuously based on a regime score in [-1,1].
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
	regimeScore := GetFloatParam(params, "regime_score", 0.0)
	if regimeScore > 1.0 {
		regimeScore = 1.0
	} else if regimeScore < -1.0 {
		regimeScore = -1.0
	}
	maxSequences := GetIntParam(params, "max_sequences", 5)

	var sequences []domain.ActionSequence

	buyTilt := math.Max(0.0, regimeScore)
	sellTilt := math.Max(0.0, -regimeScore)
	neutralTilt := 1.0 - math.Abs(regimeScore)

	// Allocate sequence budget proportionally. Keep it simple and deterministic.
	remaining := maxSequences
	nBuy := int(math.Round(float64(maxSequences) * buyTilt))
	if nBuy > remaining {
		nBuy = remaining
	}
	remaining -= nBuy

	nSell := int(math.Round(float64(maxSequences) * sellTilt))
	if nSell > remaining {
		nSell = remaining
	}
	remaining -= nSell

	// Whatever is left goes to neutral rebalancing.
	nNeutral := remaining
	_ = neutralTilt // documented intention; allocation is derived from remaining after buy/sell

	// Buy-style sequences: opportunity buys + averaging down.
	if nBuy > 0 {
		buyOpps := opportunities[domain.OpportunityCategoryOpportunityBuys]
		avgDown := opportunities[domain.OpportunityCategoryAveragingDown]
		allBuys := append(buyOpps, avgDown...)
		for i := 0; i < len(allBuys) && i < nBuy; i++ {
			sequences = append(sequences, CreateSequence([]domain.ActionCandidate{allBuys[i]}, "market_regime"))
		}
	}

	// Sell-style sequences: profit taking.
	if nSell > 0 {
		profitTaking := opportunities[domain.OpportunityCategoryProfitTaking]
		for i := 0; i < len(profitTaking) && i < nSell; i++ {
			sequences = append(sequences, CreateSequence([]domain.ActionCandidate{profitTaking[i]}, "market_regime"))
		}
	}

	// Neutral sequences: paired rebalance sells + buys.
	if nNeutral > 0 {
		sells := opportunities[domain.OpportunityCategoryRebalanceSells]
		buys := opportunities[domain.OpportunityCategoryRebalanceBuys]
		for i := 0; i < len(sells) && i < len(buys) && i < nNeutral; i++ {
			actions := []domain.ActionCandidate{sells[i], buys[i]}
			sequences = append(sequences, CreateSequence(actions, "market_regime"))
		}
	}

	return sequences, nil
}
