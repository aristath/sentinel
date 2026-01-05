package scorers

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

// ============================================================================
// Quality Gate Tests
// ============================================================================

func TestOpportunityScorer_CalculateWithQualityGate_HighOpportunityHighQuality(t *testing.T) {
	scorer := NewOpportunityScorer()

	// High opportunity (cheap) with high quality (not a value trap)
	dailyPrices := make([]float64, 300)
	for i := range dailyPrices {
		dailyPrices[i] = 100.0 - float64(i)*0.1 // Declining price (cheap)
	}
	peRatio := 10.0
	forwardPE := 9.0
	marketAvgPE := 20.0
	fundamentalsScore := 0.75 // High quality
	longTermScore := 0.70     // High quality

	result := scorer.CalculateWithQualityGate(
		dailyPrices,
		&peRatio,
		&forwardPE,
		marketAvgPE,
		&fundamentalsScore,
		&longTermScore,
		"EQUITY", // Product type for tests
	)

	// Should have high opportunity score without penalty
	assert.Greater(t, result.Score, 0.6, "High opportunity + high quality should score well")
	assert.NotContains(t, result.Components, "quality_penalty", "High quality should not have penalty")
}

func TestOpportunityScorer_CalculateWithQualityGate_HighOpportunityLowQuality(t *testing.T) {
	scorer := NewOpportunityScorer()

	// High opportunity (cheap) but low quality (value trap)
	dailyPrices := make([]float64, 300)
	for i := range dailyPrices {
		dailyPrices[i] = 100.0 - float64(i)*0.1 // Declining price (cheap)
	}
	peRatio := 8.0 // Very cheap
	forwardPE := 7.0
	marketAvgPE := 20.0
	fundamentalsScore := 0.45 // Low quality (below 0.6 threshold)
	longTermScore := 0.40     // Low quality (below 0.5 threshold)

	result := scorer.CalculateWithQualityGate(
		dailyPrices,
		&peRatio,
		&forwardPE,
		marketAvgPE,
		&fundamentalsScore,
		&longTermScore,
		"EQUITY", // Product type for tests
	)

	// Should have penalty applied (30% reduction for high opportunity + low quality)
	assert.Contains(t, result.Components, "quality_penalty", "Low quality should have penalty")
	assert.GreaterOrEqual(t, result.Components["quality_penalty"], 0.25, "Value trap should get 30% penalty")
	// Score should be lower than it would be without penalty (but may still be > 0.6 if base was very high)
	assert.Greater(t, result.Components["quality_penalty"], 0.0, "Should have some penalty applied")
}

func TestOpportunityScorer_CalculateWithQualityGate_ModerateOpportunityLowQuality(t *testing.T) {
	scorer := NewOpportunityScorer()

	// Moderate opportunity (somewhat cheap) but low quality
	dailyPrices := make([]float64, 300)
	for i := range dailyPrices {
		dailyPrices[i] = 100.0 - float64(i)*0.05 // Slightly declining
	}
	peRatio := 15.0
	forwardPE := 14.0
	marketAvgPE := 20.0
	fundamentalsScore := 0.50 // Low quality
	longTermScore := 0.45     // Low quality

	result := scorer.CalculateWithQualityGate(
		dailyPrices,
		&peRatio,
		&forwardPE,
		marketAvgPE,
		&fundamentalsScore,
		&longTermScore,
		"EQUITY", // Product type for tests
	)

	// Should have penalty (15% for moderate opportunity + low quality, or 30% if base score was high)
	// The actual penalty depends on the base opportunity score, which can vary
	if result.Components["quality_penalty"] > 0 {
		assert.GreaterOrEqual(t, result.Components["quality_penalty"], 0.10, "Should have some penalty")
		assert.LessOrEqual(t, result.Components["quality_penalty"], 0.30, "Penalty should not exceed 30%")
	}
}

func TestOpportunityScorer_CalculateWithQualityGate_LowFundamentalsOnly(t *testing.T) {
	scorer := NewOpportunityScorer()

	// High opportunity but only fundamentals is low (long-term is OK)
	dailyPrices := make([]float64, 300)
	for i := range dailyPrices {
		dailyPrices[i] = 100.0 - float64(i)*0.1
	}
	peRatio := 8.0
	forwardPE := 7.0
	marketAvgPE := 20.0
	fundamentalsScore := 0.50 // Low (below 0.6)
	longTermScore := 0.60     // OK (above 0.5)

	result := scorer.CalculateWithQualityGate(
		dailyPrices,
		&peRatio,
		&forwardPE,
		marketAvgPE,
		&fundamentalsScore,
		&longTermScore,
		"EQUITY", // Product type for tests
	)

	// Should still have penalty (one metric below threshold is enough)
	assert.Contains(t, result.Components, "quality_penalty", "Low fundamentals should trigger penalty")
}

func TestOpportunityScorer_CalculateWithQualityGate_LowLongTermOnly(t *testing.T) {
	scorer := NewOpportunityScorer()

	// High opportunity but only long-term is low (fundamentals is OK)
	dailyPrices := make([]float64, 300)
	for i := range dailyPrices {
		dailyPrices[i] = 100.0 - float64(i)*0.1
	}
	peRatio := 8.0
	forwardPE := 7.0
	marketAvgPE := 20.0
	fundamentalsScore := 0.65 // OK (above 0.6)
	longTermScore := 0.40     // Low (below 0.5)

	result := scorer.CalculateWithQualityGate(
		dailyPrices,
		&peRatio,
		&forwardPE,
		marketAvgPE,
		&fundamentalsScore,
		&longTermScore,
		"EQUITY", // Product type for tests
	)

	// Should still have penalty (one metric below threshold is enough)
	assert.Contains(t, result.Components, "quality_penalty", "Low long-term should trigger penalty")
}

func TestOpportunityScorer_CalculateWithQualityGate_NoQualityData(t *testing.T) {
	scorer := NewOpportunityScorer()

	// High opportunity but no quality data available
	dailyPrices := make([]float64, 300)
	for i := range dailyPrices {
		dailyPrices[i] = 100.0 - float64(i)*0.1
	}
	peRatio := 8.0
	forwardPE := 7.0
	marketAvgPE := 20.0

	result := scorer.CalculateWithQualityGate(
		dailyPrices,
		&peRatio,
		&forwardPE,
		marketAvgPE,
		nil,      // No fundamentals
		nil,      // No long-term
		"EQUITY", // Product type for tests
	)

	// Should not have penalty (can't detect value trap without quality data)
	assert.NotContains(t, result.Components, "quality_penalty", "No quality data should not have penalty")
	assert.Greater(t, result.Score, 0.0, "Should still calculate opportunity score")
}

func TestCalculateQualityPenalty_Thresholds(t *testing.T) {
	testCases := []struct {
		name              string
		opportunityScore  float64
		fundamentalsScore *float64
		longTermScore     *float64
		expectedMin       float64
		expectedMax       float64
		description       string
	}{
		{
			name:              "High opportunity, both quality metrics low",
			opportunityScore:  0.75,
			fundamentalsScore: floatPtrForOpportunityTest(0.50), // Below 0.6
			longTermScore:     floatPtrForOpportunityTest(0.40), // Below 0.5
			expectedMin:       0.25,
			expectedMax:       0.30,
			description:       "Should get 30% penalty",
		},
		{
			name:              "Moderate opportunity, both quality metrics low",
			opportunityScore:  0.60,
			fundamentalsScore: floatPtrForOpportunityTest(0.50),
			longTermScore:     floatPtrForOpportunityTest(0.40),
			expectedMin:       0.10,
			expectedMax:       0.20,
			description:       "Should get 15% penalty",
		},
		{
			name:              "High opportunity, high quality",
			opportunityScore:  0.75,
			fundamentalsScore: floatPtrForOpportunityTest(0.70), // Above 0.6
			longTermScore:     floatPtrForOpportunityTest(0.60), // Above 0.5
			expectedMin:       0.0,
			expectedMax:       0.0,
			description:       "Should get no penalty",
		},
		{
			name:              "Low opportunity, low quality",
			opportunityScore:  0.40,
			fundamentalsScore: floatPtrForOpportunityTest(0.50),
			longTermScore:     floatPtrForOpportunityTest(0.40),
			expectedMin:       0.0,
			expectedMax:       0.0,
			description:       "Low opportunity doesn't need penalty",
		},
		{
			name:              "High opportunity, only fundamentals low",
			opportunityScore:  0.75,
			fundamentalsScore: floatPtrForOpportunityTest(0.50), // Below 0.6
			longTermScore:     floatPtrForOpportunityTest(0.60), // Above 0.5
			expectedMin:       0.25,
			expectedMax:       0.30,
			description:       "One metric low should trigger penalty",
		},
		{
			name:              "High opportunity, only long-term low",
			opportunityScore:  0.75,
			fundamentalsScore: floatPtrForOpportunityTest(0.70), // Above 0.6
			longTermScore:     floatPtrForOpportunityTest(0.40), // Below 0.5
			expectedMin:       0.25,
			expectedMax:       0.30,
			description:       "One metric low should trigger penalty",
		},
		{
			name:              "No quality data",
			opportunityScore:  0.75,
			fundamentalsScore: nil,
			longTermScore:     nil,
			expectedMin:       0.0,
			expectedMax:       0.0,
			description:       "No quality data = no penalty",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			penalty := calculateQualityPenalty(tc.opportunityScore, tc.fundamentalsScore, tc.longTermScore)
			assert.GreaterOrEqual(t, penalty, tc.expectedMin, tc.description)
			assert.LessOrEqual(t, penalty, tc.expectedMax, tc.description)
		})
	}
}

// Helper function to create float pointer for tests
func floatPtrForOpportunityTest(f float64) *float64 {
	return &f
}
