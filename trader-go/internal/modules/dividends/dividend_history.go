package dividends

import (
	"math"
)

// Constants for dividend analysis
// Faithful translation from Python: app/modules/scoring/domain/constants.py
const (
	DividendCutThreshold              = 0.20 // 20% YoY cut = "big cut"
	HighDividendReinvestmentThreshold = 0.03 // 3% yield threshold for same-stock reinvestment
)

// DividendStabilityScore represents the result of dividend stability analysis
// Faithful translation from Python: calculate_dividend_stability_score return type
type DividendStabilityScore struct {
	Score                 float64  `json:"score"`
	HasBigCut             bool     `json:"has_big_cut"`
	YearsSinceCut         *int     `json:"years_since_cut,omitempty"`
	DividendGrowthRate    *float64 `json:"dividend_growth_rate,omitempty"`
	AbovePortfolioAverage bool     `json:"above_portfolio_avg"`
	CutPenalty            float64  `json:"cut_penalty"`
	GrowthBonus           float64  `json:"growth_bonus"`
	YieldBonus            float64  `json:"yield_bonus"`
}

// HasBigDividendCut checks for significant dividend cuts (>20% year-over-year)
// Faithful translation from Python: has_big_dividend_cut()
func HasBigDividendCut(dividendHistory []float64) (bool, *int) {
	if len(dividendHistory) < 2 {
		return false, nil
	}

	for i := 1; i < len(dividendHistory); i++ {
		prevDiv := dividendHistory[i-1]
		currDiv := dividendHistory[i]

		if prevDiv > 0 {
			change := (currDiv - prevDiv) / prevDiv
			if change < -DividendCutThreshold {
				yearsSince := len(dividendHistory) - i
				return true, &yearsSince
			}
		}
	}

	return false, nil
}

// CalculateDividendGrowthRate calculates compound annual dividend growth rate (CAGR)
// Faithful translation from Python: calculate_dividend_growth_rate()
func CalculateDividendGrowthRate(dividendHistory []float64) *float64 {
	if len(dividendHistory) < 2 {
		return nil
	}

	// Filter out zero/negative values at the start
	startIdx := -1
	for i, div := range dividendHistory {
		if div > 0 {
			startIdx = i
			break
		}
	}

	if startIdx == -1 {
		return nil // All zeros
	}

	validHistory := dividendHistory[startIdx:]
	if len(validHistory) < 2 {
		return nil
	}

	startDiv := validHistory[0]
	endDiv := validHistory[len(validHistory)-1]
	years := len(validHistory) - 1

	if startDiv <= 0 || years <= 0 {
		return nil
	}

	// Calculate CAGR: (end/start)^(1/years) - 1
	cagr := math.Pow(endDiv/startDiv, 1.0/float64(years)) - 1
	return &cagr
}

// calculateCutPenalty calculates penalty for dividend cuts and bonus for no cuts
// Faithful translation from Python: _calculate_cut_penalty()
func calculateCutPenalty(hasCut bool, yearsSince *int, dividendHistory []float64) (penalty, bonus float64) {
	if hasCut {
		if yearsSince != nil {
			if *yearsSince <= 2 {
				return 0.40, 0.0 // Full penalty for recent cuts
			} else if *yearsSince <= 5 {
				return 0.25, 0.0 // Partial penalty
			}
		}
		return 0.10, 0.0 // Old cut, less penalty
	}

	// Bonus for no cuts in history
	historyLength := len(dividendHistory)
	if historyLength >= 5 {
		return 0.0, 0.15 // Long track record without cuts
	} else if historyLength >= 3 {
		return 0.0, 0.10
	}
	return 0.0, 0.0
}

// calculateGrowthBonus calculates bonus based on dividend growth rate
// Faithful translation from Python: _calculate_growth_bonus()
func calculateGrowthBonus(growthRate *float64) float64 {
	if growthRate == nil {
		return 0.0
	}

	rate := *growthRate
	if rate >= 0.05 { // 5%+ annual growth
		return 0.30
	} else if rate >= 0.02 { // 2-5% growth
		return 0.20
	} else if rate >= 0 { // Stable
		return 0.10
	}
	return 0.0 // Declining
}

// calculateYieldBonus calculates bonus based on yield vs portfolio average
// Faithful translation from Python: _calculate_yield_bonus()
func calculateYieldBonus(currentYield *float64, portfolioAvgYield float64) (bonus float64, aboveAvg bool) {
	if currentYield == nil || *currentYield <= 0 {
		return 0.0, false
	}

	yield := *currentYield
	aboveAvg = yield >= portfolioAvgYield

	if yield >= portfolioAvgYield*1.5 {
		return 0.30, aboveAvg // Significantly above average
	} else if yield >= portfolioAvgYield {
		return 0.15, aboveAvg // Above average
	}
	return 0.0, aboveAvg
}

// CalculateDividendStabilityScore calculates dividend stability score
// Faithful translation from Python: calculate_dividend_stability_score()
//
// Components:
// - No big cuts (40%): Penalize if >20% cuts found
// - Growth trend (30%): Reward consistent growth
// - Above portfolio average (30%): Bonus if yield > portfolio avg
func CalculateDividendStabilityScore(
	dividendHistory []float64,
	portfolioAvgYield float64,
	currentYield *float64,
) DividendStabilityScore {
	result := DividendStabilityScore{
		Score:                 0.5, // Base score
		HasBigCut:             false,
		YearsSinceCut:         nil,
		DividendGrowthRate:    nil,
		AbovePortfolioAverage: false,
		CutPenalty:            0.0,
		GrowthBonus:           0.0,
		YieldBonus:            0.0,
	}

	// Check for big cuts (40% weight)
	hasCut, yearsSince := HasBigDividendCut(dividendHistory)
	result.HasBigCut = hasCut
	result.YearsSinceCut = yearsSince

	cutPenalty, noCutBonus := calculateCutPenalty(hasCut, yearsSince, dividendHistory)
	result.CutPenalty = cutPenalty
	result.Score -= cutPenalty
	result.Score += noCutBonus

	// Check growth trend (30% weight)
	growthRate := CalculateDividendGrowthRate(dividendHistory)
	result.DividendGrowthRate = growthRate
	growthBonus := calculateGrowthBonus(growthRate)
	result.GrowthBonus = growthBonus
	result.Score += growthBonus

	// Check vs portfolio average (30% weight)
	yieldBonus, aboveAvg := calculateYieldBonus(currentYield, portfolioAvgYield)
	result.YieldBonus = yieldBonus
	result.AbovePortfolioAverage = aboveAvg
	result.Score += yieldBonus

	// Clamp score to valid range [0.0, 1.0]
	result.Score = math.Max(0.0, math.Min(1.0, result.Score))

	// Round to 3 decimal places (matching Python)
	result.Score = math.Round(result.Score*1000) / 1000

	return result
}

// IsDividendConsistent is a quick check if a security has consistent dividends
// Faithful translation from Python: is_dividend_consistent()
//
// Used by the holistic planner to identify reliable income securities.
func IsDividendConsistent(
	symbolYield float64,
	portfolioAvgYield float64,
	stabilityScore float64,
	minStability float64,
) bool {
	// Must have some yield
	if symbolYield <= 0 {
		return false
	}

	// Must meet minimum stability
	if stabilityScore < minStability {
		return false
	}

	// Bonus points if above average (but not required)
	return true
}
