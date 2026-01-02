package scorers

import (
	"math"

	"github.com/aristath/arduino-trader/pkg/formulas"
)

// FundamentalsScorer calculates company health and stability score
// Faithful translation from Python: app/modules/scoring/domain/groups/fundamentals.py
type FundamentalsScorer struct{}

// FundamentalsScore represents the result of fundamentals scoring
type FundamentalsScore struct {
	Score      float64            `json:"score"`      // Total score (0-1)
	Components map[string]float64 `json:"components"` // Individual component scores
}

// NewFundamentalsScorer creates a new fundamentals scorer
func NewFundamentalsScorer() *FundamentalsScorer {
	return &FundamentalsScorer{}
}

// Calculate calculates the fundamentals score
// Components:
// - Financial Strength (60%): Profit margin, debt/equity, current ratio
// - Consistency (40%): 5-year vs 10-year CAGR similarity
func (fs *FundamentalsScorer) Calculate(
	profitMargin *float64,
	debtToEquity *float64,
	currentRatio *float64,
	monthlyPrices []formulas.MonthlyPrice,
) FundamentalsScore {
	financialScore := calculateFinancialStrength(profitMargin, debtToEquity, currentRatio)

	// Calculate CAGR for consistency
	cagr5y := formulas.CalculateCAGR(monthlyPrices, 60)
	if cagr5y == nil && len(monthlyPrices) > 0 {
		cagr5y = formulas.CalculateCAGR(monthlyPrices, len(monthlyPrices))
	}

	var cagr10y *float64
	if len(monthlyPrices) > 60 {
		cagr10y = formulas.CalculateCAGR(monthlyPrices, len(monthlyPrices))
	}

	cagr5yValue := 0.0
	if cagr5y != nil {
		cagr5yValue = *cagr5y
	}

	consistencyScore := calculateConsistency(cagr5yValue, cagr10y)

	// 60% financial strength, 40% consistency
	totalScore := financialScore*0.60 + consistencyScore*0.40
	totalScore = math.Min(1.0, totalScore)

	return FundamentalsScore{
		Score: round3(totalScore),
		Components: map[string]float64{
			"financial_strength": round3(financialScore),
			"consistency":        round3(consistencyScore),
		},
	}
}

// calculateFinancialStrength scores financial health
// Components: Profit Margin (40%), Debt/Equity (30%), Current Ratio (30%)
func calculateFinancialStrength(profitMargin, debtToEquity, currentRatio *float64) float64 {
	// Profit margin (40%): Higher = better
	marginScore := 0.5
	if profitMargin != nil {
		margin := *profitMargin
		if margin >= 0 {
			marginScore = math.Min(1.0, 0.5+margin*2.5)
		} else {
			marginScore = math.Max(0, 0.5+margin*2)
		}
	}

	// Debt/Equity (30%): Lower = better (cap at 200)
	de := 50.0
	if debtToEquity != nil {
		de = math.Min(200, *debtToEquity)
	}
	deScore := math.Max(0, 1-de/200)

	// Current ratio (30%): Higher = better (cap at 3)
	cr := 1.0
	if currentRatio != nil {
		cr = math.Min(3, *currentRatio)
	}
	crScore := math.Min(1.0, cr/2)

	return marginScore*0.40 + deScore*0.30 + crScore*0.30
}

// calculateConsistency scores CAGR consistency between 5y and 10y
// Consistent growers (similar CAGR) score higher
func calculateConsistency(cagr5y float64, cagr10y *float64) float64 {
	if cagr10y == nil {
		return 0.6 // Neutral for newer stocks
	}

	diff := math.Abs(cagr5y - *cagr10y)

	if diff < 0.02 { // Within 2%
		return 1.0
	} else if diff < 0.05 { // Within 5%
		return 0.8
	} else {
		return math.Max(0.4, 1.0-diff*4)
	}
}
