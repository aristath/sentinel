package universe

import (
	"math"

	"github.com/rs/zerolog"
)

// TagAssigner assigns tags to securities based on analysis
type TagAssigner struct {
	log zerolog.Logger
}

// NewTagAssigner creates a new tag assigner
func NewTagAssigner(log zerolog.Logger) *TagAssigner {
	return &TagAssigner{
		log: log.With().Str("service", "tag_assigner").Logger(),
	}
}

// AssignTagsInput contains all data needed to assign tags to a security
type AssignTagsInput struct {
	Symbol               string
	Security             Security
	Score                *SecurityScore
	GroupScores          map[string]float64
	SubScores            map[string]map[string]float64
	Volatility           *float64
	DailyPrices          []float64
	PERatio              *float64
	MarketAvgPE          float64
	DividendYield        *float64
	FiveYearAvgDivYield  *float64
	CurrentPrice         *float64
	Price52wHigh         *float64
	Price52wLow          *float64
	EMA200               *float64
	RSI                  *float64
	BollingerPosition    *float64
	MaxDrawdown          *float64
	PositionWeight       *float64
	TargetWeight         *float64
	AnnualizedReturn     *float64
	DaysHeld             *int
	HistoricalVolatility *float64
}

// AssignTagsForSecurity analyzes a security and returns appropriate tag IDs
func (ta *TagAssigner) AssignTagsForSecurity(input AssignTagsInput) ([]string, error) {
	var tags []string

	// Extract scores for easier access
	opportunityScore := getScore(input.GroupScores, "opportunity")
	fundamentalsScore := getScore(input.GroupScores, "fundamentals")
	longTermScore := getScore(input.GroupScores, "long_term")
	technicalScore := getScore(input.GroupScores, "technicals")
	shortTermScore := getScore(input.GroupScores, "short_term")
	dividendScore := getScore(input.GroupScores, "dividends")
	totalScore := 0.0
	if input.Score != nil {
		totalScore = input.Score.TotalScore
	}

	// Extract sub-scores
	consistencyScore := getSubScore(input.SubScores, "fundamentals", "consistency")
	cagrScore := getSubScore(input.SubScores, "long_term", "cagr")
	momentumScore := getSubScore(input.SubScores, "short_term", "momentum")
	dividendConsistencyScore := getSubScore(input.SubScores, "dividends", "consistency")

	// Calculate derived metrics
	volatility := 0.0
	if input.Volatility != nil {
		volatility = *input.Volatility
	}

	below52wHighPct := calculateBelow52wHighPct(input.CurrentPrice, input.Price52wHigh)
	peRatio := 0.0
	if input.PERatio != nil {
		peRatio = *input.PERatio
	}
	peVsMarket := 0.0
	if input.MarketAvgPE > 0 && peRatio > 0 {
		peVsMarket = (peRatio - input.MarketAvgPE) / input.MarketAvgPE
	}

	dividendYield := 0.0
	if input.DividendYield != nil {
		dividendYield = *input.DividendYield
	}

	rsi := 0.0
	if input.RSI != nil {
		rsi = *input.RSI
	}

	ema200 := 0.0
	if input.EMA200 != nil && input.CurrentPrice != nil {
		ema200 = *input.EMA200
	}

	distanceFromEMA := 0.0
	if input.CurrentPrice != nil && ema200 > 0 {
		distanceFromEMA = (*input.CurrentPrice - ema200) / ema200
	}

	bollingerPosition := 0.0
	if input.BollingerPosition != nil {
		bollingerPosition = *input.BollingerPosition
	}

	maxDrawdown := 0.0
	if input.MaxDrawdown != nil {
		maxDrawdown = *input.MaxDrawdown
	}

	historicalVolatility := volatility
	if input.HistoricalVolatility != nil {
		historicalVolatility = *input.HistoricalVolatility
	}

	volatilitySpike := false
	if historicalVolatility > 0 {
		volatilitySpike = volatility > historicalVolatility*1.5
	}

	annualizedReturn := 0.0
	if input.AnnualizedReturn != nil {
		annualizedReturn = *input.AnnualizedReturn
	}

	daysHeld := 0
	if input.DaysHeld != nil {
		daysHeld = *input.DaysHeld
	}

	positionWeight := 0.0
	if input.PositionWeight != nil {
		positionWeight = *input.PositionWeight
	}

	targetWeight := 0.0
	if input.TargetWeight != nil {
		targetWeight = *input.TargetWeight
	}

	// === OPPORTUNITY TAGS ===

	// Value Opportunities
	if opportunityScore > 0.7 && (below52wHighPct > 20.0 || peVsMarket < -0.20) {
		tags = append(tags, "value-opportunity")
	}

	if below52wHighPct > 30.0 && peVsMarket < -0.20 {
		tags = append(tags, "deep-value")
	}

	if below52wHighPct > 10.0 {
		tags = append(tags, "below-52w-high")
	}

	if peVsMarket < -0.20 {
		tags = append(tags, "undervalued-pe")
	}

	// Quality Opportunities
	if fundamentalsScore > 0.8 && longTermScore > 0.75 {
		tags = append(tags, "high-quality")
	}

	if fundamentalsScore > 0.75 && volatility < 0.20 && consistencyScore > 0.8 {
		tags = append(tags, "stable")
	}

	if consistencyScore > 0.8 && cagrScore > 8.0 {
		tags = append(tags, "consistent-grower")
	}

	if fundamentalsScore > 0.8 {
		tags = append(tags, "strong-fundamentals")
	}

	// Technical Opportunities
	if rsi < 30 {
		tags = append(tags, "oversold")
	}

	if distanceFromEMA < -0.05 {
		tags = append(tags, "below-ema")
	}

	if bollingerPosition < 0.2 {
		tags = append(tags, "bollinger-oversold")
	}

	// Dividend Opportunities
	if dividendYield > 6.0 {
		tags = append(tags, "high-dividend")
	}

	if dividendScore > 0.7 && dividendYield > 3.0 {
		tags = append(tags, "dividend-opportunity")
	}

	if dividendConsistencyScore > 0.8 && input.FiveYearAvgDivYield != nil && dividendYield > 0 {
		if *input.FiveYearAvgDivYield > dividendYield {
			tags = append(tags, "dividend-grower")
		}
	}

	// Momentum Opportunities
	if shortTermScore > 0.7 && momentumScore > 0.05 && momentumScore < 0.15 {
		tags = append(tags, "positive-momentum")
	}

	if momentumScore < 0 && fundamentalsScore > 0.7 && below52wHighPct > 15.0 {
		tags = append(tags, "recovery-candidate")
	}

	// Score-Based Opportunities
	if totalScore > 0.75 {
		tags = append(tags, "high-score")
	}

	if totalScore > 0.7 && opportunityScore > 0.7 {
		tags = append(tags, "good-opportunity")
	}

	// === DANGER TAGS ===

	// Volatility Warnings
	if volatility > 0.30 {
		tags = append(tags, "volatile")
	}

	if volatilitySpike {
		tags = append(tags, "volatility-spike")
	}

	if volatility > 0.40 {
		tags = append(tags, "high-volatility")
	}

	// Overvaluation Warnings
	if peVsMarket > 0.20 && below52wHighPct < 5.0 {
		tags = append(tags, "overvalued")
	}

	if below52wHighPct < 5.0 && input.Price52wHigh != nil && input.CurrentPrice != nil {
		if *input.CurrentPrice > *input.Price52wHigh*0.95 {
			tags = append(tags, "near-52w-high")
		}
	}

	if distanceFromEMA > 0.10 {
		tags = append(tags, "above-ema")
	}

	if rsi > 70 {
		tags = append(tags, "overbought")
	}

	// Instability Warnings
	// Note: Instability score from sell scorer not available in current input
	// Would need to be added if available
	if annualizedReturn > 50.0 && volatilitySpike {
		tags = append(tags, "unsustainable-gains")
	}

	if math.Abs(distanceFromEMA) > 0.30 {
		tags = append(tags, "valuation-stretch")
	}

	// Underperformance Warnings
	if annualizedReturn < 0.0 && daysHeld > 180 {
		tags = append(tags, "underperforming")
	}

	if annualizedReturn < 5.0 && daysHeld > 365 {
		tags = append(tags, "stagnant")
	}

	if maxDrawdown > 30.0 {
		tags = append(tags, "high-drawdown")
	}

	// Portfolio Risk Warnings
	if positionWeight > targetWeight+0.02 || positionWeight > 0.10 {
		tags = append(tags, "overweight")
	}

	if positionWeight > 0.15 {
		tags = append(tags, "concentration-risk")
	}

	// === NEW: OPTIMIZER ALIGNMENT TAGS ===

	if targetWeight > 0 {
		deviation := positionWeight - targetWeight

		if math.Abs(deviation) <= 0.01 {
			tags = append(tags, "target-aligned")
		} else if deviation > 0.03 {
			tags = append(tags, "needs-rebalance")
			if deviation > 0.02 {
				// Keep existing overweight tag logic (already added above)
			}
		} else if deviation < -0.03 {
			tags = append(tags, "needs-rebalance")
			tags = append(tags, "underweight")
		} else if deviation > 0.01 {
			tags = append(tags, "slightly-overweight")
		} else if deviation < -0.01 {
			tags = append(tags, "slightly-underweight")
		}
	}

	// === CHARACTERISTIC TAGS ===

	// Risk Profile
	if volatility < 0.15 && fundamentalsScore > 0.7 && maxDrawdown < 20.0 {
		tags = append(tags, "low-risk")
	}

	if volatility >= 0.15 && volatility <= 0.30 && fundamentalsScore > 0.6 {
		tags = append(tags, "medium-risk")
	}

	if volatility > 0.30 || fundamentalsScore < 0.5 {
		tags = append(tags, "high-risk")
	}

	// Growth Profile
	if cagrScore > 15.0 && fundamentalsScore > 0.7 {
		tags = append(tags, "growth")
	}

	if peVsMarket < 0 && opportunityScore > 0.7 {
		tags = append(tags, "value")
	}

	if dividendYield > 4.0 && dividendScore > 0.7 {
		tags = append(tags, "dividend-focused")
	}

	// Time Horizon
	if longTermScore > 0.75 && consistencyScore > 0.8 {
		tags = append(tags, "long-term")
	}

	if technicalScore > 0.7 && opportunityScore > 0.7 && momentumScore > 0 {
		tags = append(tags, "short-term-opportunity")
	}

	// === NEW: QUALITY GATE TAGS ===

	// Quality gate pass/fail
	if fundamentalsScore >= 0.6 && longTermScore >= 0.5 {
		tags = append(tags, "quality-gate-pass")
	} else {
		tags = append(tags, "quality-gate-fail")
	}

	// Quality value (high quality + value opportunity)
	// Check if we already have both tags
	hasHighQuality := false
	hasValueOpportunity := false
	for _, t := range tags {
		if t == "high-quality" {
			hasHighQuality = true
		}
		if t == "value-opportunity" {
			hasValueOpportunity = true
		}
	}
	if hasHighQuality && hasValueOpportunity {
		tags = append(tags, "quality-value")
	}

	// === NEW: BUBBLE DETECTION TAGS ===

	cagrValue := getSubScore(input.SubScores, "long_term", "cagr")
	sharpeRatio := getSubScore(input.SubScores, "long_term", "sharpe_raw")
	// Note: Sortino ratio is not currently stored in sub-scores as "sortino_raw".
	// The LongTermScorer stores "sortino" (scored value 0-1) but not the raw ratio.
	// This means:
	// - high-sortino tag (>= 1.5) will not work correctly (scored values are 0-1)
	// - poor-risk-adjusted and bubble detection using sortino < 0.5 will work but use scored value
	// - When not available, sortinoRatio will be 0.0
	// Bubble detection will rely more on Sharpe ratio, which is acceptable as Sharpe alone is sufficient.
	// TODO: Store sortino_raw in LongTermScorer similar to sharpe_raw for accurate tag assignment.
	sortinoRatio := getSubScore(input.SubScores, "long_term", "sortino") // Scored value (0-1), not raw ratio

	// Bubble risk: High CAGR with poor risk metrics
	if cagrValue > 0.165 { // 16.5% for 11% target
		isBubble := false
		if sharpeRatio < 0.5 || sortinoRatio < 0.5 || volatility > 0.40 || fundamentalsScore < 0.6 {
			isBubble = true
		}

		if isBubble {
			tags = append(tags, "bubble-risk")
		} else {
			// Only tag as quality-high-cagr if CAGR > 15% (not just > 16.5%)
			if cagrValue > 0.15 {
				tags = append(tags, "quality-high-cagr")
			}
		}
	} else if cagrValue > 0.15 {
		// High CAGR (15-16.5%) with good risk metrics
		if sharpeRatio >= 0.5 && sortinoRatio >= 0.5 && volatility <= 0.40 && fundamentalsScore >= 0.6 {
			tags = append(tags, "quality-high-cagr")
		}
	}

	// Risk-adjusted tags
	if sharpeRatio >= 1.5 {
		tags = append(tags, "high-sharpe")
	}
	if sortinoRatio >= 1.5 {
		tags = append(tags, "high-sortino")
	}
	if sharpeRatio < 0.5 || sortinoRatio < 0.5 {
		tags = append(tags, "poor-risk-adjusted")
	}

	// === NEW: VALUE TRAP TAGS ===

	// Value trap: Cheap but declining
	if peVsMarket < -0.20 {
		isValueTrap := false
		if fundamentalsScore < 0.6 || longTermScore < 0.5 || momentumScore < -0.05 || volatility > 0.35 {
			isValueTrap = true
		}

		if isValueTrap {
			tags = append(tags, "value-trap")
		}
	}

	// === NEW: TOTAL RETURN TAGS ===

	// Note: dividendYield is in percentage (e.g., 0.10 = 10%), cagrValue is in decimal (e.g., 0.15 = 15%)
	// Both are already in the same format, so we can add them directly
	totalReturn := cagrScore + dividendYield

	if totalReturn >= 0.18 {
		tags = append(tags, "excellent-total-return")
	} else if totalReturn >= 0.15 {
		tags = append(tags, "high-total-return")
	} else if totalReturn >= 0.12 {
		tags = append(tags, "moderate-total-return")
	}

	// Dividend total return (5% growth + 10% dividend example)
	if dividendYield >= 0.08 && cagrScore >= 0.05 {
		tags = append(tags, "dividend-total-return")
	}

	// === NEW: REGIME-SPECIFIC TAGS ===

	// Bear market safe
	if volatility < 0.20 && fundamentalsScore > 0.75 && maxDrawdown < 20.0 {
		tags = append(tags, "regime-bear-safe")
	}

	// Bull market growth
	if cagrScore > 0.12 && fundamentalsScore > 0.7 && momentumScore > 0 {
		tags = append(tags, "regime-bull-growth")
	}

	// Sideways value
	// Check if value-opportunity tag was already assigned
	hasValueOpportunityForRegime := false
	for _, t := range tags {
		if t == "value-opportunity" {
			hasValueOpportunityForRegime = true
			break
		}
	}
	if hasValueOpportunityForRegime && fundamentalsScore > 0.75 {
		tags = append(tags, "regime-sideways-value")
	}

	// Regime volatile
	if volatility > 0.30 || volatilitySpike {
		tags = append(tags, "regime-volatile")
	}

	// Remove duplicates
	tags = removeDuplicates(tags)

	ta.log.Debug().
		Str("symbol", input.Symbol).
		Strs("tags", tags).
		Msg("Tags assigned to security")

	return tags, nil
}

// Helper functions

func getScore(scores map[string]float64, key string) float64 {
	if scores == nil {
		return 0.0
	}
	if score, ok := scores[key]; ok {
		return score
	}
	return 0.0
}

func getSubScore(subScores map[string]map[string]float64, group, key string) float64 {
	if subScores == nil {
		return 0.0
	}
	if groupScores, ok := subScores[group]; ok {
		if score, ok := groupScores[key]; ok {
			return score
		}
	}
	return 0.0
}

func calculateBelow52wHighPct(currentPrice, price52wHigh *float64) float64 {
	if currentPrice == nil || price52wHigh == nil || *price52wHigh == 0 {
		return 0.0
	}
	if *currentPrice >= *price52wHigh {
		return 0.0
	}
	return ((*price52wHigh - *currentPrice) / *price52wHigh) * 100.0
}

func removeDuplicates(tags []string) []string {
	seen := make(map[string]bool)
	result := []string{}
	for _, tag := range tags {
		if !seen[tag] {
			seen[tag] = true
			result = append(result, tag)
		}
	}
	return result
}
