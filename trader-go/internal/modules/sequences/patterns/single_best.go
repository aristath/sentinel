package patterns

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// SingleBestPattern generates a single sequence containing only the highest-priority opportunity.
type SingleBestPattern struct {
	*BasePattern
}

// NewSingleBestPattern creates a new single best pattern generator.
func NewSingleBestPattern(log zerolog.Logger) *SingleBestPattern {
	return &SingleBestPattern{
		BasePattern: NewBasePattern(log, "single_best"),
	}
}

// Name returns the pattern name.
func (p *SingleBestPattern) Name() string {
	return "single_best"
}

// Generate creates a single sequence with the best opportunity.
func (p *SingleBestPattern) Generate(
	opportunities domain.OpportunitiesByCategory,
	params map[string]interface{},
) ([]domain.ActionSequence, error) {
	p.log.Debug().Msg("Generating single-best sequence")

	var sequences []domain.ActionSequence

	// Find the single best opportunity across all categories
	var bestCandidate *domain.ActionCandidate
	var bestPriority float64

	for category, candidates := range opportunities {
		for i := range candidates {
			if bestCandidate == nil || candidates[i].Priority > bestPriority {
				bestCandidate = &candidates[i]
				bestPriority = candidates[i].Priority
			}
		}
		p.log.Debug().
			Str("category", string(category)).
			Int("candidates", len(candidates)).
			Msg("Checked category")
	}

	if bestCandidate == nil {
		p.log.Debug().Msg("No opportunities found")
		return sequences, nil
	}

	p.log.Info().
		Str("symbol", bestCandidate.Symbol).
		Str("side", bestCandidate.Side).
		Float64("priority", bestCandidate.Priority).
		Msg("Best opportunity identified")

	// Create single sequence with best candidate
	sequence := CreateSequence([]domain.ActionCandidate{*bestCandidate}, "single_best")
	sequences = append(sequences, sequence)

	return sequences, nil
}

func init() {
	// Auto-register on import
	DefaultPatternRegistry.Register(NewSingleBestPattern(zerolog.Nop()))
}
