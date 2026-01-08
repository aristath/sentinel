// Package sequences provides trading sequence generation functionality.
package sequences

import (
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sort"

	"github.com/aristath/sentinel/internal/modules/optimization"
	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/sequences/filters"
	"github.com/aristath/sentinel/internal/modules/sequences/generators"
	"github.com/aristath/sentinel/internal/modules/sequences/patterns"
	"github.com/rs/zerolog"
)

type Service struct {
	patternRegistry   *patterns.PatternRegistry
	generatorRegistry *generators.GeneratorRegistry
	filterRegistry    *filters.FilterRegistry
	log               zerolog.Logger
}

func NewService(log zerolog.Logger, riskBuilder *optimization.RiskModelBuilder) *Service {
	return &Service{
		patternRegistry:   patterns.NewPopulatedPatternRegistry(log),
		generatorRegistry: generators.NewPopulatedGeneratorRegistry(log),
		filterRegistry:    filters.NewPopulatedFilterRegistry(log, riskBuilder),
		log:               log.With().Str("module", "sequences").Logger(),
	}
}

func (s *Service) GenerateSequences(
	opportunities domain.OpportunitiesByCategory,
	config *domain.PlannerConfiguration,
) ([]domain.ActionSequence, error) {
	// Generate from patterns
	sequences, err := s.patternRegistry.GenerateSequences(opportunities, config)
	if err != nil {
		return nil, fmt.Errorf("failed to generate sequences from patterns: %w", err)
	}

	// Apply generators
	sequences, err = s.generatorRegistry.ApplyGenerators(sequences, config)
	if err != nil {
		return nil, fmt.Errorf("failed to apply generators: %w", err)
	}

	// Apply filters
	sequences, err = s.filterRegistry.ApplyFilters(sequences, config)
	if err != nil {
		return nil, fmt.Errorf("failed to apply filters: %w", err)
	}

	// Post-process: Ensure SELL actions come before BUY actions in all sequences
	// This is critical for cash generation - we need to sell first to generate cash for buys
	sequences = s.ensureSellBeforeBuy(sequences)

	s.log.Info().Int("final_sequences", len(sequences)).Msg("Sequence generation complete")
	return sequences, nil
}

// ensureSellBeforeBuy sorts actions within each sequence to ensure SELL actions
// come before BUY actions. This is architecturally important because:
// 1. SELL actions generate cash needed for BUY actions
// 2. Combinatorial generators may combine sequences in any order
// 3. This ensures all sequences have proper execution order regardless of source
func (s *Service) ensureSellBeforeBuy(sequences []domain.ActionSequence) []domain.ActionSequence {
	result := make([]domain.ActionSequence, len(sequences))

	for i, seq := range sequences {
		// Create a copy of actions to avoid mutating the original
		actions := make([]domain.ActionCandidate, len(seq.Actions))
		copy(actions, seq.Actions)

		// Sort actions: SELL first, then BUY
		// Within each group, maintain relative order (stable sort)
		sort.SliceStable(actions, func(i, j int) bool {
			// SELL actions come before BUY actions
			if actions[i].Side == "SELL" && actions[j].Side == "BUY" {
				return true
			}
			if actions[i].Side == "BUY" && actions[j].Side == "SELL" {
				return false
			}
			// If same side, maintain original order (stable sort)
			return false
		})

		// Regenerate sequence hash since order changed
		sequenceHash := s.generateSequenceHash(actions)

		// Create new sequence with sorted actions
		result[i] = domain.ActionSequence{
			Actions:      actions,
			Priority:     seq.Priority,
			Depth:        len(actions),
			PatternType:  seq.PatternType,
			SequenceHash: sequenceHash,
		}
	}

	return result
}

// generateSequenceHash creates a deterministic MD5 hash for a sequence.
// Matches evaluation service hashSequence() and legacy Python implementation.
// Based on: (symbol, side, quantity) tuples, order-dependent
func (s *Service) generateSequenceHash(actions []domain.ActionCandidate) string {
	type tuple struct {
		Symbol   string `json:"symbol"`
		Side     string `json:"side"`
		Quantity int    `json:"quantity"`
	}

	// Create tuples matching Python: [(c.symbol, c.side, c.quantity) for c in sequence]
	tuples := make([]tuple, len(actions))
	for i, action := range actions {
		tuples[i] = tuple{
			Symbol:   action.Symbol,
			Side:     action.Side,
			Quantity: action.Quantity,
		}
	}

	// JSON marshal (Go's json.Marshal preserves order by default, like sort_keys=False)
	jsonBytes, err := json.Marshal(tuples)
	if err != nil {
		// Fallback: should not happen, but handle gracefully
		return ""
	}

	// MD5 hash and return hex digest (matches hashlib.md5().hexdigest())
	hash := md5.Sum(jsonBytes)
	return hex.EncodeToString(hash[:])
}
