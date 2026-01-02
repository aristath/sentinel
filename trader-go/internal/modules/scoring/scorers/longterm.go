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
	Score      float64            `json:"score"`       // Total score (0-1)
	Components map[string]float64 `json:"components"`  // Individual component scores
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
	// CAGR Score (40% weight)
	cagr5y := formulas.CalculateCAGR(monthlyPrices, 60) // 5 years
	if cagr5y == nil && len(monthlyPrices) > 0 {
		// Fallback to all available data
		cagr5y = formulas.CalculateCAGR(monthlyPrices, len(monthlyPrices))
	}
	cagrValue := 0.0
	if cagr5y != nil {
		cagrValue = *cagr5y
	}
	cagrScore := scoreCAGR(cagrValue, targetAnnualReturn)

	// Sharpe Score (25% weight)
	var sharpeRatio *float64
	if len(dailyPrices) >= 50 {
		sharpeRatio = formulas.CalculateSharpeFromPrices(dailyPrices, 0.02) // 2% risk-free rate
	}
	sharpeScore := scoreSharpe(sharpeRatio)

	// Sortino Score (35% weight)
	// Note: Sortino is passed in if available from PyFolio analytics
	sortinoScore := scoreSortino(sortinoRatio)

	// Combine with weights: 40% CAGR, 35% Sortino, 25% Sharpe
	totalScore := cagrScore*0.40 + sortinoScore*0.35 + sharpeScore*0.25
	totalScore = math.Min(1.0, totalScore)

	return LongTermScore{
		Score: round3(totalScore),
		Components: map[string]float64{
			"cagr":    round3(cagrScore),
			"sortino": round3(sortinoScore),
			"sharpe":  round3(sharpeScore),
		},
	}
}

// scoreCAGR scores CAGR using a bell curve
// Peak at target (default 11%), uses asymmetric Gaussian
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
