// Package sequences provides exhaustive sequence generation for trading planning.
package sequences

import (
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"sort"

	"github.com/aristath/sentinel/internal/modules/planning/constraints"
	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// ExhaustiveGenerator generates all valid combinations of opportunities up to a maximum depth.
// It replaces the pattern-based approach with a single comprehensive generator that:
// - Collects all opportunities regardless of category
// - Applies constraint filtering (cooloff, ineligibility, allow_buy/sell)
// - Generates all valid combinations from depth 1 to max_depth
// - Uses order-independent hashing for deduplication
// - Prunes infeasible sequences during generation (cash constraints)
type ExhaustiveGenerator struct {
	log      zerolog.Logger
	enforcer *constraints.Enforcer
}

// NewExhaustiveGenerator creates a new exhaustive sequence generator.
func NewExhaustiveGenerator(log zerolog.Logger, enforcer *constraints.Enforcer) *ExhaustiveGenerator {
	return &ExhaustiveGenerator{
		log:      log.With().Str("component", "exhaustive_generator").Logger(),
		enforcer: enforcer,
	}
}

// GenerationConfig contains parameters for sequence generation.
type GenerationConfig struct {
	MaxDepth        int     // Maximum number of actions per sequence (default: 8)
	MaxSequences    int     // Maximum total sequences to generate (0 = unlimited)
	AvailableCash   float64 // Available cash for feasibility checks
	PruneInfeasible bool    // Whether to prune cash-infeasible sequences during generation
}

// DefaultGenerationConfig returns sensible defaults for generation.
func DefaultGenerationConfig() GenerationConfig {
	return GenerationConfig{
		MaxDepth:        8,
		MaxSequences:    0, // No limit
		AvailableCash:   0,
		PruneInfeasible: true,
	}
}

// Generate creates all valid action sequences from the given opportunities.
// Returns deduplicated sequences sorted by priority.
func (g *ExhaustiveGenerator) Generate(
	opportunities domain.OpportunitiesByCategory,
	ctx *domain.OpportunityContext,
	config GenerationConfig,
) []domain.ActionSequence {
	// Step 1: Collect and filter all opportunities
	allCandidates := g.collectAndFilter(opportunities, ctx)
	if len(allCandidates) == 0 {
		g.log.Debug().Msg("No valid candidates after filtering")
		return nil
	}

	g.log.Info().
		Int("candidates", len(allCandidates)).
		Int("max_depth", config.MaxDepth).
		Msg("Starting exhaustive generation")

	// Step 2: Generate all combinations
	var sequences []domain.ActionSequence
	seen := make(map[string]bool)

	effectiveMaxDepth := config.MaxDepth
	if effectiveMaxDepth > len(allCandidates) {
		effectiveMaxDepth = len(allCandidates)
	}

	// Generate combinations from depth 1 to max_depth
	for depth := 1; depth <= effectiveMaxDepth; depth++ {
		combos := g.generateCombinations(allCandidates, depth)
		for _, combo := range combos {
			// Normalize: Sort SELL before BUY for canonical order
			normalized := g.normalizeSequence(combo)

			// Check for duplicates using order-independent hash
			hash := g.computeSequenceHash(normalized)
			if seen[hash] {
				continue
			}

			// Feasibility check: Can we afford this sequence?
			if config.PruneInfeasible && config.AvailableCash > 0 {
				if !g.checkCashFeasibility(normalized, config.AvailableCash) {
					continue
				}
			}

			seen[hash] = true

			// Create sequence
			seq := domain.ActionSequence{
				Actions:      normalized,
				Priority:     g.computePriority(normalized),
				Depth:        len(normalized),
				PatternType:  "exhaustive",
				SequenceHash: hash,
			}
			sequences = append(sequences, seq)

			// Check max sequences limit
			if config.MaxSequences > 0 && len(sequences) >= config.MaxSequences {
				g.log.Info().
					Int("sequences", len(sequences)).
					Msg("Reached max sequences limit")
				return sequences
			}
		}
	}

	g.log.Info().
		Int("sequences", len(sequences)).
		Int("duplicates_removed", len(seen)-len(sequences)+(len(seen)-len(sequences))).
		Msg("Exhaustive generation complete")

	return sequences
}

// collectAndFilter gathers all opportunities and applies constraint filtering.
func (g *ExhaustiveGenerator) collectAndFilter(
	opportunities domain.OpportunitiesByCategory,
	ctx *domain.OpportunityContext,
) []domain.ActionCandidate {
	var all []domain.ActionCandidate

	// Collect from all categories
	for category, candidates := range opportunities {
		for _, c := range candidates {
			// Fast feasibility check via enforcer
			if g.enforcer != nil {
				feasible, reason := g.enforcer.IsActionFeasible(c, ctx)
				if !feasible {
					g.log.Debug().
						Str("symbol", c.Symbol).
						Str("side", c.Side).
						Str("category", string(category)).
						Str("reason", reason).
						Msg("Candidate filtered")
					continue
				}
			}
			all = append(all, c)
		}
	}

	// Sort by priority (highest first) for better sequence quality
	sort.Slice(all, func(i, j int) bool {
		return all[i].Priority > all[j].Priority
	})

	return all
}

// generateCombinations returns all k-element subsets of items (n choose k).
// Uses standard combinatorial algorithm.
func (g *ExhaustiveGenerator) generateCombinations(items []domain.ActionCandidate, k int) [][]domain.ActionCandidate {
	n := len(items)
	if k > n || k <= 0 {
		return nil
	}

	var result [][]domain.ActionCandidate
	indices := make([]int, k)

	// Initialize indices to [0, 1, 2, ..., k-1]
	for i := range indices {
		indices[i] = i
	}

	for {
		// Copy current combination
		combo := make([]domain.ActionCandidate, k)
		for i, idx := range indices {
			combo[i] = items[idx]
		}
		result = append(result, combo)

		// Find rightmost index that can be incremented
		i := k - 1
		for i >= 0 && indices[i] == n-k+i {
			i--
		}
		if i < 0 {
			break
		}

		// Increment and reset subsequent indices
		indices[i]++
		for j := i + 1; j < k; j++ {
			indices[j] = indices[j-1] + 1
		}
	}

	return result
}

// normalizeSequence sorts actions: SELL first, then BUY.
// Within each group, sort by ISIN for deterministic ordering.
// This ensures "SELL A + BUY B" and "BUY B + SELL A" have the same hash.
func (g *ExhaustiveGenerator) normalizeSequence(actions []domain.ActionCandidate) []domain.ActionCandidate {
	result := make([]domain.ActionCandidate, len(actions))
	copy(result, actions)

	sort.Slice(result, func(i, j int) bool {
		// SELL comes before BUY
		if result[i].Side != result[j].Side {
			return result[i].Side == "SELL"
		}
		// Within same side, sort by ISIN
		return result[i].ISIN < result[j].ISIN
	})

	return result
}

// computeSequenceHash creates a deterministic MD5 hash for a sequence.
// The sequence must be normalized first for order-independent comparison.
func (g *ExhaustiveGenerator) computeSequenceHash(actions []domain.ActionCandidate) string {
	type tuple struct {
		Symbol   string `json:"symbol"`
		Side     string `json:"side"`
		Quantity int    `json:"quantity"`
	}

	tuples := make([]tuple, len(actions))
	for i, action := range actions {
		tuples[i] = tuple{
			Symbol:   action.Symbol,
			Side:     action.Side,
			Quantity: action.Quantity,
		}
	}

	jsonBytes, err := json.Marshal(tuples)
	if err != nil {
		return ""
	}

	hash := md5.Sum(jsonBytes)
	return hex.EncodeToString(hash[:])
}

// computePriority calculates aggregate priority for a sequence.
// Uses average of individual action priorities.
func (g *ExhaustiveGenerator) computePriority(actions []domain.ActionCandidate) float64 {
	if len(actions) == 0 {
		return 0
	}

	var total float64
	for _, a := range actions {
		total += a.Priority
	}
	return total / float64(len(actions))
}

// checkCashFeasibility performs a quick check if sequence is cash-feasible.
// Assumes sequence is normalized (SELL before BUY).
func (g *ExhaustiveGenerator) checkCashFeasibility(actions []domain.ActionCandidate, availableCash float64) bool {
	cash := availableCash

	for _, action := range actions {
		if action.Side == "SELL" {
			cash += action.ValueEUR
		} else { // BUY
			if action.ValueEUR > cash {
				return false
			}
			cash -= action.ValueEUR
		}
	}

	return true
}
