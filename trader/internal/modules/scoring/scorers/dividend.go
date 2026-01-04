package scorers

import (
	"math"

	"github.com/aristath/arduino-trader/internal/modules/scoring"
)

// DividendScorer calculates dividend quality score
// Faithful translation from Python: app/modules/scoring/domain/groups/dividends.py
type DividendScorer struct{}

// DividendScore represents the result of dividend scoring
type DividendScore struct {
	Components map[string]float64 `json:"components"`
	Score      float64            `json:"score"`
}

// NewDividendScorer creates a new dividend scorer
func NewDividendScorer() *DividendScorer {
	return &DividendScorer{}
}

// Calculate calculates the dividend score
// Components:
// - Dividend Yield (70%): Current yield level
// - Dividend Consistency (30%): Payout ratio and growth
func (ds *DividendScorer) Calculate(
	dividendYield *float64,
	payoutRatio *float64,
	fiveYearAvgDivYield *float64,
) DividendScore {
	yieldScore := scoreDividendYield(dividendYield)
	consistencyScore := scoreDividendConsistency(payoutRatio, fiveYearAvgDivYield)

	// 70% yield, 30% consistency
	totalScore := yieldScore*0.70 + consistencyScore*0.30
	totalScore = math.Min(1.0, totalScore)

	return DividendScore{
		Score: round3(totalScore),
		Components: map[string]float64{
			"yield":       round3(yieldScore),
			"consistency": round3(consistencyScore),
		},
	}
}

// scoreDividendYield scores based on dividend yield
// Higher yield = higher score for income-focused investing
func scoreDividendYield(dividendYield *float64) float64 {
	if dividendYield == nil || *dividendYield <= 0 {
		return 0.3 // Base score for non-dividend stocks
	}

	yield := *dividendYield

	if yield >= scoring.HighDividendThreshold { // 6%+ yield
		return 1.0
	} else if yield >= scoring.MidDividendThreshold { // 3-6% yield
		// Linear scale from 0.7 to 1.0
		pct := (yield - scoring.MidDividendThreshold) / (scoring.HighDividendThreshold - scoring.MidDividendThreshold)
		return 0.7 + pct*0.3
	} else if yield >= 0.01 { // 1-3% yield
		// Linear scale from 0.4 to 0.7
		pct := (yield - 0.01) / (scoring.MidDividendThreshold - 0.01)
		return 0.4 + pct*0.3
	} else { // 0-1% yield
		return 0.3 + (yield/0.01)*0.1
	}
}

// scoreDividendConsistency scores based on dividend consistency/growth
// Uses payout ratio (30-60% ideal) and 5-year dividend growth
func scoreDividendConsistency(payoutRatio, fiveYearAvgDivYield *float64) float64 {
	// Payout ratio score
	payoutScore := 0.5
	if payoutRatio != nil {
		ratio := *payoutRatio
		if ratio >= 0.3 && ratio <= 0.6 {
			payoutScore = 1.0
		} else if ratio < 0.3 {
			payoutScore = 0.5 + (ratio/0.3)*0.5
		} else if ratio <= 0.8 {
			payoutScore = 1.0 - ((ratio-0.6)/0.2)*0.3
		} else {
			payoutScore = 0.4 // High payout = risky
		}
	}

	// 5-year dividend growth score
	growthScore := 0.5
	if fiveYearAvgDivYield != nil {
		growthScore = math.Min(1.0, 0.5+*fiveYearAvgDivYield*5)
	}

	return payoutScore*0.5 + growthScore*0.5
}
