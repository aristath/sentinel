package patterns

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// AveragingDownPattern generates sequences for averaging down on underperforming positions.
type AveragingDownPattern struct {
	*BasePattern
}

// NewAveragingDownPattern creates a new averaging down pattern generator.
func NewAveragingDownPattern(log zerolog.Logger) *AveragingDownPattern {
	return &AveragingDownPattern{
		BasePattern: NewBasePattern(log, "averaging_down"),
	}
}

// Name returns the pattern name.
func (p *AveragingDownPattern) Name() string {
	return "averaging_down"
}

// Generate creates averaging-down sequences.
func (p *AveragingDownPattern) Generate(
	opportunities domain.OpportunitiesByCategory,
	params map[string]interface{},
) ([]domain.ActionSequence, error) {
	// Parameters
	maxSequences := GetIntParam(params, "max_sequences", 5)

	p.log.Debug().
		Int("max_sequences", maxSequences).
		Msg("Generating averaging-down sequences")

	var sequences []domain.ActionSequence

	// Get averaging-down opportunities
	averagingDownCandidates, ok := opportunities[domain.OpportunityCategoryAveragingDown]
	if !ok || len(averagingDownCandidates) == 0 {
		p.log.Debug().Msg("No averaging-down opportunities found")
		return sequences, nil
	}

	// Create single-action sequences for each opportunity
	for i, candidate := range averagingDownCandidates {
		if maxSequences > 0 && i >= maxSequences {
			break
		}
		sequence := CreateSequence([]domain.ActionCandidate{candidate}, "averaging_down")
		sequences = append(sequences, sequence)
	}

	p.log.Info().
		Int("sequences", len(sequences)).
		Int("opportunities", len(averagingDownCandidates)).
		Msg("Averaging-down sequences generated")

	return sequences, nil
}

func init() {
	// Auto-register on import
	DefaultPatternRegistry.Register(NewAveragingDownPattern(zerolog.Nop()))
}
