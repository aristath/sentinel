package scorers

import (
	"math"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/scoring"
)

// WindfallScorer identifies excess gains vs expected growth
// Faithful translation from Python: app/modules/scoring/domain/windfall.py
//
// This module distinguishes between:
// - Consistent growers: Stocks performing at their historical rate
// - Windfalls: Unexpected gains significantly above historical average
//
// Used by the holistic planner to decide when to take profits
// without selling consistent performers prematurely.
type WindfallScorer struct{}

// WindfallScore represents the result of windfall scoring
type WindfallScore struct {
	Status         string  `json:"status,omitempty"`
	CurrentGain    float64 `json:"current_gain"`
	YearsHeld      float64 `json:"years_held"`
	HistoricalCAGR float64 `json:"historical_cagr"`
	ExpectedGain   float64 `json:"expected_gain"`
	ExcessGain     float64 `json:"excess_gain"`
	WindfallScore  float64 `json:"windfall_score"`
}

// ProfitTakingRecommendation represents whether and how much to sell
type ProfitTakingRecommendation struct {
	Reason           string  `json:"reason"`
	SuggestedSellPct float64 `json:"suggested_sell_pct"`
	ShouldSell       bool    `json:"should_sell"`
}

// WindfallAnalysis represents complete windfall analysis for a position
type WindfallAnalysis struct {
	Symbol            string                     `json:"symbol"`
	Error             string                     `json:"error,omitempty"`
	Recommendation    ProfitTakingRecommendation `json:"recommendation"`
	CurrentGainPct    float64                    `json:"current_gain_pct"`
	YearsHeld         float64                    `json:"years_held"`
	WindfallScore     float64                    `json:"windfall_score"`
	ExcessGainPct     float64                    `json:"excess_gain_pct"`
	ExpectedGainPct   float64                    `json:"expected_gain_pct"`
	HistoricalCAGRPct float64                    `json:"historical_cagr_pct"`
}

// NewWindfallScorer creates a new windfall scorer
func NewWindfallScorer() *WindfallScorer {
	return &WindfallScorer{}
}

// CalculateExcessGain calculates excess gain above expected based on historical CAGR
//
// Excess gain = actual gain - expected gain from historical growth
//
// Example 1: Consistent grower
//
//	held 3 years, up 61%, historical CAGR = 17%
//	expected = (1.17^3) - 1 = 60%
//	excess = 61% - 60% = 1%  -> No windfall
//
// Example 2: Sudden spike
//
//	held 1 year, up 80%, historical CAGR = 10%
//	expected = 10%
//	excess = 80% - 10% = 70%  -> Windfall!
//
// Args:
//
//	currentGain: Current profit percentage (e.g., 0.80 = 80% gain)
//	yearsHeld: Number of years position has been held
//	historicalCAGR: Security's historical compound annual growth rate
//
// Returns:
//
//	Excess gain as decimal (can be negative if underperforming)
func (ws *WindfallScorer) CalculateExcessGain(currentGain, yearsHeld, historicalCAGR float64) float64 {
	if yearsHeld <= 0 {
		return currentGain // No history = all excess
	}

	if historicalCAGR <= -1 {
		// Invalid CAGR (would cause math error)
		return currentGain
	}

	// Calculate expected gain: (1 + CAGR)^years - 1
	expectedGain := math.Pow(1+historicalCAGR, yearsHeld) - 1
	excess := currentGain - expectedGain

	return excess
}

// CalculateWindfallScore calculates windfall score (0-1) based on excess gain
//
// Higher score = more of a windfall = stronger signal to take profits.
//
// Args:
//
//	currentGain: Current profit percentage (optional, use nil if unknown)
//	yearsHeld: Years position held (optional, use nil if unknown)
//	historicalCAGR: Historical CAGR (optional, will default to 0.10 if nil)
//
// Returns:
//
//	WindfallScore with all components
func (ws *WindfallScorer) CalculateWindfallScore(
	currentGain *float64,
	yearsHeld *float64,
	historicalCAGR *float64,
) WindfallScore {
	// Default historical CAGR to market average if not provided
	defaultCAGR := 0.10
	cagr := defaultCAGR
	if historicalCAGR != nil {
		cagr = *historicalCAGR
	}

	// If we don't have current gain or years held, return neutral
	if currentGain == nil || yearsHeld == nil {
		return WindfallScore{
			Status:         "insufficient_data",
			HistoricalCAGR: round4(cagr),
			WindfallScore:  0.0,
		}
	}

	gain := *currentGain
	years := *yearsHeld

	// Calculate excess gain
	excess := ws.CalculateExcessGain(gain, years, cagr)

	// Calculate expected gain
	expectedGain := 0.0
	if years > 0 {
		expectedGain = math.Pow(1+cagr, years) - 1
	}

	// Calculate score based on excess
	var windfallScore float64
	if excess >= scoring.WindfallExcessHigh { // 50%+ excess
		windfallScore = 1.0
	} else if excess >= scoring.WindfallExcessMedium { // 25-50% excess
		// Linear interpolation from 0.5 to 1.0
		windfallScore = 0.5 + ((excess-scoring.WindfallExcessMedium)/(scoring.WindfallExcessHigh-scoring.WindfallExcessMedium))*0.5
	} else if excess > 0 { // 0-25% excess
		// Linear interpolation from 0.0 to 0.5
		windfallScore = (excess / scoring.WindfallExcessMedium) * 0.5
	} else {
		// No excess or underperforming
		windfallScore = 0.0
	}

	return WindfallScore{
		CurrentGain:    round4(gain),
		YearsHeld:      round2(years),
		HistoricalCAGR: round4(cagr),
		ExpectedGain:   round4(expectedGain),
		ExcessGain:     round4(excess),
		WindfallScore:  round3(windfallScore),
	}
}

// ShouldTakeProfits determines if profits should be taken and how much
//
// Rules:
// 1. If doubled money (100%+ gain):
//   - Windfall doubler (excess > 30%): sell 50%
//   - Consistent doubler: sell 30%
//
// 2. If excess gain > 50%: sell 40%
// 3. If excess gain > 25%: sell 20%
// 4. Otherwise: don't sell based on gains
//
// Args:
//
//	currentGain: Current profit percentage
//	yearsHeld: Years position held
//	historicalCAGR: Historical CAGR
//
// Returns:
//
//	ProfitTakingRecommendation with decision, percentage, and reason
func (ws *WindfallScorer) ShouldTakeProfits(currentGain, yearsHeld, historicalCAGR float64) ProfitTakingRecommendation {
	excess := ws.CalculateExcessGain(currentGain, yearsHeld, historicalCAGR)

	// Doubled money rule
	if currentGain >= 1.0 { // 100%+ gain
		if excess > 0.30 { // Significant windfall component
			return ProfitTakingRecommendation{
				ShouldSell:       true,
				SuggestedSellPct: 0.50,
				Reason:           formatWindfallReason("Windfall doubler", currentGain, excess),
			}
		}
		return ProfitTakingRecommendation{
			ShouldSell:       true,
			SuggestedSellPct: scoring.ConsistentDoubleSellPct,
			Reason:           formatConsistentDoublerReason(currentGain, scoring.ConsistentDoubleSellPct),
		}
	}

	// Windfall rules
	if excess >= scoring.WindfallExcessHigh { // 50%+ above expected
		return ProfitTakingRecommendation{
			ShouldSell:       true,
			SuggestedSellPct: scoring.WindfallSellPctHigh,
			Reason:           formatExcessReason("High windfall", excess),
		}
	} else if excess >= scoring.WindfallExcessMedium { // 25-50% above expected
		return ProfitTakingRecommendation{
			ShouldSell:       true,
			SuggestedSellPct: scoring.WindfallSellPctMedium,
			Reason:           formatExcessReason("Medium windfall", excess),
		}
	}

	// No windfall - don't sell
	var reason string
	if excess > 0 {
		reason = formatPerformingReason(excess)
	} else if excess > -0.10 {
		reason = "Performing near expectations"
	} else {
		reason = formatUnderperformingReason(excess)
	}

	return ProfitTakingRecommendation{
		ShouldSell:       false,
		SuggestedSellPct: 0.0,
		Reason:           reason,
	}
}

// GetWindfallRecommendation gets complete windfall analysis for a position
//
// Convenience function that calculates all windfall metrics
// and returns a recommendation.
//
// Args:
//
//	symbol: Security symbol
//	currentPrice: Current market price
//	avgPrice: Average purchase price
//	firstBoughtAt: Time of first purchase (optional)
//	historicalCAGR: Historical CAGR (optional, defaults to 0.10)
//
// Returns:
//
//	WindfallAnalysis with complete analysis and recommendation
func (ws *WindfallScorer) GetWindfallRecommendation(
	symbol string,
	currentPrice float64,
	avgPrice float64,
	firstBoughtAt *time.Time,
	historicalCAGR *float64,
) WindfallAnalysis {
	// Calculate current gain
	if avgPrice <= 0 {
		return WindfallAnalysis{
			Symbol: symbol,
			Error:  "Invalid average price",
		}
	}

	currentGain := (currentPrice - avgPrice) / avgPrice

	// Calculate years held
	yearsHeld := 1.0 // Default
	if firstBoughtAt != nil {
		daysHeld := time.Since(*firstBoughtAt).Hours() / 24
		yearsHeld = math.Max(0.1, daysHeld/365.0) // Minimum 0.1 years
	}

	// Get windfall score
	score := ws.CalculateWindfallScore(&currentGain, &yearsHeld, historicalCAGR)

	// Get recommendation
	cagr := score.HistoricalCAGR
	recommendation := ws.ShouldTakeProfits(currentGain, yearsHeld, cagr)

	return WindfallAnalysis{
		Symbol:            symbol,
		CurrentGainPct:    round1(currentGain * 100),
		YearsHeld:         round2(yearsHeld),
		WindfallScore:     score.WindfallScore,
		ExcessGainPct:     round1(score.ExcessGain * 100),
		ExpectedGainPct:   round1(score.ExpectedGain * 100),
		HistoricalCAGRPct: round1(cagr * 100),
		Recommendation:    recommendation,
	}
}

// Helper functions for formatting reasons

func formatWindfallReason(label string, gain, excess float64) string {
	return roundPercent(label, gain*100) + " gain with " + roundPercent("", excess*100) + "% excess"
}

func formatConsistentDoublerReason(gain, sellPct float64) string {
	return roundPercent("Consistent doubler", gain*100) + " gain, taking " + roundPercent("", sellPct*100) + "%"
}

func formatExcessReason(label string, excess float64) string {
	return label + ": " + roundPercent("", excess*100) + "% above expected growth"
}

func formatPerformingReason(excess float64) string {
	return "Performing " + roundPercent("", excess*100) + "% above expected, but within normal range"
}

func formatUnderperformingReason(excess float64) string {
	return "Underperforming by " + roundPercent("", math.Abs(excess)*100) + "%"
}
