package filters

import (
	"testing"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestDedupeFilter_RemovesDuplicates(t *testing.T) {
	filter := NewDedupeFilter(zerolog.Nop())

	sequences := []domain.ActionSequence{
		{SequenceHash: "hash1", PatternType: "multi_sell"},
		{SequenceHash: "hash2", PatternType: "profit_taking"},
		{SequenceHash: "hash1", PatternType: "profit_taking"}, // Duplicate of first
		{SequenceHash: "hash3", PatternType: "rebalance"},
		{SequenceHash: "hash2", PatternType: "mixed"}, // Duplicate of second
	}

	result, err := filter.Filter(sequences, nil)

	require.NoError(t, err)
	assert.Equal(t, 3, len(result), "Should remove 2 duplicates")

	// Verify we kept the first occurrence of each unique hash
	hashes := make([]string, len(result))
	for i, seq := range result {
		hashes[i] = seq.SequenceHash
	}
	assert.Contains(t, hashes, "hash1")
	assert.Contains(t, hashes, "hash2")
	assert.Contains(t, hashes, "hash3")

	// Verify we kept the first occurrence (multi_sell, not profit_taking)
	assert.Equal(t, "multi_sell", result[0].PatternType, "Should keep first occurrence")
}

func TestDedupeFilter_NoDuplicates(t *testing.T) {
	filter := NewDedupeFilter(zerolog.Nop())

	sequences := []domain.ActionSequence{
		{SequenceHash: "hash1"},
		{SequenceHash: "hash2"},
		{SequenceHash: "hash3"},
	}

	result, err := filter.Filter(sequences, nil)

	require.NoError(t, err)
	assert.Equal(t, 3, len(result), "No duplicates to remove")
}

func TestDedupeFilter_EmptySequences(t *testing.T) {
	filter := NewDedupeFilter(zerolog.Nop())

	result, err := filter.Filter([]domain.ActionSequence{}, nil)

	require.NoError(t, err)
	assert.Empty(t, result)
}

func TestDedupeFilter_NilSequences(t *testing.T) {
	filter := NewDedupeFilter(zerolog.Nop())

	result, err := filter.Filter(nil, nil)

	require.NoError(t, err)
	assert.Nil(t, result)
}

func TestDedupeFilter_EmptyHashPreserved(t *testing.T) {
	filter := NewDedupeFilter(zerolog.Nop())

	// Sequences without hashes should be preserved (edge case)
	sequences := []domain.ActionSequence{
		{SequenceHash: "hash1"},
		{SequenceHash: ""},      // Empty hash - should be kept
		{SequenceHash: "hash1"}, // Duplicate
		{SequenceHash: ""},      // Another empty hash - should also be kept
	}

	result, err := filter.Filter(sequences, nil)

	require.NoError(t, err)
	// Should have: hash1, empty, empty (hash1 duplicate removed)
	assert.Equal(t, 3, len(result))
}

func TestDedupeFilter_Name(t *testing.T) {
	filter := NewDedupeFilter(zerolog.Nop())
	assert.Equal(t, "dedupe", filter.Name())
}
