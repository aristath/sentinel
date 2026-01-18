package planning

import (
	"testing"

	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestInMemoryRecommendationRepository_StoreRejectedSequences(t *testing.T) {
	repo := NewInMemoryRecommendationRepository(zerolog.Nop())

	rejectedSequences := []planningdomain.RejectedSequence{
		{
			Rank:     2,
			Actions:  []planningdomain.ActionCandidate{{Symbol: "AAPL", Side: "BUY", Quantity: 10}},
			Score:    0.843,
			Feasible: true,
			Reason:   "lower_score",
		},
		{
			Rank:     3,
			Actions:  []planningdomain.ActionCandidate{{Symbol: "MSFT", Side: "BUY", Quantity: 5}},
			Score:    0.841,
			Feasible: true,
			Reason:   "lower_score",
		},
		{
			Rank:     4,
			Actions:  []planningdomain.ActionCandidate{{Symbol: "NVDA", Side: "BUY", Quantity: 100}},
			Score:    0.412,
			Feasible: false,
			Reason:   "insufficient_cash",
		},
	}

	portfolioHash := "test-hash-123"
	err := repo.StoreRejectedSequences(rejectedSequences, portfolioHash)
	require.NoError(t, err)

	// Retrieve and verify
	retrieved := repo.GetRejectedSequences(portfolioHash)
	require.NotNil(t, retrieved)
	assert.Len(t, retrieved, 3)
	assert.Equal(t, 2, retrieved[0].Rank)
	assert.Equal(t, "AAPL", retrieved[0].Actions[0].Symbol)
	assert.Equal(t, 0.843, retrieved[0].Score)
	assert.True(t, retrieved[0].Feasible)
	assert.Equal(t, "lower_score", retrieved[0].Reason)
}

func TestInMemoryRecommendationRepository_GetRejectedSequences_NotFound(t *testing.T) {
	repo := NewInMemoryRecommendationRepository(zerolog.Nop())

	// Get non-existent rejected sequences
	retrieved := repo.GetRejectedSequences("nonexistent-hash")
	assert.Nil(t, retrieved)
}

func TestInMemoryRecommendationRepository_StoreRejectedSequences_Overwrite(t *testing.T) {
	repo := NewInMemoryRecommendationRepository(zerolog.Nop())
	portfolioHash := "test-hash-123"

	// Store initial sequences
	initial := []planningdomain.RejectedSequence{
		{Rank: 2, Score: 0.5, Feasible: true, Reason: "lower_score"},
	}
	err := repo.StoreRejectedSequences(initial, portfolioHash)
	require.NoError(t, err)

	// Store new sequences (should overwrite)
	updated := []planningdomain.RejectedSequence{
		{Rank: 2, Score: 0.8, Feasible: true, Reason: "lower_score"},
		{Rank: 3, Score: 0.7, Feasible: true, Reason: "lower_score"},
	}
	err = repo.StoreRejectedSequences(updated, portfolioHash)
	require.NoError(t, err)

	// Verify overwrite
	retrieved := repo.GetRejectedSequences(portfolioHash)
	assert.Len(t, retrieved, 2)
	assert.Equal(t, 0.8, retrieved[0].Score)
}

func TestInMemoryRecommendationRepository_GetRejectedSequences_MultipleHashes(t *testing.T) {
	repo := NewInMemoryRecommendationRepository(zerolog.Nop())

	// Store sequences for different portfolio hashes
	hash1 := "hash-1"
	hash2 := "hash-2"

	sequences1 := []planningdomain.RejectedSequence{
		{Rank: 2, Score: 0.5, Feasible: true, Reason: "lower_score"},
	}
	sequences2 := []planningdomain.RejectedSequence{
		{Rank: 2, Score: 0.9, Feasible: false, Reason: "insufficient_cash"},
		{Rank: 3, Score: 0.8, Feasible: true, Reason: "lower_score"},
	}

	err := repo.StoreRejectedSequences(sequences1, hash1)
	require.NoError(t, err)
	err = repo.StoreRejectedSequences(sequences2, hash2)
	require.NoError(t, err)

	// Verify each hash has its own data
	retrieved1 := repo.GetRejectedSequences(hash1)
	retrieved2 := repo.GetRejectedSequences(hash2)

	assert.Len(t, retrieved1, 1)
	assert.Equal(t, 0.5, retrieved1[0].Score)

	assert.Len(t, retrieved2, 2)
	assert.Equal(t, 0.9, retrieved2[0].Score)
}

func TestInMemoryRecommendationRepository_GetRejectedOpportunities(t *testing.T) {
	repo := NewInMemoryRecommendationRepository(zerolog.Nop())

	rejectedOpportunities := []planningdomain.RejectedOpportunity{
		{
			Side:           "SELL",
			Symbol:         "AAPL",
			Name:           "Apple Inc.",
			Reasons:        []string{"low_score", "recently_bought"},
			OriginalReason: "Rebalance: overweight",
		},
		{
			Side:           "BUY",
			Symbol:         "MSFT",
			Name:           "Microsoft Corp.",
			Reasons:        []string{"insufficient_cash"},
			OriginalReason: "Growth opportunity",
		},
	}

	portfolioHash := "test-hash-456"
	err := repo.StoreRejectedOpportunities(rejectedOpportunities, portfolioHash)
	require.NoError(t, err)

	// Retrieve and verify
	retrieved := repo.GetRejectedOpportunities(portfolioHash)
	require.NotNil(t, retrieved)
	assert.Len(t, retrieved, 2)
	assert.Equal(t, "AAPL", retrieved[0].Symbol)
	assert.Equal(t, "SELL", retrieved[0].Side)
	assert.Equal(t, []string{"low_score", "recently_bought"}, retrieved[0].Reasons)
	assert.Equal(t, "Rebalance: overweight", retrieved[0].OriginalReason)
}

func TestInMemoryRecommendationRepository_GetRejectedOpportunities_NotFound(t *testing.T) {
	repo := NewInMemoryRecommendationRepository(zerolog.Nop())

	// Get non-existent rejected opportunities
	retrieved := repo.GetRejectedOpportunities("nonexistent-hash")
	assert.Nil(t, retrieved)
}
