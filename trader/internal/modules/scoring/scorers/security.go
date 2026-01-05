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
// Quality-focused weights for 15-20 year retirement fund strategy
// Emphasizes quality (long-term + fundamentals = 45%) and dividends (18%)
var ScoreWeights = map[string]float64{
	"long_term":       0.25, // CAGR, Sortino, Sharpe (↑ from 20%)
	"fundamentals":    0.20, // Financial strength, Consistency (↑ from 15%)
	"dividends":       0.18, // Yield, Consistency, Growth (↑ from 12%)
	"opportunity":     0.12, // 52W high distance, P/E ratio (↓ from 15%)
	"short_term":      0.08, // Recent momentum, Drawdown (↓ from 10%)
	"technicals":      0.07, // RSI, Bollinger, EMA (↓ from 10%)
	"opinion":         0.05, // Analyst recommendations, Price targets (↓ from 10%)
	"diversification": 0.05, // Geography, Industry, Averaging down (↓ from 8%)
	// Total: 100%
	//
	// Rationale:
	// - Quality focus: Long-term + Fundamentals = 45% (vs 35% before)
	// - Dividend emphasis: 18% (vs 12%) - accounts for total return (growth + dividend)
	// - Opportunity reduced: 12% (vs 15%) - use as filter, not primary driver
	// - Technicals reduced: 7% (vs 10%) - less important for long-term
	// - Opinion reduced: 5% (vs 10%) - external forecasts less reliable
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
	ProductType           string // Product type: EQUITY, ETF, MUTUALFUND, ETC, CASH, UNKNOWN
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

	// 1. Long-term Performance (25%) - CAGR, Sortino, Sharpe
	longTermScore := ss.longTerm.Calculate(
		input.MonthlyPrices,
		input.DailyPrices,
		input.SortinoRatio,
		input.TargetAnnualReturn,
	)
	groupScores["long_term"] = longTermScore.Score
	subScores["long_term"] = longTermScore.Components

	// 2. Fundamentals (20%) - Financial strength, Consistency
	fundamentalsScore := ss.fundamentals.Calculate(
		input.ProfitMargin,
		input.DebtToEquity,
		input.CurrentRatio,
		input.MonthlyPrices,
	)
	groupScores["fundamentals"] = fundamentalsScore.Score
	subScores["fundamentals"] = fundamentalsScore.Components

	// 3. Opportunity (12%) - 52W high distance, P/E ratio (with quality gates)
	opportunityScore := ss.opportunity.CalculateWithQualityGate(
		input.DailyPrices,
		input.PERatio,
		input.ForwardPE,
		input.MarketAvgPE,
		&fundamentalsScore.Score, // Pass fundamentals score for quality gate
		&longTermScore.Score,     // Pass long-term score for quality gate
		input.ProductType,        // Pass product type for product-type-aware opportunity scoring
	)
	groupScores["opportunity"] = opportunityScore.Score
	subScores["opportunity"] = opportunityScore.Components

	// 4. Dividends (18%) - Yield, Consistency, Growth (with total return boost)
	// Extract CAGR from long-term components for total return calculation
	var expectedCAGR *float64
	if cagrRaw, hasCAGR := longTermScore.Components["cagr_raw"]; hasCAGR && cagrRaw > 0 {
		expectedCAGR = &cagrRaw
	}
	dividendScore := ss.dividend.CalculateEnhanced(
		input.DividendYield,
		input.PayoutRatio,
		input.FiveYearAvgDivYield,
		expectedCAGR,
	)
	groupScores["dividends"] = dividendScore.Score
	subScores["dividends"] = dividendScore.Components

	// 5. Short-term Performance (8%) - Recent momentum, Drawdown
	shortTermScore := ss.shortTerm.Calculate(
		input.DailyPrices,
		input.MaxDrawdown,
	)
	groupScores["short_term"] = shortTermScore.Score
	subScores["short_term"] = shortTermScore.Components

	// 6. Technicals (7%) - RSI, Bollinger, EMA
	technicalsScore := ss.technicals.Calculate(input.DailyPrices)
	groupScores["technicals"] = technicalsScore.Score
	subScores["technicals"] = technicalsScore.Components

	// 7. Opinion (5%) - Analyst recommendations, Price targets
	opinionScore := ss.opinion.Calculate(
		input.AnalystRecommendation,
		input.UpsidePct,
	)
	groupScores["opinion"] = opinionScore.Score
	subScores["opinion"] = opinionScore.Components

	// 8. Diversification (5%) - DYNAMIC, portfolio-aware
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

	// Get product-type-aware weights
	weights := ss.getScoreWeights(input.ProductType)

	// Normalize weights
	normalizedWeights := normalizeWeights(weights)

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

// getScoreWeights returns score weights based on product type
// Implements product-type-aware scoring weights as per PRODUCT_TYPE_DIFFERENTIATION.md
func (ss *SecurityScorer) getScoreWeights(productType string) map[string]float64 {
	// Treat ETFs and Mutual Funds identically (both are diversified products)
	if productType == "ETF" || productType == "MUTUALFUND" {
		// Diversified product weights (ETFs & Mutual Funds)
		return map[string]float64{
			"long_term":       0.35, // ↑ from 25% (tracking quality matters)
			"fundamentals":    0.10, // ↓ from 20% (less relevant)
			"dividends":       0.18, // Same
			"opportunity":     0.12, // Same
			"short_term":      0.08, // Same
			"technicals":      0.07, // Same
			"opinion":         0.05, // Same
			"diversification": 0.05, // Same
		}
	}

	// Default weights for stocks (EQUITY) and other types
	return ScoreWeights
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
