package scorers

import (
	"math"

	"github.com/aristath/arduino-trader/internal/modules/scoring"
)

// ShortTermScorer calculates short-term performance score
// Faithful translation from Python: app/modules/scoring/domain/groups/short_term.py
type ShortTermScorer struct{}

// ShortTermScore represents the result of short-term scoring
type ShortTermScore struct {
	Score      float64            `json:"score"`      // Total score (0-1)
	Components map[string]float64 `json:"components"` // Individual component scores
}

// NewShortTermScorer creates a new short-term scorer
func NewShortTermScorer() *ShortTermScorer {
	return &ShortTermScorer{}
}

// Calculate calculates the short-term performance score
// Components:
// - Recent Momentum (50%): 30-day and 90-day price performance
// - Max Drawdown (50%): Recent drawdown severity
func (sts *ShortTermScorer) Calculate(
	dailyPrices []float64,
	maxDrawdown *float64,
) ShortTermScore {
	momentum := calculateMomentum(dailyPrices)
	momentumScore := scoreMomentum(momentum)

	drawdownScore := scoreDrawdown(maxDrawdown)

	// 50% momentum, 50% drawdown
	totalScore := momentumScore*0.50 + drawdownScore*0.50
	totalScore = math.Min(1.0, totalScore)

	return ShortTermScore{
		Score: round3(totalScore),
		Components: map[string]float64{
			"momentum": round3(momentumScore),
			"drawdown": round3(drawdownScore),
		},
	}
}

// calculateMomentum calculates blended momentum from 30-day and 90-day
func calculateMomentum(dailyPrices []float64) *float64 {
	if len(dailyPrices) < 30 {
		return nil
	}

	current := dailyPrices[len(dailyPrices)-1]

	// 30-day momentum
	var momentum30d float64
	if len(dailyPrices) >= 30 {
		price30d := dailyPrices[len(dailyPrices)-30]
		if price30d > 0 {
			momentum30d = (current - price30d) / price30d
		}
	}

	// 90-day momentum
	var momentum90d float64
	hasMomentum90d := false
	if len(dailyPrices) >= 90 {
		price90d := dailyPrices[len(dailyPrices)-90]
		if price90d > 0 {
			momentum90d = (current - price90d) / price90d
			hasMomentum90d = true
		}
	}

	// Blend (60% 30-day, 40% 90-day)
	var blended float64
	if hasMomentum90d {
		blended = momentum30d*0.6 + momentum90d*0.4
	} else {
		blended = momentum30d
	}

	return &blended
}

// scoreMomentum converts momentum to score
// Optimal: 5-15% gain, positive momentum = higher score
func scoreMomentum(momentum *float64) float64 {
	if momentum == nil {
		return 0.5
	}

	m := *momentum

	// Optimal: 5-15% gain over period
	if m >= 0.05 && m <= 0.15 {
		return 1.0
	} else if m >= 0 && m < 0.05 {
		return 0.6 + (m/0.05)*0.4
	} else if m > 0.15 && m <= 0.30 {
		// Still good but watch for overextension
		return 0.8 + (0.30-m)/0.15*0.2
	} else if m > 0.30 {
		// Too fast, might be overextended
		return math.Max(0.5, 0.8-(m-0.30)*2)
	} else if m >= -0.10 && m < 0 {
		// Small dip, could be opportunity
		return 0.5 + (m+0.10)/0.10*0.1
	} else {
		// Significant decline
		return math.Max(0.2, 0.5+m*3)
	}
}

// scoreDrawdown scores based on max drawdown severity
// Lower drawdown = higher score (better resilience)
func scoreDrawdown(maxDrawdown *float64) float64 {
	if maxDrawdown == nil {
		return 0.5
	}

	ddPct := math.Abs(*maxDrawdown)

	if ddPct <= scoring.DrawdownExcellent { // <= 10%
		return 1.0
	} else if ddPct <= scoring.DrawdownGood { // <= 20%
		return 0.8 + (scoring.DrawdownGood-ddPct)*2
	} else if ddPct <= scoring.DrawdownOK { // <= 30%
		return 0.6 + (scoring.DrawdownOK-ddPct)*2
	} else if ddPct <= scoring.DrawdownPoor { // <= 50%
		return 0.2 + (scoring.DrawdownPoor-ddPct)*2
	} else {
		return math.Max(0.0, 0.2-(ddPct-scoring.DrawdownPoor))
	}
}
