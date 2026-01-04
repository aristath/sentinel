package scorers

import (
	"math"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/scoring"
	"github.com/aristath/arduino-trader/internal/modules/scoring/domain"
	"github.com/aristath/arduino-trader/pkg/formulas"
)

// SecurityScorer orchestrates all scoring groups for a security
// Faithful translation from Python: app/modules/scoring/domain/security_scorer.py
type SecurityScorer struct {
	technicals      *TechnicalsScorer
	longTerm        *LongTermScorer
	opportunity     *OpportunityScorer
	dividend        *DividendScorer
	fundamentals    *FundamentalsScorer
	shortTerm       *ShortTermScorer
	opinion         *OpinionScorer
	diversification *DiversificationScorer
}

// ScoreWeights defines the weight for each scoring group
// Fixed weights (no longer configurable) - optimizer handles portfolio decisions
var ScoreWeights = map[string]float64{
	"long_term":       0.20, // CAGR, Sortino, Sharpe
	"fundamentals":    0.15, // Financial strength, Consistency
	"opportunity":     0.15, // 52W high distance, P/E ratio
	"dividends":       0.12, // Yield, Dividend consistency
	"short_term":      0.10, // Recent momentum, Drawdown
	"technicals":      0.10, // RSI, Bollinger, EMA
	"opinion":         0.10, // Analyst recommendations, Price targets
	"diversification": 0.08, // Geography, Industry, Averaging down
}

// NewSecurityScorer creates a new security scorer
func NewSecurityScorer() *SecurityScorer {
	return &SecurityScorer{
		technicals:      NewTechnicalsScorer(),
		longTerm:        NewLongTermScorer(),
		opportunity:     NewOpportunityScorer(),
		dividend:        NewDividendScorer(),
		fundamentals:    NewFundamentalsScorer(),
		shortTerm:       NewShortTermScorer(),
		opinion:         NewOpinionScorer(),
		diversification: NewDiversificationScorer(),
	}
}

// ScoreSecurityInput contains all data needed to score a security
type ScoreSecurityInput struct {
	PayoutRatio           *float64
	DebtToEquity          *float64
	PortfolioContext      *domain.PortfolioContext
	Industry              *string
	Country               *string
	SortinoRatio          *float64
	MaxDrawdown           *float64
	PERatio               *float64
	DividendYield         *float64
	UpsidePct             *float64
	ProfitMargin          *float64
	FiveYearAvgDivYield   *float64
	AnalystRecommendation *float64
	ForwardPE             *float64
	CurrentRatio          *float64
	Symbol                string
	DailyPrices           []float64
	MonthlyPrices         []formulas.MonthlyPrice
	MarketAvgPE           float64
	TargetAnnualReturn    float64
}

// ScoreSecurityWithDefaults scores a security with default values for missing data
func (ss *SecurityScorer) ScoreSecurityWithDefaults(input ScoreSecurityInput) *domain.CalculatedSecurityScore {
	// Set defaults
	if input.TargetAnnualReturn == 0 {
		input.TargetAnnualReturn = scoring.OptimalCAGR
	}
	if input.MarketAvgPE == 0 {
		input.MarketAvgPE = scoring.DefaultMarketAvgPE
	}

	return ss.ScoreSecurity(input)
}

// ScoreSecurity calculates complete security score with all groups
func (ss *SecurityScorer) ScoreSecurity(input ScoreSecurityInput) *domain.CalculatedSecurityScore {
	groupScores := make(map[string]float64)
	subScores := make(map[string]map[string]float64)

	// 1. Long-term Performance (20%)
	longTermScore := ss.longTerm.Calculate(
		input.MonthlyPrices,
		input.DailyPrices,
		input.SortinoRatio,
		input.TargetAnnualReturn,
	)
	groupScores["long_term"] = longTermScore.Score
	subScores["long_term"] = longTermScore.Components

	// 2. Fundamentals (15%)
	fundamentalsScore := ss.fundamentals.Calculate(
		input.ProfitMargin,
		input.DebtToEquity,
		input.CurrentRatio,
		input.MonthlyPrices,
	)
	groupScores["fundamentals"] = fundamentalsScore.Score
	subScores["fundamentals"] = fundamentalsScore.Components

	// 3. Opportunity (15%)
	opportunityScore := ss.opportunity.Calculate(
		input.DailyPrices,
		input.PERatio,
		input.ForwardPE,
		input.MarketAvgPE,
	)
	groupScores["opportunity"] = opportunityScore.Score
	subScores["opportunity"] = opportunityScore.Components

	// 4. Dividends (12%)
	dividendScore := ss.dividend.Calculate(
		input.DividendYield,
		input.PayoutRatio,
		input.FiveYearAvgDivYield,
	)
	groupScores["dividends"] = dividendScore.Score
	subScores["dividends"] = dividendScore.Components

	// 5. Short-term Performance (10%)
	shortTermScore := ss.shortTerm.Calculate(
		input.DailyPrices,
		input.MaxDrawdown,
	)
	groupScores["short_term"] = shortTermScore.Score
	subScores["short_term"] = shortTermScore.Components

	// 6. Technicals (10%)
	technicalsScore := ss.technicals.Calculate(input.DailyPrices)
	groupScores["technicals"] = technicalsScore.Score
	subScores["technicals"] = technicalsScore.Components

	// 7. Opinion (10%)
	opinionScore := ss.opinion.Calculate(
		input.AnalystRecommendation,
		input.UpsidePct,
	)
	groupScores["opinion"] = opinionScore.Score
	subScores["opinion"] = opinionScore.Components

	// 8. Diversification (8%) - DYNAMIC, portfolio-aware
	if input.PortfolioContext != nil && input.Country != nil {
		// Need quality and opportunity for averaging down calculation
		qualityApprox := (groupScores["long_term"] + groupScores["fundamentals"]) / 2
		diversificationScore := ss.diversification.Calculate(
			input.Symbol,
			*input.Country,
			input.Industry,
			qualityApprox,
			groupScores["opportunity"],
			input.PortfolioContext,
		)
		groupScores["diversification"] = diversificationScore.Score
		subScores["diversification"] = diversificationScore.Components
	} else {
		// No portfolio context - return neutral
		groupScores["diversification"] = 0.5
		subScores["diversification"] = map[string]float64{
			"country":   0.5,
			"industry":  0.5,
			"averaging": 0.5,
		}
	}

	// Normalize weights
	normalizedWeights := normalizeWeights(ScoreWeights)

	// Calculate weighted total
	totalScore := 0.0
	for group, score := range groupScores {
		weight := normalizedWeights[group]
		totalScore += score * weight
	}

	// Calculate volatility
	var volatility *float64
	if len(input.DailyPrices) >= 30 {
		returns := formulas.CalculateReturns(input.DailyPrices)
		vol := formulas.AnnualizedVolatility(returns)
		volatility = &vol
	}

	return &domain.CalculatedSecurityScore{
		Symbol:       input.Symbol,
		TotalScore:   round4(totalScore),
		Volatility:   volatility,
		CalculatedAt: time.Now(),
		GroupScores:  roundScores(groupScores),
		SubScores:    roundSubScores(subScores),
	}
}

// normalizeWeights ensures weights sum to 1.0
func normalizeWeights(weights map[string]float64) map[string]float64 {
	sum := 0.0
	for _, weight := range weights {
		sum += weight
	}

	if sum == 0 {
		return weights
	}

	normalized := make(map[string]float64, len(weights))
	for group, weight := range weights {
		normalized[group] = weight / sum
	}

	return normalized
}

// round4 rounds to 4 decimal places
func round4(f float64) float64 {
	return math.Round(f*10000) / 10000
}

// roundScores rounds all scores in map to 3 decimal places
func roundScores(scores map[string]float64) map[string]float64 {
	rounded := make(map[string]float64, len(scores))
	for k, v := range scores {
		rounded[k] = round3(v)
	}
	return rounded
}

// roundSubScores rounds all sub-scores to 3 decimal places
func roundSubScores(subScores map[string]map[string]float64) map[string]map[string]float64 {
	rounded := make(map[string]map[string]float64, len(subScores))
	for group, components := range subScores {
		rounded[group] = make(map[string]float64, len(components))
		for component, score := range components {
			rounded[group][component] = round3(score)
		}
	}
	return rounded
}
