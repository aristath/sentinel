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
	return ds.CalculateEnhanced(dividendYield, payoutRatio, fiveYearAvgDivYield, nil)
}

// CalculateEnhanced calculates the dividend score with total return boost
// Accounts for both growth (CAGR) and dividends for a holistic return perspective.
//
// Components:
// - Dividend Yield (70%): Current yield level
// - Dividend Consistency (30%): Payout ratio and growth
// - Total Return Boost: Additional boost for high total return (growth + dividend)
//
// Example: 5% growth + 10% dividend = 15% total return gets boost
func (ds *DividendScorer) CalculateEnhanced(
	dividendYield *float64,
	payoutRatio *float64,
	fiveYearAvgDivYield *float64,
	expectedCAGR *float64, // Optional: CAGR for total return calculation
) DividendScore {
	yieldScore := scoreDividendYield(dividendYield)
	consistencyScore := scoreDividendConsistency(payoutRatio, fiveYearAvgDivYield)

	// Base score: 70% yield, 30% consistency
	baseScore := yieldScore*0.70 + consistencyScore*0.30

	// Calculate total return boost (growth + dividend)
	totalReturnBoost := calculateTotalReturnBoost(dividendYield, expectedCAGR)

	// Enhanced score: base + boost (capped at 1.0)
	enhancedScore := baseScore + totalReturnBoost
	enhancedScore = math.Min(1.0, enhancedScore)

	// Build components map with both scored values and dividend bonus
	components := map[string]float64{
		"yield":       round3(yieldScore),
		"consistency": round3(consistencyScore),
	}

	// Calculate dividend bonus for optimization returns calculation
	// Based on yield thresholds: High (6%+) = 0.10, Mid (3-6%) = 0.07, Low (<3%) = 0.03
	dividendBonus := calculateDividendBonus(dividendYield)
	components["dividend_bonus"] = dividendBonus

	// Store total return boost in components
	components["total_return_boost"] = round3(totalReturnBoost)

	// Calculate and store total return value if CAGR is available
	if expectedCAGR != nil && dividendYield != nil {
		totalReturn := *expectedCAGR + *dividendYield
		components["total_return"] = round3(totalReturn)
	}

	return DividendScore{
		Score:      round3(enhancedScore),
		Components: components,
	}
}

// calculateTotalReturnBoost calculates boost for high total return (growth + dividend)
// Rewards securities with high total return, not just high dividend yield.
//
// Example: 5% growth + 10% dividend = 15% total (excellent)
// vs 7% growth + 2% dividend = 9% total (lower)
//
// Boost thresholds:
// - 15%+ total return: +0.20 boost
// - 12-15% total return: +0.15 boost
// - 10-12% total return: +0.10 boost
// - Below 10%: no boost
func calculateTotalReturnBoost(dividendYield *float64, expectedCAGR *float64) float64 {
	if dividendYield == nil || expectedCAGR == nil {
		return 0.0
	}

	// Calculate total return = growth + dividend
	totalReturn := *expectedCAGR + *dividendYield

	// Boost score for high total return
	if totalReturn >= 0.15 {
		return 0.20 // 20% boost for 15%+ total return
	} else if totalReturn >= 0.12 {
		return 0.15 // 15% boost for 12-15% total return
	} else if totalReturn >= 0.10 {
		return 0.10 // 10% boost for 10-12% total return
	}

	return 0.0 // No boost below 10% total return
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

// calculateDividendBonus calculates dividend bonus value for optimization
// Based on yield thresholds: High (6%+) = 0.10, Mid (3-6%) = 0.07, Low (<3%) = 0.03
func calculateDividendBonus(dividendYield *float64) float64 {
	if dividendYield == nil || *dividendYield <= 0 {
		return 0.0
	}

	yield := *dividendYield

	if yield >= scoring.HighDividendThreshold { // 6%+
		return scoring.HighDividendBonus // 0.10
	} else if yield >= scoring.MidDividendThreshold { // 3-6%
		return scoring.MidDividendBonus // 0.07
	} else {
		return scoring.LowDividendBonus // 0.03
	}
}
