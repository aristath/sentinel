package scorers

import (
	"math"

	"github.com/aristath/arduino-trader/internal/modules/scoring"
	"github.com/aristath/arduino-trader/pkg/formulas"
)

// LongTermScorer calculates long-term performance score
// Faithful translation from Python: app/modules/scoring/domain/groups/long_term.py
type LongTermScorer struct{}

// LongTermScore represents the result of long-term scoring
type LongTermScore struct {
	Components map[string]float64 `json:"components"`
	Score      float64            `json:"score"`
}

// NewLongTermScorer creates a new long-term scorer
func NewLongTermScorer() *LongTermScorer {
	return &LongTermScorer{}
}

// Calculate calculates the long-term performance score
// Components:
// - CAGR (40%): Compound Annual Growth Rate
// - Sortino Ratio (35%): Downside risk-adjusted returns
// - Sharpe Ratio (25%): Overall risk-adjusted returns
func (lts *LongTermScorer) Calculate(
	monthlyPrices []formulas.MonthlyPrice,
	dailyPrices []float64,
	sortinoRatio *float64,
	targetAnnualReturn float64,
) LongTermScore {
	// Sharpe Score (25% weight) - calculate first for bubble detection
	var sharpeRatio *float64
	if len(dailyPrices) >= 50 {
		sharpeRatio = formulas.CalculateSharpeFromPrices(dailyPrices, 0.02) // 2% risk-free rate
	}
	sharpeScore := scoreSharpe(sharpeRatio)

	// Calculate volatility for bubble detection
	var volatility *float64
	if len(dailyPrices) >= 2 {
		volatility = formulas.CalculateVolatility(dailyPrices)
	}

	// CAGR Score (40% weight) - with bubble detection
	cagr5y := formulas.CalculateCAGR(monthlyPrices, 60) // 5 years
	if cagr5y == nil && len(monthlyPrices) > 0 {
		// Fallback to all available data
		cagr5y = formulas.CalculateCAGR(monthlyPrices, len(monthlyPrices))
	}
	cagrValue := 0.0
	if cagr5y != nil {
		cagrValue = *cagr5y
	}
	// Enhanced CAGR scoring with bubble detection
	cagrScore := scoreCAGRWithBubbleDetection(cagrValue, targetAnnualReturn, sharpeRatio, sortinoRatio, volatility)

	// Sortino Score (35% weight)
	// Note: Sortino is passed in if available from PyFolio analytics
	sortinoScore := scoreSortino(sortinoRatio)

	// Combine with weights: 40% CAGR, 35% Sortino, 25% Sharpe
	totalScore := cagrScore*0.40 + sortinoScore*0.35 + sharpeScore*0.25
	totalScore = math.Min(1.0, totalScore)

	// Build components map with both scored and raw values
	components := map[string]float64{
		"cagr":    round3(cagrScore),
		"sortino": round3(sortinoScore),
		"sharpe":  round3(sharpeScore),
	}

	// Store raw Sharpe ratio for database storage
	if sharpeRatio != nil {
		components["sharpe_raw"] = *sharpeRatio
	} else {
		components["sharpe_raw"] = 0.0
	}

	// Store raw CAGR value for total return calculation (growth + dividend)
	components["cagr_raw"] = round3(cagrValue)

	return LongTermScore{
		Score:      round3(totalScore),
		Components: components,
	}
}

// scoreCAGR scores CAGR using a bell curve
// Peak at target (default 11%), uses asymmetric Gaussian
// DEPRECATED: Use scoreCAGRWithBubbleDetection instead for enhanced scoring
func scoreCAGR(cagr, target float64) float64 {
	if cagr <= 0 {
		return scoring.BellCurveFloor
	}

	// Use different sigma based on which side of target we're on
	sigma := scoring.BellCurveSigmaLeft
	if cagr >= target {
		sigma = scoring.BellCurveSigmaRight
	}

	// Gaussian bell curve centered at target
	rawScore := math.Exp(-math.Pow(cagr-target, 2) / (2 * math.Pow(sigma, 2)))

	// Scale to range [BellCurveFloor, 1.0]
	return scoring.BellCurveFloor + rawScore*(1-scoring.BellCurveFloor)
}

// scoreCAGRWithBubbleDetection scores CAGR with risk-adjusted monotonic scoring above target
// and bubble detection to avoid unsustainable growth.
//
// Algorithm:
// - Below target: Bell curve (penalize being too low)
// - Above target: Monotonic (reward higher CAGR) IF quality (good risk metrics)
// - Bubble detection: High CAGR + poor risk metrics = cap at 0.6
//
// Args:
//   - cagr: Compound Annual Growth Rate
//   - target: Target CAGR (default 11%)
//   - sharpeRatio: Sharpe ratio for bubble detection (optional)
//   - sortinoRatio: Sortino ratio for bubble detection (optional)
//   - volatility: Annualized volatility for bubble detection (optional)
//
// Returns:
//   - Score from 0.15 to 1.0
func scoreCAGRWithBubbleDetection(
	cagr float64,
	target float64,
	sharpeRatio *float64,
	sortinoRatio *float64,
	volatility *float64,
) float64 {
	if cagr <= 0 {
		return scoring.BellCurveFloor
	}

	// Bubble detection: High CAGR with poor risk metrics = bubble
	// Threshold: CAGR > 1.5x target (e.g., 16.5% for 11% target)
	isBubble := false
	if cagr > target*1.5 {
		// Check risk metrics - if multiple are poor, it's likely a bubble
		poorRiskCount := 0

		// Poor Sharpe ratio
		if sharpeRatio != nil && *sharpeRatio < 0.5 {
			poorRiskCount++
		}

		// Poor Sortino ratio
		if sortinoRatio != nil && *sortinoRatio < 0.5 {
			poorRiskCount++
		}

		// Extreme volatility
		if volatility != nil && *volatility > 0.40 {
			poorRiskCount++
		}

		// If 2+ risk metrics are poor, consider it a bubble
		if poorRiskCount >= 2 {
			isBubble = true
		}
	}

	if isBubble {
		// Penalize bubbles: cap score at 0.6 even if CAGR is high
		return 0.6
	}

	// Quality high CAGR: reward it (monotonic scoring above target)
	if cagr >= target {
		excess := cagr - target

		// 11% = 0.8, 15% = 0.95, 20%+ = 1.0
		if excess >= 0.09 { // 20%+
			return 1.0
		} else if excess >= 0.04 { // 15%+
			// Linear interpolation: 0.95 to 1.0 over 5% excess (15% to 20%)
			return 0.95 + (excess-0.04)/0.05*0.05
		} else { // 11-15%
			// Linear interpolation: 0.8 to 0.95 over 4% excess (11% to 15%)
			return 0.8 + excess/0.04*0.15
		}
	}

	// Below target: use bell curve (penalize being too low)
	sigma := scoring.BellCurveSigmaLeft
	rawScore := math.Exp(-math.Pow(cagr-target, 2) / (2 * math.Pow(sigma, 2)))

	// Scale to range [BellCurveFloor, 1.0]
	return scoring.BellCurveFloor + rawScore*(1-scoring.BellCurveFloor)
}

// scoreSharpe converts Sharpe ratio to score
// Sharpe > 2.0 is excellent, > 1.0 is good
func scoreSharpe(sharpeRatio *float64) float64 {
	if sharpeRatio == nil {
		return 0.5
	}

	sharpe := *sharpeRatio

	if sharpe >= scoring.SharpeExcellent { // >= 2.0
		return 1.0
	} else if sharpe >= scoring.SharpeGood { // >= 1.0
		return 0.7 + (sharpe-scoring.SharpeGood)*0.3
	} else if sharpe >= scoring.SharpeOK { // >= 0.5
		return 0.4 + (sharpe-scoring.SharpeOK)*0.6
	} else if sharpe >= 0 {
		return sharpe * 0.8
	} else {
		return 0.0
	}
}

// scoreSortino converts Sortino ratio to score
// Sortino > 2.0 is excellent (focuses on downside risk)
func scoreSortino(sortinoRatio *float64) float64 {
	if sortinoRatio == nil {
		return 0.5
	}

	sortino := *sortinoRatio

	if sortino >= 2.0 {
		return 1.0
	} else if sortino >= 1.5 {
		return 0.8 + (sortino-1.5)*0.4
	} else if sortino >= 1.0 {
		return 0.6 + (sortino-1.0)*0.4
	} else if sortino >= 0.5 {
		return 0.4 + (sortino-0.5)*0.4
	} else if sortino >= 0 {
		return sortino * 0.8
	} else {
		return 0.0
	}
}
