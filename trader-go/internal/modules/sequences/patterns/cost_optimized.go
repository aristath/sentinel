package patterns

import (
	"sort"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// CostOptimizedPattern minimizes transaction costs by batching actions.
type CostOptimizedPattern struct {
	*BasePattern
}

func NewCostOptimizedPattern(log zerolog.Logger) *CostOptimizedPattern {
	return &CostOptimizedPattern{BasePattern: NewBasePattern(log, "cost_optimized")}
}

func (p *CostOptimizedPattern) Name() string {
	return "cost_optimized"
}

func (p *CostOptimizedPattern) Generate(
	opportunities domain.OpportunitiesByCategory,
	params map[string]interface{},
) ([]domain.ActionSequence, error) {
	maxActions := GetIntParam(params, "max_actions", 5)

	var allCandidates []domain.ActionCandidate
	for _, candidates := range opportunities {
		allCandidates = append(allCandidates, candidates...)
	}

	sort.Slice(allCandidates, func(i, j int) bool {
		return allCandidates[i].ValueEUR > allCandidates[j].ValueEUR
	})

	end := maxActions
	if end > len(allCandidates) {
		end = len(allCandidates)
	}

	if end == 0 {
		return nil, nil
	}

	sequence := CreateSequence(allCandidates[:end], "cost_optimized")
	return []domain.ActionSequence{sequence}, nil
}

func init() {
	DefaultPatternRegistry.Register(NewCostOptimizedPattern(zerolog.Nop()))
}
