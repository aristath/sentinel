package patterns

import (
	"sort"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// OpportunityFirstPattern prioritizes highest-scoring opportunities first.
type OpportunityFirstPattern struct {
	*BasePattern
}

func NewOpportunityFirstPattern(log zerolog.Logger) *OpportunityFirstPattern {
	return &OpportunityFirstPattern{BasePattern: NewBasePattern(log, "opportunity_first")}
}

func (p *OpportunityFirstPattern) Name() string {
	return "opportunity_first"
}

func (p *OpportunityFirstPattern) Generate(
	opportunities domain.OpportunitiesByCategory,
	params map[string]interface{},
) ([]domain.ActionSequence, error) {
	maxSequences := GetIntParam(params, "max_sequences", 10)

	var allCandidates []domain.ActionCandidate
	for _, candidates := range opportunities {
		allCandidates = append(allCandidates, candidates...)
	}

	sort.Slice(allCandidates, func(i, j int) bool {
		return allCandidates[i].Priority > allCandidates[j].Priority
	})

	var sequences []domain.ActionSequence
	for i := 0; i < len(allCandidates) && i < maxSequences; i++ {
		sequence := CreateSequence([]domain.ActionCandidate{allCandidates[i]}, "opportunity_first")
		sequences = append(sequences, sequence)
	}

	return sequences, nil
}

func init() {
	DefaultPatternRegistry.Register(NewOpportunityFirstPattern(zerolog.Nop()))
}
