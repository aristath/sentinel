package patterns

import (
	"sort"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// AdaptivePattern adapts strategy based on market conditions and opportunity mix.
type AdaptivePattern struct {
	*BasePattern
}

func NewAdaptivePattern(log zerolog.Logger) *AdaptivePattern {
	return &AdaptivePattern{BasePattern: NewBasePattern(log, "adaptive")}
}

func (p *AdaptivePattern) Name() string {
	return "adaptive"
}

func (p *AdaptivePattern) Generate(
	opportunities domain.OpportunitiesByCategory,
	params map[string]interface{},
) ([]domain.ActionSequence, error) {
	maxSequences := GetIntParam(params, "max_sequences", 5)
	adaptiveThreshold := GetFloatParam(params, "adaptive_threshold", 0.7)

	var highPriority []domain.ActionCandidate
	var mediumPriority []domain.ActionCandidate

	for _, candidates := range opportunities {
		for _, c := range candidates {
			if c.Priority >= adaptiveThreshold {
				highPriority = append(highPriority, c)
			} else {
				mediumPriority = append(mediumPriority, c)
			}
		}
	}

	sort.Slice(highPriority, func(i, j int) bool {
		return highPriority[i].Priority > highPriority[j].Priority
	})

	var sequences []domain.ActionSequence

	// Create sequences with high-priority actions first
	for i := 0; i < len(highPriority) && i < maxSequences; i++ {
		var actions []domain.ActionCandidate
		actions = append(actions, highPriority[i])

		// Add complementary medium priority if available
		if len(mediumPriority) > i {
			if highPriority[i].Side == "SELL" && mediumPriority[i].Side == "BUY" {
				actions = append(actions, mediumPriority[i])
			} else if highPriority[i].Side == "BUY" && mediumPriority[i].Side == "SELL" {
				actions = append([]domain.ActionCandidate{mediumPriority[i]}, actions...)
			}
		}

		sequence := CreateSequence(actions, "adaptive")
		sequences = append(sequences, sequence)
	}

	return sequences, nil
}

func init() {
	DefaultPatternRegistry.Register(NewAdaptivePattern(zerolog.Nop()))
}
