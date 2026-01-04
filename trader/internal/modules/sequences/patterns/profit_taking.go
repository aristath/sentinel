package patterns

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// ProfitTakingPattern generates sequences focused on taking profits from winning positions.
type ProfitTakingPattern struct {
	*BasePattern
}

// NewProfitTakingPattern creates a new profit taking pattern generator.
func NewProfitTakingPattern(log zerolog.Logger) *ProfitTakingPattern {
	return &ProfitTakingPattern{
		BasePattern: NewBasePattern(log, "profit_taking"),
	}
}

// Name returns the pattern name.
func (p *ProfitTakingPattern) Name() string {
	return "profit_taking"
}

// Generate creates sequences from profit-taking opportunities.
func (p *ProfitTakingPattern) Generate(
	opportunities domain.OpportunitiesByCategory,
	params map[string]interface{},
) ([]domain.ActionSequence, error) {
	// Parameters
	maxSequences := GetIntParam(params, "max_sequences", 10)
	prioritizeWindfalls := GetBoolParam(params, "prioritize_windfalls", true)

	p.log.Debug().
		Int("max_sequences", maxSequences).
		Bool("prioritize_windfalls", prioritizeWindfalls).
		Msg("Generating profit-taking sequences")

	var sequences []domain.ActionSequence

	// Get profit-taking opportunities
	profitTakingCandidates, ok := opportunities[domain.OpportunityCategoryProfitTaking]
	if !ok || len(profitTakingCandidates) == 0 {
		p.log.Debug().Msg("No profit-taking opportunities found")
		return sequences, nil
	}

	// Separate windfalls from regular profit-taking if requested
	var windfalls []domain.ActionCandidate
	var regular []domain.ActionCandidate

	if prioritizeWindfalls {
		for _, candidate := range profitTakingCandidates {
			isWindfall := false
			for _, tag := range candidate.Tags {
				if tag == "windfall" {
					isWindfall = true
					break
				}
			}
			if isWindfall {
				windfalls = append(windfalls, candidate)
			} else {
				regular = append(regular, candidate)
			}
		}

		p.log.Debug().
			Int("windfalls", len(windfalls)).
			Int("regular", len(regular)).
			Msg("Categorized profit-taking opportunities")
	} else {
		regular = profitTakingCandidates
	}

	// Create sequences - windfalls first, then regular
	count := 0
	for _, candidate := range windfalls {
		if maxSequences > 0 && count >= maxSequences {
			break
		}
		sequence := CreateSequence([]domain.ActionCandidate{candidate}, "profit_taking")
		sequences = append(sequences, sequence)
		count++
	}

	for _, candidate := range regular {
		if maxSequences > 0 && count >= maxSequences {
			break
		}
		sequence := CreateSequence([]domain.ActionCandidate{candidate}, "profit_taking")
		sequences = append(sequences, sequence)
		count++
	}

	p.log.Info().
		Int("sequences", len(sequences)).
		Int("windfalls", len(windfalls)).
		Int("regular", len(regular)).
		Msg("Profit-taking sequences generated")

	return sequences, nil
}
