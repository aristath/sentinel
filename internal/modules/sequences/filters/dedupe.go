package filters

import (
	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// DedupeFilter removes duplicate sequences based on their hash.
// Multiple pattern generators may produce identical sequences (e.g., multi_sell
// and profit_taking both generating single-sell sequences). This filter ensures
// each unique sequence is only evaluated once.
type DedupeFilter struct {
	*BaseFilter
}

// NewDedupeFilter creates a new deduplication filter.
func NewDedupeFilter(log zerolog.Logger) *DedupeFilter {
	return &DedupeFilter{
		BaseFilter: NewBaseFilter(log, "dedupe"),
	}
}

// Name returns the filter name.
func (f *DedupeFilter) Name() string {
	return "dedupe"
}

// Filter removes duplicate sequences, keeping the first occurrence.
// Duplicates are identified by SequenceHash (MD5 of symbol+side+quantity).
// Params: (none currently, reserved for future configuration)
func (f *DedupeFilter) Filter(
	sequences []domain.ActionSequence,
	_ map[string]interface{},
) ([]domain.ActionSequence, error) {
	if len(sequences) == 0 {
		return sequences, nil
	}

	seen := make(map[string]bool)
	var result []domain.ActionSequence
	duplicateCount := 0

	for _, seq := range sequences {
		// Use sequence hash for deduplication
		if seq.SequenceHash == "" {
			// No hash - keep the sequence (shouldn't happen, but be safe)
			result = append(result, seq)
			continue
		}

		if seen[seq.SequenceHash] {
			duplicateCount++
			continue
		}

		seen[seq.SequenceHash] = true
		result = append(result, seq)
	}

	if duplicateCount > 0 {
		f.log.Info().
			Int("input", len(sequences)).
			Int("output", len(result)).
			Int("duplicates_removed", duplicateCount).
			Msg("Deduplicated sequences")
	}

	return result, nil
}
