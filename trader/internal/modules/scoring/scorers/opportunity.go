package scorers

import (
	"math"

	"github.com/aristath/arduino-trader/internal/modules/scoring"
	"github.com/aristath/arduino-trader/pkg/formulas"
)

// OpportunityScorer calculates opportunity (value/dip) score
// Faithful translation from Python: app/modules/scoring/domain/groups/opportunity.py
type OpportunityScorer struct{}

// OpportunityScore represents the result of opportunity scoring
type OpportunityScore struct {
	Components map[string]float64 `json:"components"`
	Score      float64            `json:"score"`
}

// NewOpportunityScorer creates a new opportunity scorer
func NewOpportunityScorer() *OpportunityScorer {
	return &OpportunityScorer{}
}

// Calculate calculates the opportunity score from daily prices and fundamentals
// Components:
// - Below 52-week High (50%): Distance from peak - dip opportunity
// - P/E vs Market (50%): Below average = undervalued
func (os *OpportunityScorer) Calculate(
	dailyPrices []float64,
	peRatio *float64,
	forwardPE *float64,
	marketAvgPE float64,
) OpportunityScore {
	if len(dailyPrices) < scoring.MinDaysForOpportunity {
		// Insufficient data - return neutral score
		return OpportunityScore{
			Score: 0.5,
			Components: map[string]float64{
				"below_52w_high": 0.5,
				"pe_ratio":       0.5,
			},
		}
	}

	currentPrice := dailyPrices[len(dailyPrices)-1]

	// Calculate 52-week high distance score
	high52w := formulas.Calculate52WeekHigh(dailyPrices)
	below52wScore := scoreBelow52WeekHigh(currentPrice, high52w)

	// Calculate P/E ratio score
	peScore := scorePERatio(peRatio, forwardPE, marketAvgPE)

	// Combined score (50/50 split)
	totalScore := below52wScore*0.50 + peScore*0.50
	totalScore = math.Min(1.0, totalScore)

	return OpportunityScore{
		Score: round3(totalScore),
		Components: map[string]float64{
			"below_52w_high": round3(below52wScore),
			"pe_ratio":       round3(peScore),
		},
	}
}

// scoreBelow52WeekHigh scores based on distance below 52-week high
// Further below = HIGHER score (buying opportunity)
func scoreBelow52WeekHigh(currentPrice float64, high52w *float64) float64 {
	if high52w == nil || *high52w <= 0 {
		return 0.5
	}

	pctBelow := (*high52w - currentPrice) / *high52w

	if pctBelow <= 0 {
		// At or above high = expensive
		return 0.2
	} else if pctBelow < scoring.BelowHighOK { // 0-10%
		return 0.2 + (pctBelow/scoring.BelowHighOK)*0.3 // 0.2-0.5
	} else if pctBelow < scoring.BelowHighGood { // 10-20%
		return 0.5 + ((pctBelow-scoring.BelowHighOK)/0.10)*0.3 // 0.5-0.8
	} else if pctBelow < scoring.BelowHighExcellent { // 20-30%
		return 0.8 + ((pctBelow-scoring.BelowHighGood)/0.10)*0.2 // 0.8-1.0
	} else { // 30%+ below
		return 1.0
	}
}

// scorePERatio scores based on P/E vs market average
// Below average = HIGHER score (cheap)
func scorePERatio(peRatio, forwardPE *float64, marketAvgPE float64) float64 {
	if peRatio == nil || *peRatio <= 0 {
		// Penalty for missing P/E data - unknown = risky
		return 0.3
	}

	// Blend current and forward P/E
	effectivePE := *peRatio
	if forwardPE != nil && *forwardPE > 0 {
		effectivePE = (*peRatio + *forwardPE) / 2
	}

	pctDiff := (effectivePE - marketAvgPE) / marketAvgPE

	if pctDiff >= 0.20 { // 20%+ above average
		return 0.2 // Expensive
	} else if pctDiff >= 0 { // 0-20% above
		return 0.5 - (pctDiff/0.20)*0.3 // 0.5-0.2
	} else if pctDiff >= -0.10 { // 0-10% below
		return 0.5 + (math.Abs(pctDiff)/0.10)*0.2 // 0.5-0.7
	} else if pctDiff >= -0.20 { // 10-20% below
		return 0.7 + ((math.Abs(pctDiff)-0.10)/0.10)*0.3 // 0.7-1.0
	} else { // 20%+ below
		return 1.0
	}
}

// IsPriceTooHigh checks if price is too close to 52-week high for buying
// Guardrail to prevent chasing all-time highs
func IsPriceTooHigh(currentPrice float64, high52w *float64, maxPriceVs52wHigh float64) bool {
	if high52w == nil || *high52w <= 0 {
		return false // No data, allow trade
	}
	return currentPrice >= *high52w*maxPriceVs52wHigh
}
