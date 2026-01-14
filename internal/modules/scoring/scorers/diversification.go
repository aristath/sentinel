// Package scorers provides security scoring implementations.
package scorers

import (
	"math"

	"github.com/aristath/sentinel/internal/modules/scoring"
	"github.com/aristath/sentinel/internal/modules/scoring/domain"
	"github.com/aristath/sentinel/internal/utils"
)

// DiversificationScorer calculates portfolio fit and balance score
// Faithful translation from Python: app/modules/scoring/domain/diversification.py
type DiversificationScorer struct{}

// DiversificationScore represents the result of diversification scoring
type DiversificationScore struct {
	Components map[string]float64 `json:"components"`
	Score      float64            `json:"score"`
}

// NewDiversificationScorer creates a new diversification scorer
func NewDiversificationScorer() *DiversificationScorer {
	return &DiversificationScorer{}
}

// Calculate calculates the diversification score based on portfolio awareness
// Components:
// - Geography Gap (40%): Boost underweight regions
// - Industry Gap (30%): Boost underweight sectors
// - Averaging Down (30%): Bonus for quality dips we own
func (ds *DiversificationScorer) Calculate(
	symbol string,
	geography string,
	industry *string,
	qualityScore float64,
	opportunityScore float64,
	portfolioContext *domain.PortfolioContext,
) DiversificationScore {
	// Default neutral scores if no portfolio context
	if portfolioContext == nil {
		return DiversificationScore{
			Score: 0.5,
			Components: map[string]float64{
				"geography": 0.5,
				"industry":  0.5,
				"averaging": 0.5,
			},
		}
	}

	geoGapScore := calculateGeoGapScore(geography, portfolioContext)
	industryGapScore := calculateIndustryGapScore(industry, portfolioContext)
	averagingDownScore := calculateAveragingDownScore(symbol, qualityScore, opportunityScore, portfolioContext)

	// Weights: 40% geography, 30% industry, 30% averaging
	totalScore := geoGapScore*0.40 + industryGapScore*0.30 + averagingDownScore*0.30
	totalScore = math.Min(1.0, totalScore)

	return DiversificationScore{
		Score: round3(totalScore),
		Components: map[string]float64{
			"geography": round3(geoGapScore),
			"industry":  round3(industryGapScore),
			"averaging": round3(averagingDownScore),
		},
	}
}

// calculateGeoGapScore calculates geography gap score (40% weight)
// Higher weight = underweight region = higher score (buy to rebalance)
// For securities with multiple geographies, returns the highest score.
func calculateGeoGapScore(geography string, portfolioContext *domain.PortfolioContext) float64 {
	geos := utils.ParseCSV(geography)
	if len(geos) == 0 {
		return 0.5
	}

	// Find highest score across all geographies
	maxScore := 0.1

	for _, geo := range geos {
		// Look up weight for the geography directly (0 to 1, where higher = prioritize)
		geoWeight := 0.0
		if portfolioContext.GeographyWeights != nil {
			geoWeight = portfolioContext.GeographyWeights[geo]
		}

		// Convert weight to score: 0.1 + (weight * 0.8)
		// weight=1 (prioritize) → score=0.9
		// weight=0.5 (neutral) → score=0.5
		// weight=0 (avoid) → score=0.1
		geoGapScore := 0.1 + (geoWeight * 0.8)
		if geoGapScore > maxScore {
			maxScore = geoGapScore
		}
	}

	return math.Max(0.1, math.Min(0.9, maxScore))
}

// calculateIndustryGapScore calculates industry gap score (30% weight)
// Higher weight = underweight sector = higher score
// For securities with multiple industries, returns the average score.
func calculateIndustryGapScore(industry *string, portfolioContext *domain.PortfolioContext) float64 {
	if industry == nil {
		return 0.5
	}

	industries := utils.ParseCSV(*industry)
	if len(industries) == 0 {
		return 0.5
	}

	indScores := make([]float64, 0, len(industries))
	for _, ind := range industries {
		// Look up weight for the industry directly (0 to 1, where higher = prioritize)
		indWeight := 0.0
		if portfolioContext.IndustryWeights != nil {
			indWeight = portfolioContext.IndustryWeights[ind]
		}

		// Convert weight to score: 0.1 + (weight * 0.8)
		// weight=1 (prioritize) → score=0.9
		// weight=0.5 (neutral) → score=0.5
		// weight=0 (avoid) → score=0.1
		indScore := 0.1 + (indWeight * 0.8)
		indScores = append(indScores, math.Max(0.1, math.Min(0.9, indScore)))
	}

	// Average across all industries
	sum := 0.0
	for _, score := range indScores {
		sum += score
	}
	return sum / float64(len(indScores))
}

// calculateAveragingDownScore calculates averaging down score (30% weight)
// Rewards buying more of quality positions that have dipped
func calculateAveragingDownScore(
	symbol string,
	qualityScore float64,
	opportunityScore float64,
	portfolioContext *domain.PortfolioContext,
) float64 {
	// Check if we own this position
	positionValue := 0.0
	if portfolioContext.Positions != nil {
		positionValue = portfolioContext.Positions[symbol]
	}

	// If we don't own it, return neutral
	if positionValue <= 0 {
		return 0.5
	}

	// Calculate averaging down potential
	avgDownPotential := qualityScore * opportunityScore

	// Base score based on potential
	averagingDownScore := 0.3
	if avgDownPotential >= 0.5 {
		averagingDownScore = 0.7 + (avgDownPotential-0.5)*0.6
	} else if avgDownPotential >= 0.3 {
		averagingDownScore = 0.5 + (avgDownPotential-0.3)*1.0
	}

	// Apply cost basis bonus
	averagingDownScore = applyCostBasisBonus(symbol, averagingDownScore, portfolioContext)

	// Apply concentration penalty
	averagingDownScore = applyConcentrationPenalty(positionValue, averagingDownScore, portfolioContext)

	return averagingDownScore
}

// applyCostBasisBonus applies bonus if current price is below average purchase price
// Rewards buying the dip on positions we're already in
func applyCostBasisBonus(symbol string, score float64, portfolioContext *domain.PortfolioContext) float64 {
	if portfolioContext.PositionAvgPrices == nil || portfolioContext.CurrentPrices == nil {
		return score
	}

	avgPrice, hasAvg := portfolioContext.PositionAvgPrices[symbol]
	currentPrice, hasCurrent := portfolioContext.CurrentPrices[symbol]

	if !hasAvg || !hasCurrent || avgPrice <= 0 {
		return score
	}

	// Calculate price vs average
	priceVsAvg := (currentPrice - avgPrice) / avgPrice

	// Only apply bonus if we're below average (loss)
	if priceVsAvg >= 0 {
		return score
	}

	// loss_pct is absolute value
	lossPct := math.Abs(priceVsAvg)

	// Only apply bonus up to COST_BASIS_BOOST_THRESHOLD (default 0.15 = 15%)
	if lossPct <= scoring.CostBasisBoostThreshold {
		costBasisBoost := math.Min(scoring.MaxCostBasisBoost, lossPct*2)
		return math.Min(1.0, score+costBasisBoost)
	}

	return score
}

// applyConcentrationPenalty penalizes over-concentration in single positions
// Prevents position from becoming too large relative to portfolio
func applyConcentrationPenalty(positionValue float64, score float64, portfolioContext *domain.PortfolioContext) float64 {
	totalValue := portfolioContext.TotalValue
	if totalValue <= 0 {
		return score
	}

	positionPct := positionValue / totalValue

	// Apply penalties for concentration
	if positionPct > scoring.ConcentrationHigh {
		// High concentration (>25%): 70% of original score
		return score * 0.7
	} else if positionPct > scoring.ConcentrationMed {
		// Medium concentration (>15%): 90% of original score
		return score * 0.9
	}

	return score
}

// calculateDiversificationScore calculates diversification score (40% weight)
// Measures how close portfolio is to target geo/industry allocations
func calculateDiversificationScore(portfolioContext *domain.PortfolioContext, totalValue float64) float64 {
	var geographyDeviations []float64

	if portfolioContext.SecurityGeographies != nil {
		// Aggregate position values by geography (direct, no groups)
		geographyValues := make(map[string]float64)
		for symbol, value := range portfolioContext.Positions {
			geography, hasGeography := portfolioContext.SecurityGeographies[symbol]
			if !hasGeography {
				geography = "OTHER"
			}

			// Parse comma-separated geographies and distribute value equally
			geos := utils.ParseCSV(geography)
			if len(geos) == 0 {
				geos = []string{"OTHER"}
			}
			valuePerGeo := value / float64(len(geos))
			for _, geo := range geos {
				geographyValues[geo] += valuePerGeo
			}
		}

		// Compare geography allocations to geography targets
		for geography, weight := range portfolioContext.GeographyWeights {
			targetPct := weight // Targets are already percentages (0-1)
			currentPct := 0.0
			if totalValue > 0 {
				currentPct = geographyValues[geography] / totalValue
			}
			deviation := math.Abs(currentPct - targetPct)
			geographyDeviations = append(geographyDeviations, deviation)
		}
	}

	avgGeographyDeviation := 0.2
	if len(geographyDeviations) > 0 {
		sum := 0.0
		for _, dev := range geographyDeviations {
			sum += dev
		}
		avgGeographyDeviation = sum / float64(len(geographyDeviations))
	}

	return math.Max(0, 100*(1-avgGeographyDeviation/0.3))
}

// calculateDividendScore calculates dividend score (30% weight)
// Weighted average dividend yield across positions
func calculateDividendScore(portfolioContext *domain.PortfolioContext, totalValue float64) float64 {
	if portfolioContext.SecurityDividends == nil {
		return 50.0
	}

	weightedDividend := 0.0
	for symbol, value := range portfolioContext.Positions {
		divYield, hasDiv := portfolioContext.SecurityDividends[symbol]
		if !hasDiv {
			divYield = 0
		}
		weightedDividend += divYield * (value / totalValue)
	}

	return math.Min(100, 30+weightedDividend*1000)
}

// calculateQualityScore calculates quality score (30% weight)
// Weighted average security quality scores
func calculateQualityScore(portfolioContext *domain.PortfolioContext, totalValue float64) float64 {
	if portfolioContext.SecurityScores == nil {
		return 50.0
	}

	weightedQuality := 0.0
	for symbol, value := range portfolioContext.Positions {
		quality, hasQuality := portfolioContext.SecurityScores[symbol]
		if !hasQuality {
			quality = 0.5
		}
		weightedQuality += quality * (value / totalValue)
	}

	return weightedQuality * 100
}

// CalculatePortfolioScore calculates overall portfolio health score
//
// Components:
// - Diversification (40%): How close to target geo/industry allocations
// - Dividend (30%): Weighted average dividend yield across positions
// - Quality (30%): Weighted average security quality scores
//
// Args:
//
//	portfolioContext: Portfolio context with positions and weights
//
// Returns:
//
//	PortfolioScore with component scores and total (0-100 scale)
func (ds *DiversificationScorer) CalculatePortfolioScore(portfolioContext *domain.PortfolioContext) domain.PortfolioScore {
	totalValue := portfolioContext.TotalValue
	if totalValue <= 0 {
		return domain.PortfolioScore{
			DiversificationScore: 50.0,
			DividendScore:        50.0,
			QualityScore:         50.0,
			Total:                50.0,
		}
	}

	diversificationScore := calculateDiversificationScore(portfolioContext, totalValue)
	dividendScore := calculateDividendScore(portfolioContext, totalValue)
	qualityScore := calculateQualityScore(portfolioContext, totalValue)

	total := diversificationScore*0.40 + dividendScore*0.30 + qualityScore*0.30

	return domain.PortfolioScore{
		DiversificationScore: round1(diversificationScore),
		DividendScore:        round1(dividendScore),
		QualityScore:         round1(qualityScore),
		Total:                round1(total),
	}
}

// CalculatePostTransactionScore calculates portfolio score AFTER a proposed transaction
//
// Args:
//
//	symbol: Security symbol to buy
//	geography: Security geography (e.g., "US", "EU", "North America")
//	industry: Security industry (can be nil)
//	proposedValue: Transaction value (min_lot * price)
//	stockQuality: Quality score of the security (0-1)
//	stockDividend: Dividend yield of the security (0-1)
//	portfolioContext: Current portfolio context
//
// Returns:
//
//	Tuple of (new_portfolio_score, score_change)
func (ds *DiversificationScorer) CalculatePostTransactionScore(
	symbol string,
	geography string,
	industry *string,
	proposedValue float64,
	stockQuality float64,
	stockDividend float64,
	portfolioContext *domain.PortfolioContext,
) (domain.PortfolioScore, float64) {
	// Calculate current portfolio score
	currentScore := ds.CalculatePortfolioScore(portfolioContext)

	// Create modified context with proposed transaction
	newPositions := make(map[string]float64)
	for k, v := range portfolioContext.Positions {
		newPositions[k] = v
	}
	newPositions[symbol] += proposedValue

	newGeographies := make(map[string]string)
	if portfolioContext.SecurityGeographies != nil {
		for k, v := range portfolioContext.SecurityGeographies {
			newGeographies[k] = v
		}
	}
	newGeographies[symbol] = geography

	newIndustries := make(map[string]string)
	if portfolioContext.SecurityIndustries != nil {
		for k, v := range portfolioContext.SecurityIndustries {
			newIndustries[k] = v
		}
	}
	if industry != nil {
		newIndustries[symbol] = *industry
	}

	newScores := make(map[string]float64)
	if portfolioContext.SecurityScores != nil {
		for k, v := range portfolioContext.SecurityScores {
			newScores[k] = v
		}
	}
	newScores[symbol] = stockQuality

	newDividends := make(map[string]float64)
	if portfolioContext.SecurityDividends != nil {
		for k, v := range portfolioContext.SecurityDividends {
			newDividends[k] = v
		}
	}
	newDividends[symbol] = stockDividend

	newContext := &domain.PortfolioContext{
		GeographyWeights:    portfolioContext.GeographyWeights,
		IndustryWeights:     portfolioContext.IndustryWeights,
		Positions:           newPositions,
		TotalValue:          portfolioContext.TotalValue + proposedValue,
		SecurityGeographies: newGeographies,
		SecurityIndustries:  newIndustries,
		SecurityScores:      newScores,
		SecurityDividends:   newDividends,
		PositionAvgPrices:   portfolioContext.PositionAvgPrices,
		CurrentPrices:       portfolioContext.CurrentPrices,
	}

	// Calculate new portfolio score
	newScore := ds.CalculatePortfolioScore(newContext)
	scoreChange := newScore.Total - currentScore.Total

	return newScore, scoreChange
}
