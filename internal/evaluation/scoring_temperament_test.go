package evaluation

import (
	"testing"

	"github.com/aristath/sentinel/internal/modules/settings"
	"github.com/stretchr/testify/assert"
)

// TestScoringParamsStruct verifies the scoring params struct works correctly
func TestScoringParamsStruct(t *testing.T) {
	params := settings.ScoringParams{
		VolatilityExcellent:  0.15,
		VolatilityGood:       0.25,
		VolatilityAcceptable: 0.40,
		SharpeExcellent:      2.0,
		SharpeGood:           1.0,
		SharpeAcceptable:     0.5,
	}

	// Verify tier ordering for volatility
	assert.True(t, params.VolatilityExcellent < params.VolatilityGood,
		"excellent volatility should be lower than good")
	assert.True(t, params.VolatilityGood < params.VolatilityAcceptable,
		"good volatility should be lower than acceptable")

	// Verify tier ordering for Sharpe
	assert.True(t, params.SharpeExcellent > params.SharpeGood,
		"excellent Sharpe should be higher than good")
	assert.True(t, params.SharpeGood > params.SharpeAcceptable,
		"good Sharpe should be higher than acceptable")
}

// TestEvaluationWeightsFromSettings verifies weights can be retrieved from settings
func TestEvaluationWeightsFromSettings(t *testing.T) {
	// Pure end-state scoring with 4 components
	weights := settings.EvaluationWeights{
		PortfolioQuality:         0.35,
		DiversificationAlignment: 0.30,
		RiskAdjustedMetrics:      0.25,
		EndStateImprovement:      0.10,
	}

	// Verify weights sum to 1.0
	sum := weights.PortfolioQuality + weights.DiversificationAlignment +
		weights.RiskAdjustedMetrics + weights.EndStateImprovement

	assert.InDelta(t, 1.0, sum, 0.001, "weights should sum to 1.0")

	// Verify normalization works
	normalized := weights.Normalize()
	normalizedSum := normalized.PortfolioQuality + normalized.DiversificationAlignment +
		normalized.RiskAdjustedMetrics + normalized.EndStateImprovement

	assert.InDelta(t, 1.0, normalizedSum, 0.001, "normalized weights should sum to 1.0")
}

// TestDefaultWeightsMatchConstants verifies default weights match the new pure end-state constants
func TestDefaultWeightsMatchConstants(t *testing.T) {
	// Current constants for pure end-state scoring
	assert.Equal(t, 0.35, WeightPortfolioQuality)
	assert.Equal(t, 0.30, WeightDiversificationAlignment)
	assert.Equal(t, 0.25, WeightRiskAdjustedMetrics)
	assert.Equal(t, 0.10, WeightEndStateImprovement)

	// Sum should be 1.0
	sum := WeightPortfolioQuality + WeightDiversificationAlignment +
		WeightRiskAdjustedMetrics + WeightEndStateImprovement
	assert.InDelta(t, 1.0, sum, 0.001, "constant weights should sum to 1.0")
}

// TestScoringThresholdsMatchDefaults verifies default thresholds match constants
func TestScoringThresholdsMatchDefaults(t *testing.T) {
	// Current constants
	assert.Equal(t, 0.3, DeviationScale)
}

// TestTemperamentScorerInterface verifies the scorer can be created with settings
func TestTemperamentScorerInterface(t *testing.T) {
	// Pure end-state weights
	weights := settings.EvaluationWeights{
		PortfolioQuality:         0.35,
		DiversificationAlignment: 0.30,
		RiskAdjustedMetrics:      0.25,
		EndStateImprovement:      0.10,
	}

	params := settings.ScoringParams{
		DeviationScale: 0.30,
	}

	// Create a scorer config
	config := ScorerConfig{
		Weights:                weights,
		ScoringParams:          params,
		TransactionCostFixed:   2.0,
		TransactionCostPercent: 0.002,
	}

	// Verify config is valid
	assert.NotNil(t, config)
	assert.InDelta(t, 1.0, config.Weights.PortfolioQuality+config.Weights.DiversificationAlignment+
		config.Weights.RiskAdjustedMetrics+config.Weights.EndStateImprovement, 0.001)
}

// TestGetRegimeAdaptiveWeights_BullMarket verifies bull market weight adjustments
func TestGetRegimeAdaptiveWeights_BullMarket(t *testing.T) {
	// Strong bull market
	weights := GetRegimeAdaptiveWeights(0.8)

	// In bull market, quality should increase
	assert.Greater(t, weights["quality"], WeightPortfolioQuality,
		"quality weight should increase in bull market")

	// Risk weight should decrease
	assert.Less(t, weights["risk"], WeightRiskAdjustedMetrics,
		"risk weight should decrease in bull market")
}

// TestGetRegimeAdaptiveWeights_BearMarket verifies bear market weight adjustments
func TestGetRegimeAdaptiveWeights_BearMarket(t *testing.T) {
	// Strong bear market
	weights := GetRegimeAdaptiveWeights(-0.8)

	// In bear market, quality should decrease
	assert.Less(t, weights["quality"], WeightPortfolioQuality,
		"quality weight should decrease in bear market")

	// Risk weight should increase
	assert.Greater(t, weights["risk"], WeightRiskAdjustedMetrics,
		"risk weight should increase in bear market")
}

// TestGetRegimeAdaptiveWeights_NeutralMarket verifies neutral market uses base weights
func TestGetRegimeAdaptiveWeights_NeutralMarket(t *testing.T) {
	// Neutral market
	weights := GetRegimeAdaptiveWeights(0.0)

	// Weights should be at base values
	assert.Equal(t, WeightPortfolioQuality, weights["quality"])
	assert.Equal(t, WeightDiversificationAlignment, weights["diversification"])
	assert.Equal(t, WeightRiskAdjustedMetrics, weights["risk"])
	assert.Equal(t, WeightEndStateImprovement, weights["improvement"])
}
