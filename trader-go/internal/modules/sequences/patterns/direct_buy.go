package patterns

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// DirectBuyPattern generates sequences that directly execute buy opportunities.
type DirectBuyPattern struct {
	*BasePattern
}

// NewDirectBuyPattern creates a new direct buy pattern generator.
func NewDirectBuyPattern(log zerolog.Logger) *DirectBuyPattern {
	return &DirectBuyPattern{
		BasePattern: NewBasePattern(log, "direct_buy"),
	}
}

// Name returns the pattern name.
func (p *DirectBuyPattern) Name() string {
	return "direct_buy"
}

// Generate creates sequences from buy opportunities.
func (p *DirectBuyPattern) Generate(
	opportunities domain.OpportunitiesByCategory,
	params map[string]interface{},
) ([]domain.ActionSequence, error) {
	// Parameters
	maxSequences := GetIntParam(params, "max_sequences", 10)
	singleActionOnly := GetBoolParam(params, "single_action_only", true)

	p.log.Debug().
		Int("max_sequences", maxSequences).
		Bool("single_action_only", singleActionOnly).
		Msg("Generating direct buy sequences")

	var sequences []domain.ActionSequence

	// Collect all buy opportunities
	var buyOpportunities []domain.ActionCandidate
	for category, candidates := range opportunities {
		for _, candidate := range candidates {
			if candidate.Side == "BUY" {
				buyOpportunities = append(buyOpportunities, candidate)
			}
		}
		p.log.Debug().
			Str("category", string(category)).
			Int("buy_candidates", len(buyOpportunities)).
			Msg("Collected buy candidates")
	}

	if len(buyOpportunities) == 0 {
		p.log.Debug().Msg("No buy opportunities found")
		return sequences, nil
	}

	// Create sequences
	if singleActionOnly {
		// Create one sequence per buy opportunity
		for i, candidate := range buyOpportunities {
			if maxSequences > 0 && i >= maxSequences {
				break
			}
			sequence := CreateSequence([]domain.ActionCandidate{candidate}, "direct_buy")
			sequences = append(sequences, sequence)
		}
	} else {
		// Create multi-action sequences (combinations)
		// For now, just create single-action sequences
		// Multi-action will be handled by combinatorial generators
		for i, candidate := range buyOpportunities {
			if maxSequences > 0 && i >= maxSequences {
				break
			}
			sequence := CreateSequence([]domain.ActionCandidate{candidate}, "direct_buy")
			sequences = append(sequences, sequence)
		}
	}

	p.log.Info().
		Int("sequences", len(sequences)).
		Int("buy_opportunities", len(buyOpportunities)).
		Msg("Direct buy sequences generated")

	return sequences, nil
}

func init() {
	// Auto-register on import
	DefaultPatternRegistry.Register(NewDirectBuyPattern(zerolog.Nop()))
}
