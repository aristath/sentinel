package patterns

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// CashGenerationPattern focuses on generating cash through sells.
type CashGenerationPattern struct {
	*BasePattern
}

func NewCashGenerationPattern(log zerolog.Logger) *CashGenerationPattern {
	return &CashGenerationPattern{BasePattern: NewBasePattern(log, "cash_generation")}
}

func (p *CashGenerationPattern) Name() string {
	return "cash_generation"
}

func (p *CashGenerationPattern) Generate(
	opportunities domain.OpportunitiesByCategory,
	params map[string]interface{},
) ([]domain.ActionSequence, error) {
	maxSells := GetIntParam(params, "max_sells", 5)

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

	end := maxSells
	if end > len(allSells) {
		end = len(allSells)
	}

	sequence := CreateSequence(allSells[:end], "cash_generation")
	return []domain.ActionSequence{sequence}, nil
}
