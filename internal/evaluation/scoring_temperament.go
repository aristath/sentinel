package evaluation

import (
	"github.com/aristath/sentinel/internal/modules/settings"
)

// ScorerConfig holds the configuration for temperament-aware scoring.
// This allows the scorer to use adjusted weights and thresholds from the settings service.
//
// With pure end-state scoring, we have 4 components:
// - Portfolio Quality (35%)
// - Diversification & Alignment (30%)
// - Risk-Adjusted Metrics (25%)
// - End-State Improvement (10%)
type ScorerConfig struct {
	// Weights holds the evaluation weights adjusted by temperament
	Weights settings.EvaluationWeights

	// ScoringParams holds scoring thresholds adjusted by temperament
	ScoringParams settings.ScoringParams

	// Transaction cost settings
	TransactionCostFixed   float64
	TransactionCostPercent float64
	CostPenaltyFactor      float64
}

// NewScorerConfig creates a ScorerConfig from the settings service.
// This is the recommended way to create a scorer config as it respects temperament settings.
func NewScorerConfig(settingsService *settings.Service) ScorerConfig {
	return ScorerConfig{
		Weights:       settingsService.GetAdjustedEvaluationWeights(),
		ScoringParams: settingsService.GetAdjustedScoringParams(),
	}
}

// NewDefaultScorerConfig creates a ScorerConfig with default (non-temperament-adjusted) values.
// Use this when you don't have access to the settings service.
func NewDefaultScorerConfig() ScorerConfig {
	return ScorerConfig{
		Weights: settings.EvaluationWeights{
			// Pure end-state scoring weights
			PortfolioQuality:         WeightPortfolioQuality,
			DiversificationAlignment: WeightDiversificationAlignment,
			RiskAdjustedMetrics:      WeightRiskAdjustedMetrics,
			EndStateImprovement:      WeightEndStateImprovement,
		},
		ScoringParams: settings.ScoringParams{
			DeviationScale:       DeviationScale,
			RegimeBullThreshold:  0.30,
			RegimeBearThreshold:  -0.30,
			VolatilityExcellent:  0.15,
			VolatilityGood:       0.25,
			VolatilityAcceptable: 0.40,
			DrawdownExcellent:    0.10,
			DrawdownGood:         0.20,
			DrawdownAcceptable:   0.30,
			SharpeExcellent:      2.0,
			SharpeGood:           1.0,
			SharpeAcceptable:     0.5,
		},
	}
}

// GetWeightsMap converts EvaluationWeights to a map for use with existing code.
// Uses the new 4-component pure end-state scoring structure.
func (c ScorerConfig) GetWeightsMap() map[string]float64 {
	return map[string]float64{
		"quality":         c.Weights.PortfolioQuality,
		"diversification": c.Weights.DiversificationAlignment,
		"risk":            c.Weights.RiskAdjustedMetrics,
		"improvement":     c.Weights.EndStateImprovement,
	}
}

// GetRegimeAdaptiveWeightsWithConfig returns evaluation weights adjusted for market regime
// using the temperament-adjusted base weights from the config.
// Uses pure end-state adjustments (no action-based components).
func GetRegimeAdaptiveWeightsWithConfig(regimeScore float64, config ScorerConfig) map[string]float64 {
	// Start with temperament-adjusted weights
	weights := config.GetWeightsMap()

	// Apply regime adjustments - pure end-state focus
	if regimeScore > config.ScoringParams.RegimeBullThreshold { // Bull market
		bullFactor := (regimeScore - config.ScoringParams.RegimeBullThreshold) /
			(1.0 - config.ScoringParams.RegimeBullThreshold)
		// In bull markets: emphasize quality and diversification
		weights["quality"] = weights["quality"] + 0.03*bullFactor
		weights["risk"] = weights["risk"] - 0.03*bullFactor
	} else if regimeScore < config.ScoringParams.RegimeBearThreshold { // Bear market
		bearFactor := (config.ScoringParams.RegimeBearThreshold - regimeScore) /
			(config.ScoringParams.RegimeBearThreshold - (-1.0))
		// In bear markets: emphasize risk management and diversification
		weights["risk"] = weights["risk"] + 0.08*bearFactor
		weights["diversification"] = weights["diversification"] + 0.02*bearFactor
		weights["quality"] = weights["quality"] - 0.05*bearFactor
		weights["improvement"] = weights["improvement"] - 0.05*bearFactor
	}

	return weights
}

// VolatilityScore converts weighted volatility to a score using temperament thresholds.
func VolatilityScore(weightedVol float64, params settings.ScoringParams) float64 {
	if weightedVol <= params.VolatilityExcellent {
		return 1.0
	} else if weightedVol <= params.VolatilityGood {
		// Interpolate between 1.0 and 0.7
		return 1.0 - (weightedVol-params.VolatilityExcellent)/
			(params.VolatilityGood-params.VolatilityExcellent)*0.3
	} else if weightedVol <= params.VolatilityAcceptable {
		// Interpolate between 0.7 and 0.3
		return 0.7 - (weightedVol-params.VolatilityGood)/
			(params.VolatilityAcceptable-params.VolatilityGood)*0.4
	}
	// Above acceptable threshold
	return 0.3 - (weightedVol-params.VolatilityAcceptable)*0.5
}

// DrawdownScore converts weighted drawdown to a score using temperament thresholds.
func DrawdownScore(weightedDD float64, params settings.ScoringParams) float64 {
	if weightedDD <= params.DrawdownExcellent {
		return 1.0
	} else if weightedDD <= params.DrawdownGood {
		return 0.8 + (params.DrawdownGood-weightedDD)*2
	} else if weightedDD <= params.DrawdownAcceptable {
		return 0.6 + (params.DrawdownAcceptable-weightedDD)*2
	}
	// Above acceptable threshold
	return 0.6 - (weightedDD-params.DrawdownAcceptable)*2
}

// SharpeScore converts weighted Sharpe ratio to a score using temperament thresholds.
func SharpeScore(weightedSharpe float64, params settings.ScoringParams) float64 {
	if weightedSharpe >= params.SharpeExcellent {
		return 1.0
	} else if weightedSharpe >= params.SharpeGood {
		return 0.7 + (weightedSharpe-params.SharpeGood)/
			(params.SharpeExcellent-params.SharpeGood)*0.3
	} else if weightedSharpe >= params.SharpeAcceptable {
		return 0.4 + (weightedSharpe-params.SharpeAcceptable)/
			(params.SharpeGood-params.SharpeAcceptable)*0.3
	} else if weightedSharpe >= 0 {
		return weightedSharpe / params.SharpeAcceptable * 0.4
	}
	return 0.0
}

// NOTE: WindfallScore has been removed as part of the pure end-state scoring refactor.
// Windfall was an action-based metric that no longer applies to the new scoring philosophy.

// DeviationScore converts average deviation to a score using temperament scale.
func DeviationScore(avgDeviation float64, params settings.ScoringParams) float64 {
	if avgDeviation >= params.DeviationScale {
		return 0.0
	}
	return 1.0 - avgDeviation/params.DeviationScale
}
