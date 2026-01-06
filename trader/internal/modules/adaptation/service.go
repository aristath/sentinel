package adaptation

import (
	"math"

	"github.com/rs/zerolog"
)

// QualityGateThresholds represents adaptive quality gate thresholds
type QualityGateThresholds struct {
	Fundamentals float64 // Fundamentals score threshold
	LongTerm     float64 // Long-term score threshold
}

// GetFundamentals returns the fundamentals threshold
func (q *QualityGateThresholds) GetFundamentals() float64 {
	return q.Fundamentals
}

// GetLongTerm returns the long-term threshold
func (q *QualityGateThresholds) GetLongTerm() float64 {
	return q.LongTerm
}

// AdaptiveMarketService provides adaptive market hypothesis functionality
type AdaptiveMarketService struct {
	regimeDetector     interface{} // MarketRegimeDetector (will be properly typed)
	performanceTracker interface{} // PerformanceTracker (will be properly typed)
	weightsCalculator  interface{} // AdaptiveWeightsCalculator (will be properly typed)
	repository         interface{} // AdaptiveRepository (will be properly typed)
	log                zerolog.Logger
}

// NewAdaptiveMarketService creates a new adaptive market service
func NewAdaptiveMarketService(
	regimeDetector interface{},
	performanceTracker interface{},
	weightsCalculator interface{},
	repository interface{},
	log zerolog.Logger,
) *AdaptiveMarketService {
	return &AdaptiveMarketService{
		regimeDetector:     regimeDetector,
		performanceTracker: performanceTracker,
		weightsCalculator:  weightsCalculator,
		repository:         repository,
		log:                log.With().Str("component", "adaptive_market_service").Logger(),
	}
}

// ShouldAdapt determines if adaptation is needed based on regime score change
func (s *AdaptiveMarketService) ShouldAdapt(currentScore, lastScore, threshold float64) bool {
	change := math.Abs(currentScore - lastScore)

	// Adapt if change exceeds threshold
	if change > threshold {
		return true
	}

	// Also adapt if crossing key thresholds (-0.33, 0.0, +0.33)
	keyThresholds := []float64{-0.33, 0.0, 0.33}
	for _, keyThresh := range keyThresholds {
		if (lastScore < keyThresh && currentScore >= keyThresh) ||
			(lastScore > keyThresh && currentScore <= keyThresh) {
			return true
		}
	}

	return false
}

// CalculateAdaptiveWeights calculates adaptive scoring weights based on regime score
// Uses linear interpolation between extreme cases (bull/bear/neutral)
func (s *AdaptiveMarketService) CalculateAdaptiveWeights(regimeScore float64) map[string]float64 {
	// Clamp score to valid range
	score := math.Max(-1.0, math.Min(1.0, regimeScore))

	// Define base weights for extreme cases
	neutralWeights := map[string]float64{
		"long_term":       0.25,
		"fundamentals":    0.20,
		"dividends":       0.18,
		"opportunity":     0.12,
		"short_term":      0.08,
		"technicals":      0.07,
		"opinion":         0.05,
		"diversification": 0.05,
	}

	bullWeights := map[string]float64{
		"long_term":       0.30, // Higher in bull
		"fundamentals":    0.15, // Lower in bull
		"dividends":       0.15, // Lower in bull
		"opportunity":     0.18, // Higher in bull
		"short_term":      0.08,
		"technicals":      0.07,
		"opinion":         0.05,
		"diversification": 0.02,
	}

	bearWeights := map[string]float64{
		"long_term":       0.20, // Lower in bear
		"fundamentals":    0.30, // Higher in bear
		"dividends":       0.25, // Higher in bear
		"opportunity":     0.08, // Lower in bear
		"short_term":      0.05,
		"technicals":      0.05,
		"opinion":         0.04,
		"diversification": 0.03,
	}

	// Linear interpolation
	weights := make(map[string]float64)

	if score >= 0 {
		// Interpolate between neutral and bull
		for key := range neutralWeights {
			neutral := neutralWeights[key]
			bull := bullWeights[key]
			weights[key] = neutral + (bull-neutral)*score
		}
	} else {
		// Interpolate between neutral and bear
		absScore := math.Abs(score)
		for key := range neutralWeights {
			neutral := neutralWeights[key]
			bear := bearWeights[key]
			weights[key] = neutral + (bear-neutral)*absScore
		}
	}

	return weights
}

// CalculateAdaptiveBlend calculates MV/HRP blend based on regime score
// Uses linear interpolation: Bull → more MV, Bear → more HRP
func (s *AdaptiveMarketService) CalculateAdaptiveBlend(regimeScore float64) float64 {
	// Clamp score to valid range
	score := math.Max(-1.0, math.Min(1.0, regimeScore))

	// Base points
	neutralBlend := 0.5 // Balanced
	bullBlend := 0.3    // More MV (return-focused)
	bearBlend := 0.7    // More HRP (risk-focused)

	// Linear interpolation
	if score >= 0 {
		// Interpolate between neutral (0.5) and bull (0.3)
		blend := neutralBlend - (neutralBlend-bullBlend)*score
		return math.Max(0.0, math.Min(1.0, blend))
	} else {
		// Interpolate between neutral (0.5) and bear (0.7)
		absScore := math.Abs(score)
		blend := neutralBlend + (bearBlend-neutralBlend)*absScore
		return math.Max(0.0, math.Min(1.0, blend))
	}
}

// CalculateAdaptiveQualityGates calculates quality gate thresholds based on regime score
// Uses linear interpolation: Bull → lower thresholds, Bear → higher thresholds
// Returns QualityGateThresholds which implements the QualityGateThresholdsProvider interface
func (s *AdaptiveMarketService) CalculateAdaptiveQualityGates(regimeScore float64) *QualityGateThresholds {
	// Clamp score to valid range
	score := math.Max(-1.0, math.Min(1.0, regimeScore))

	// Base thresholds
	neutralFundamentals := 0.60
	neutralLongTerm := 0.50

	bullFundamentals := 0.55
	bullLongTerm := 0.45

	bearFundamentals := 0.65
	bearLongTerm := 0.55

	var fundamentals, longTerm float64

	if score >= 0 {
		// Interpolate between neutral and bull (lower thresholds)
		fundamentals = neutralFundamentals - (neutralFundamentals-bullFundamentals)*score
		longTerm = neutralLongTerm - (neutralLongTerm-bullLongTerm)*score
	} else {
		// Interpolate between neutral and bear (higher thresholds)
		absScore := math.Abs(score)
		fundamentals = neutralFundamentals + (bearFundamentals-neutralFundamentals)*absScore
		longTerm = neutralLongTerm + (bearLongTerm-neutralLongTerm)*absScore
	}

	return &QualityGateThresholds{
		Fundamentals: math.Max(0.0, math.Min(1.0, fundamentals)),
		LongTerm:     math.Max(0.0, math.Min(1.0, longTerm)),
	}
}
