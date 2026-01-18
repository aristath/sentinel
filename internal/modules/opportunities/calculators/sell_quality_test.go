package calculators

import (
	"testing"

	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestCalculateSellQualityScore_LowStabilityIncreasessPriority(t *testing.T) {
	// Given: Position with low stability score (0.3)
	// When: CalculateSellQualityScore is called
	// Then: SellPriorityBoost should be > 1.0

	ctx := &planningdomain.OpportunityContext{
		StabilityScores: map[string]float64{
			"US123": 0.3, // Low stability
		},
		LongTermScores: map[string]float64{
			"US123": 0.4, // Low long-term
		},
	}

	result := CalculateSellQualityScore(ctx, "US123", nil, nil)

	assert.Greater(t, result.SellPriorityBoost, 1.0,
		"Low stability should increase sell priority (boost > 1.0)")
	assert.InDelta(t, 0.3, result.StabilityScore, 0.01)
	assert.InDelta(t, 0.4, result.LongTermScore, 0.01)
	assert.False(t, result.IsHighQuality, "Low scores should not be marked as high quality")
}

func TestCalculateSellQualityScore_HighQualityProtected(t *testing.T) {
	// Given: Position with high stability (0.8) and long-term (0.85) scores
	// When: CalculateSellQualityScore is called
	// Then: IsHighQuality should be true and SellPriorityBoost < 1.0

	ctx := &planningdomain.OpportunityContext{
		StabilityScores: map[string]float64{
			"US123": 0.80, // High stability
		},
		LongTermScores: map[string]float64{
			"US123": 0.85, // High long-term
		},
	}

	result := CalculateSellQualityScore(ctx, "US123", nil, nil)

	assert.True(t, result.IsHighQuality,
		"High scores should mark position as high quality")
	assert.Less(t, result.SellPriorityBoost, 1.0,
		"High quality should reduce sell priority (boost < 1.0)")
	assert.Greater(t, result.QualityScore, 0.7,
		"Composite quality score should be > 0.7")
}

func TestCalculateSellQualityScore_NegativeTagsIncreasePriority(t *testing.T) {
	tests := []struct {
		name             string
		tags             []string
		expectNegative   bool
		minPriorityBoost float64 // Minimum expected boost
	}{
		{
			name:             "stagnant tag",
			tags:             []string{"stagnant"},
			expectNegative:   true,
			minPriorityBoost: 1.2, // At least 20% boost
		},
		{
			name:             "underperforming tag",
			tags:             []string{"underperforming"},
			expectNegative:   true,
			minPriorityBoost: 1.2,
		},
		{
			name:             "value-trap tag",
			tags:             []string{"value-trap"},
			expectNegative:   true,
			minPriorityBoost: 1.2,
		},
		{
			name:             "ensemble-value-trap tag",
			tags:             []string{"ensemble-value-trap"},
			expectNegative:   true,
			minPriorityBoost: 1.2,
		},
		{
			name:             "multiple negative tags",
			tags:             []string{"stagnant", "underperforming"},
			expectNegative:   true,
			minPriorityBoost: 1.4, // Higher boost for multiple tags
		},
		{
			name:             "no negative tags",
			tags:             []string{"growth", "stable"},
			expectNegative:   false,
			minPriorityBoost: 0.8, // May reduce priority if positive
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ctx := &planningdomain.OpportunityContext{
				StabilityScores: map[string]float64{"US123": 0.5}, // Neutral
				LongTermScores:  map[string]float64{"US123": 0.5}, // Neutral
			}

			result := CalculateSellQualityScore(ctx, "US123", tt.tags, nil)

			assert.Equal(t, tt.expectNegative, result.HasNegativeTags,
				"HasNegativeTags should be %v for tags %v", tt.expectNegative, tt.tags)

			if tt.expectNegative {
				assert.GreaterOrEqual(t, result.SellPriorityBoost, tt.minPriorityBoost,
					"Negative tags should boost priority to at least %.2f", tt.minPriorityBoost)
			}
		})
	}
}

func TestCalculateSellQualityScore_ProtectedTagsReducePriority(t *testing.T) {
	tests := []struct {
		name             string
		tags             []string
		maxPriorityBoost float64 // Maximum expected boost (should be reduced)
	}{
		{
			name:             "high-quality tag",
			tags:             []string{"high-quality"},
			maxPriorityBoost: 0.9, // Should reduce priority
		},
		{
			name:             "quality-high-cagr tag",
			tags:             []string{"quality-high-cagr"},
			maxPriorityBoost: 0.9,
		},
		{
			name:             "high-stability tag",
			tags:             []string{"high-stability"},
			maxPriorityBoost: 0.9,
		},
		{
			name:             "consistent-grower tag",
			tags:             []string{"consistent-grower"},
			maxPriorityBoost: 0.9,
		},
		{
			name:             "meets-target-return tag",
			tags:             []string{"meets-target-return"},
			maxPriorityBoost: 0.9,
		},
		{
			name:             "multiple protected tags",
			tags:             []string{"high-quality", "consistent-grower"},
			maxPriorityBoost: 0.7, // Lower boost for multiple protected tags
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ctx := &planningdomain.OpportunityContext{
				StabilityScores: map[string]float64{"US123": 0.5}, // Neutral
				LongTermScores:  map[string]float64{"US123": 0.5}, // Neutral
			}

			result := CalculateSellQualityScore(ctx, "US123", tt.tags, nil)

			assert.True(t, result.IsHighQuality,
				"Protected tags should mark as high quality")
			assert.LessOrEqual(t, result.SellPriorityBoost, tt.maxPriorityBoost,
				"Protected tags should reduce priority to at most %.2f", tt.maxPriorityBoost)
		})
	}
}

func TestCalculateSellQualityScore_MixedTags(t *testing.T) {
	// When position has both negative and protected tags, they should balance

	ctx := &planningdomain.OpportunityContext{
		StabilityScores: map[string]float64{"US123": 0.5},
		LongTermScores:  map[string]float64{"US123": 0.5},
	}

	// Has stagnant (negative) but also high-quality (protected)
	result := CalculateSellQualityScore(ctx, "US123", []string{"stagnant", "high-quality"}, nil)

	// Should have both flags set
	assert.True(t, result.HasNegativeTags, "Should have negative tags")
	assert.True(t, result.IsHighQuality, "Should be high quality")

	// Priority boost should be somewhere in the middle
	// Not as high as pure negative, not as low as pure positive
	assert.Greater(t, result.SellPriorityBoost, 0.5,
		"Mixed tags should result in moderate priority")
	assert.Less(t, result.SellPriorityBoost, 1.5,
		"Mixed tags should not have extreme priority")
}

func TestCalculateSellQualityScore_NoScoresAvailable(t *testing.T) {
	// When no scores are available, should use default neutral priority

	ctx := &planningdomain.OpportunityContext{
		StabilityScores: nil,
		LongTermScores:  nil,
	}

	result := CalculateSellQualityScore(ctx, "US123", nil, nil)

	assert.InDelta(t, 1.0, result.SellPriorityBoost, 0.1,
		"Without scores, should default to neutral priority (~1.0)")
	assert.False(t, result.IsHighQuality, "Without scores, should not be high quality")
	assert.False(t, result.HasNegativeTags, "Without tags, should not have negative tags")
}

func TestSortPositionsBySellPriority_LowQualityFirst(t *testing.T) {
	// Given: 3 positions with different quality scores
	// When: SortPositionsBySellPriority is called
	// Then: Low quality should come first (highest sell priority)

	positions := []planningdomain.EnrichedPosition{
		{ISIN: "HIGH_QUALITY", Symbol: "HIGH.US", Quantity: 100, CurrentPrice: 10.0},
		{ISIN: "LOW_QUALITY", Symbol: "LOW.US", Quantity: 100, CurrentPrice: 10.0},
		{ISIN: "MED_QUALITY", Symbol: "MED.US", Quantity: 100, CurrentPrice: 10.0},
	}

	ctx := &planningdomain.OpportunityContext{
		StabilityScores: map[string]float64{
			"HIGH_QUALITY": 0.85, // High quality
			"LOW_QUALITY":  0.25, // Low quality
			"MED_QUALITY":  0.55, // Medium quality
		},
		LongTermScores: map[string]float64{
			"HIGH_QUALITY": 0.80,
			"LOW_QUALITY":  0.30,
			"MED_QUALITY":  0.50,
		},
	}

	sorted := SortPositionsBySellPriority(positions, ctx, nil, nil)

	require.Len(t, sorted, 3)

	// Low quality should be first (highest sell priority)
	assert.Equal(t, "LOW_QUALITY", sorted[0].ISIN,
		"Lowest quality position should be first")

	// Medium quality should be second
	assert.Equal(t, "MED_QUALITY", sorted[1].ISIN,
		"Medium quality position should be second")

	// High quality should be last (lowest sell priority)
	assert.Equal(t, "HIGH_QUALITY", sorted[2].ISIN,
		"Highest quality position should be last")
}

func TestSortPositionsBySellPriority_NegativeTagsBoostToFront(t *testing.T) {
	// Given: Position A (quality 0.6, no tags) and Position B (quality 0.7, has "stagnant" tag)
	// When: SortPositionsBySellPriority is called
	// Then: Position B should come first despite higher quality score

	positions := []planningdomain.EnrichedPosition{
		{ISIN: "NO_TAGS", Symbol: "A.US", Quantity: 100, CurrentPrice: 10.0},
		{ISIN: "STAGNANT", Symbol: "B.US", Quantity: 100, CurrentPrice: 10.0},
	}

	ctx := &planningdomain.OpportunityContext{
		StabilityScores: map[string]float64{
			"NO_TAGS":  0.60,
			"STAGNANT": 0.70, // Higher quality score
		},
		LongTermScores: map[string]float64{
			"NO_TAGS":  0.60,
			"STAGNANT": 0.70,
		},
	}

	// Mock security repo that returns tags
	mockRepo := &mockSecurityRepository{
		tags: map[string][]string{
			"A.US": {},
			"B.US": {"stagnant"}, // Has negative tag
		},
	}

	sorted := SortPositionsBySellPriority(positions, ctx, mockRepo, nil)

	require.Len(t, sorted, 2)

	// Stagnant position should be first despite higher quality
	assert.Equal(t, "STAGNANT", sorted[0].ISIN,
		"Position with stagnant tag should be prioritized for selling")
}

func TestSortPositionsBySellPriority_EmptyList(t *testing.T) {
	ctx := &planningdomain.OpportunityContext{}

	sorted := SortPositionsBySellPriority(nil, ctx, nil, nil)
	assert.Empty(t, sorted, "Should handle nil input")

	sorted = SortPositionsBySellPriority([]planningdomain.EnrichedPosition{}, ctx, nil, nil)
	assert.Empty(t, sorted, "Should handle empty input")
}

func TestSortPositionsBySellPriority_SinglePosition(t *testing.T) {
	positions := []planningdomain.EnrichedPosition{
		{ISIN: "ONLY", Symbol: "ONLY.US", Quantity: 100},
	}

	ctx := &planningdomain.OpportunityContext{
		StabilityScores: map[string]float64{"ONLY": 0.5},
		LongTermScores:  map[string]float64{"ONLY": 0.5},
	}

	sorted := SortPositionsBySellPriority(positions, ctx, nil, nil)

	require.Len(t, sorted, 1)
	assert.Equal(t, "ONLY", sorted[0].ISIN)
}

// Mock security repository for tests
type mockSecurityRepository struct {
	tags map[string][]string
}

func (m *mockSecurityRepository) GetTagsForSecurity(symbol string) ([]string, error) {
	if m.tags == nil {
		return nil, nil
	}
	return m.tags[symbol], nil
}

func (m *mockSecurityRepository) GetByTags(tags []string) ([]universe.Security, error) {
	return nil, nil
}
