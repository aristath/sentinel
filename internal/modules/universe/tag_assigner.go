package universe

import (
	"math"

	"github.com/aristath/sentinel/internal/modules/quantum"
	"github.com/rs/zerolog"
)

// QualityGateThresholdsProvider provides access to quality gate thresholds
type QualityGateThresholdsProvider interface {
	GetFundamentals() float64
	GetLongTerm() float64
}

// AdaptiveQualityGatesProvider interface for getting adaptive quality gate thresholds
// The returned value must implement QualityGateThresholdsProvider interface
type AdaptiveQualityGatesProvider interface {
	CalculateAdaptiveQualityGates(regimeScore float64) QualityGateThresholdsProvider
}

// RegimeScoreProvider provides access to current regime score
type RegimeScoreProvider interface {
	GetCurrentRegimeScore() (float64, error)
}

// TagAssigner assigns tags to securities based on analysis
type TagAssigner struct {
	log                 zerolog.Logger
	adaptiveService     AdaptiveQualityGatesProvider          // Optional: adaptive market service
	regimeScoreProvider RegimeScoreProvider                   // Optional: regime score provider
	quantumCalculator   *quantum.QuantumProbabilityCalculator // Quantum probability calculator
}

// NewTagAssigner creates a new tag assigner
func NewTagAssigner(log zerolog.Logger) *TagAssigner {
	return &TagAssigner{
		log:               log.With().Str("service", "tag_assigner").Logger(),
		quantumCalculator: quantum.NewQuantumProbabilityCalculator(),
	}
}

// SetAdaptiveService sets the adaptive market service for dynamic quality gates
func (ta *TagAssigner) SetAdaptiveService(service AdaptiveQualityGatesProvider) {
	ta.adaptiveService = service
}

// SetRegimeScoreProvider sets the regime score provider for getting current regime
func (ta *TagAssigner) SetRegimeScoreProvider(provider RegimeScoreProvider) {
	ta.regimeScoreProvider = provider
}

// AssignTagsInput contains all data needed to assign tags to a security
type AssignTagsInput struct {
	Symbol                   string
	Security                 Security
	Score                    *SecurityScore
	GroupScores              map[string]float64
	SubScores                map[string]map[string]float64
	Volatility               *float64
	DailyPrices              []float64
	PERatio                  *float64
	MarketAvgPE              float64
	DividendYield            *float64
	FiveYearAvgDivYield      *float64
	CurrentPrice             *float64
	Price52wHigh             *float64
	Price52wLow              *float64
	EMA200                   *float64
	RSI                      *float64
	BollingerPosition        *float64
	MaxDrawdown              *float64
	PositionWeight           *float64
	TargetWeight             *float64
	AnnualizedReturn         *float64
	DaysHeld                 *int
	HistoricalVolatility     *float64
	TargetReturn             float64 // Target annual return (default: 0.11 = 11%)
	TargetReturnThresholdPct float64 // Threshold percentage (default: 0.80 = 80%)
}

// AssignTagsForSecurity analyzes a security and returns appropriate tag IDs
func (ta *TagAssigner) AssignTagsForSecurity(input AssignTagsInput) ([]string, error) {
	var tags []string

	// Extract scores for easier access
	opportunityScore := getScore(input.GroupScores, "opportunity")
	fundamentalsScore := getScore(input.GroupScores, "fundamentals")
	longTermScore := getScore(input.GroupScores, "long_term")
	dividendScore := getScore(input.GroupScores, "dividends")
	totalScore := 0.0
	if input.Score != nil {
		totalScore = input.Score.TotalScore
	}

	// Extract sub-scores
	consistencyScore := getSubScore(input.SubScores, "fundamentals", "consistency")
	cagrRaw := getSubScore(input.SubScores, "long_term", "cagr_raw") // Raw CAGR (e.g., 0.15 = 15%)
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

	ema200 := 0.0
	if input.EMA200 != nil && input.CurrentPrice != nil {
		ema200 = *input.EMA200
	}

	distanceFromEMA := 0.0
	if input.CurrentPrice != nil && ema200 > 0 {
		distanceFromEMA = (*input.CurrentPrice - ema200) / ema200
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
	if opportunityScore > 0.65 && (below52wHighPct > 15.0 || peVsMarket < -0.20) {
		tags = append(tags, "value-opportunity")
	}

	// Deep value: 25%+ discount AND cheap PE, OR 30%+ discount alone
	if (below52wHighPct > 25.0 && peVsMarket < -0.20) || below52wHighPct > 30.0 {
		tags = append(tags, "deep-value")
	}

	if below52wHighPct > 10.0 {
		tags = append(tags, "below-52w-high")
	}

	if peVsMarket < -0.20 {
		tags = append(tags, "undervalued-pe")
	}

	// Quality Opportunities
	if fundamentalsScore > 0.7 && longTermScore > 0.7 {
		tags = append(tags, "high-quality")
	}

	if fundamentalsScore > 0.75 && volatility < 0.25 && consistencyScore > 0.75 {
		tags = append(tags, "stable")
	}

	// Consistent grower: requires both consistency and meaningful growth
	// 9% CAGR threshold ensures meaningful growth for a retirement fund targeting 11%
	if consistencyScore > 0.75 && cagrRaw > 0.09 {
		tags = append(tags, "consistent-grower")
	}

	if fundamentalsScore > 0.75 {
		tags = append(tags, "strong-fundamentals")
	}

	// Technical Opportunities
	// Only tag as oversold if RSI is actually available (not nil) and below 30
	// Defaulting to 0.0 when RSI is missing would incorrectly tag all securities
	if input.RSI != nil && *input.RSI < 30 {
		tags = append(tags, "oversold")
	}

	// Removed: below-ema and bollinger-oversold tags (unused)

	// Dividend Opportunities
	if dividendYield > 0.04 {
		tags = append(tags, "high-dividend")
	}

	if dividendScore > 0.55 && dividendYield > 0.025 {
		tags = append(tags, "dividend-opportunity")
	}

	if dividendConsistencyScore > 0.7 && input.FiveYearAvgDivYield != nil && dividendYield > 0 {
		if *input.FiveYearAvgDivYield > dividendYield {
			tags = append(tags, "dividend-grower")
		}
	}

	// Momentum Opportunities
	// Removed: positive-momentum tag (unused)

	if momentumScore < 0 && fundamentalsScore > 0.65 && below52wHighPct > 12.0 {
		tags = append(tags, "recovery-candidate")
	}

	// Score-Based Opportunities
	if totalScore > 0.7 {
		tags = append(tags, "high-score")
	}

	// Removed: good-opportunity tag (unused)

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

	// Removed: near-52w-high and above-ema tags (unused)

	// Only tag as overbought if RSI is actually available (not nil) and above 70
	// Defaulting to 0.0 when RSI is missing would incorrectly tag securities
	if input.RSI != nil && *input.RSI > 70 {
		tags = append(tags, "overbought")
	}

	// Instability Warnings
	// Note: Instability score from sell scorer not available in current input
	// Would need to be added if available
	if annualizedReturn > 0.50 && volatilitySpike {
		tags = append(tags, "unsustainable-gains")
	}

	if math.Abs(distanceFromEMA) > 0.30 {
		tags = append(tags, "valuation-stretch")
	}

	// Underperformance Warnings
	if annualizedReturn < 0.0 && daysHeld > 180 {
		tags = append(tags, "underperforming")
	}

	if annualizedReturn < 0.05 && daysHeld > 365 {
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

		// Only tag significant deviations (keep needs-rebalance, removed unused weight tags)
		if deviation > 0.03 || deviation < -0.03 {
			tags = append(tags, "needs-rebalance")
		}
	}

	// === CHARACTERISTIC TAGS ===

	// Risk Profile
	if volatility < 0.15 && fundamentalsScore > 0.7 && maxDrawdown < 20.0 {
		tags = append(tags, "low-risk")
	}

	if volatility >= 0.15 && volatility <= 0.30 && fundamentalsScore > 0.55 {
		tags = append(tags, "medium-risk")
	}

	if volatility > 0.30 || fundamentalsScore < 0.5 {
		tags = append(tags, "high-risk")
	}

	// Growth Profile
	if cagrRaw > 0.15 && fundamentalsScore > 0.7 {
		tags = append(tags, "growth")
	}

	if peVsMarket < 0 && opportunityScore > 0.7 {
		tags = append(tags, "value")
	}

	if dividendYield > 0.04 && dividendScore > 0.65 {
		tags = append(tags, "dividend-focused")
	}

	// === MULTI-PATH QUALITY GATE TAGS ===

	// Get adaptive quality gate thresholds (for Path 1 only)
	fundamentalsThreshold := 0.55 // Relaxed from 0.6
	longTermThreshold := 0.45     // Relaxed from 0.5

	if ta.adaptiveService != nil {
		// Get current regime score if provider is available, otherwise use neutral (0.0)
		regimeScore := 0.0
		if ta.regimeScoreProvider != nil {
			currentScore, err := ta.regimeScoreProvider.GetCurrentRegimeScore()
			if err == nil {
				regimeScore = currentScore
			}
		}

		// Calculate adaptive thresholds based on current regime score
		thresholds := ta.adaptiveService.CalculateAdaptiveQualityGates(regimeScore)
		if thresholds != nil {
			fundamentalsThreshold = thresholds.GetFundamentals()
			longTermThreshold = thresholds.GetLongTerm()
		}
	}

	// Extract additional scores for multi-path evaluation
	sharpeRaw := getSubScore(input.SubScores, "long_term", "sharpe_raw")
	sortinoRatioRaw := getSubScore(input.SubScores, "long_term", "sortino_raw")

	// Evaluate all 7 paths - ANY path passes
	passes := false
	passedPath := ""

	// Path 1: Balanced (adaptive)
	if evaluatePath1Balanced(fundamentalsScore, longTermScore, fundamentalsThreshold, longTermThreshold) {
		passes = true
		passedPath = "balanced"
	}

	// Path 2: Exceptional Excellence
	if !passes && evaluatePath2ExceptionalExcellence(fundamentalsScore, longTermScore) {
		passes = true
		passedPath = "exceptional_excellence"
	}

	// Path 3: Quality Value Play
	if !passes && evaluatePath3QualityValuePlay(fundamentalsScore, opportunityScore, longTermScore) {
		passes = true
		passedPath = "quality_value"
	}

	// Path 4: Dividend Income Play
	if !passes && evaluatePath4DividendIncomePlay(fundamentalsScore, dividendScore, dividendYield) {
		passes = true
		passedPath = "dividend_income"
	}

	// Path 5: Risk-Adjusted Excellence
	if !passes && evaluatePath5RiskAdjustedExcellence(longTermScore, sharpeRaw, sortinoRatioRaw, volatility) {
		passes = true
		passedPath = "risk_adjusted"
	}

	// Path 6: Composite Minimum
	if !passes && evaluatePath6CompositeMinimum(fundamentalsScore, longTermScore) {
		passes = true
		passedPath = "composite"
	}

	// Path 7: Growth Opportunity
	if !passes && evaluatePath7GrowthOpportunity(cagrRaw, fundamentalsScore, volatility) {
		passes = true
		passedPath = "growth"
	}

	// Assign quality gate tag (only when failing - cleaner approach)
	// Architectural change: Tag what's wrong, not what's right
	if !passes {
		tags = append(tags, "quality-gate-fail")
		ta.log.Debug().
			Str("symbol", input.Symbol).
			Float64("fundamentals", fundamentalsScore).
			Float64("long_term", longTermScore).
			Msg("Quality gate failed - no paths satisfied")
	} else {
		ta.log.Debug().
			Str("symbol", input.Symbol).
			Str("path", passedPath).
			Float64("fundamentals", fundamentalsScore).
			Float64("long_term", longTermScore).
			Msg("Quality gate passed")
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

	sharpeRatio := getSubScore(input.SubScores, "long_term", "sharpe_raw")
	// sortinoRatioRaw already extracted above for multi-path quality gates

	// Bubble risk: High CAGR with poor risk metrics
	// Only use raw values for accurate risk assessment - no fallback approximations
	isBubble := false
	if cagrRaw > 0.15 { // 15% for 11% target (1.36x target, relaxed from 1.5x)
		// Check risk metrics - require raw Sortino for accurate assessment
		// If sortino_raw is not available (0), we can't accurately assess bubble risk
		hasPoorRisk := sharpeRatio < 0.5 || volatility > 0.40 || fundamentalsScore < 0.55
		if sortinoRatioRaw > 0 {
			hasPoorRisk = hasPoorRisk || sortinoRatioRaw < 0.5
		}
		// Only flag as bubble if we have sufficient risk data
		if hasPoorRisk && (sortinoRatioRaw > 0 || sharpeRatio > 0) {
			isBubble = true
		}

		if isBubble {
			tags = append(tags, "bubble-risk")
		} else {
			// High CAGR (15%+) with good risk metrics = quality-high-cagr
			// Require both Sharpe and Sortino for quality-high-cagr tag
			if sharpeRatio >= 0.5 && sortinoRatioRaw >= 0.5 && volatility <= 0.40 && fundamentalsScore >= 0.55 {
				tags = append(tags, "quality-high-cagr")
			}
		}
	}

	// === QUANTUM BUBBLE DETECTION (Ensemble with Classical) ===

	// Get regime score for adaptive weighting
	regimeScore := 0.0
	if ta.regimeScoreProvider != nil {
		currentScore, err := ta.regimeScoreProvider.GetCurrentRegimeScore()
		if err == nil {
			regimeScore = currentScore
		}
	}

	// Calculate quantum bubble probability
	quantumBubbleProb := ta.quantumCalculator.CalculateBubbleProbability(
		cagrRaw,
		sharpeRatio,
		sortinoRatioRaw,
		volatility,
		fundamentalsScore,
		regimeScore,
		nil, // kurtosis not available in tag assigner
	)

	// Ensemble decision logic
	classicalBubble := isBubble
	if classicalBubble {
		// Classical detected bubble - add ensemble tag
		tags = append(tags, "ensemble-bubble-risk")
	} else if quantumBubbleProb > 0.7 {
		// Quantum detected high probability bubble
		tags = append(tags, "quantum-bubble-risk")
		tags = append(tags, "ensemble-bubble-risk")
	} else if quantumBubbleProb > 0.5 {
		// Quantum early warning
		tags = append(tags, "quantum-bubble-warning")
	}

	// === NEW: VALUE TRAP TAGS ===

	// Value trap: Cheap but declining
	isValueTrap := false
	if peVsMarket < -0.20 {
		if fundamentalsScore < 0.55 || longTermScore < 0.45 || momentumScore < -0.05 || volatility > 0.35 {
			isValueTrap = true
		}

		if isValueTrap {
			tags = append(tags, "value-trap")
		}
	}

	// === QUANTUM VALUE TRAP DETECTION (Ensemble with Classical) ===

	// Calculate quantum value trap probability (only if cheap)
	if peVsMarket < -0.20 {
		quantumTrapProb := ta.quantumCalculator.CalculateValueTrapProbability(
			peVsMarket,
			fundamentalsScore,
			longTermScore,
			momentumScore,
			volatility,
			regimeScore,
		)

		// Ensemble decision logic
		classicalTrap := isValueTrap
		if classicalTrap {
			// Classical detected trap - add ensemble tag
			tags = append(tags, "ensemble-value-trap")
		} else if quantumTrapProb > 0.7 {
			// Quantum detected high probability trap
			tags = append(tags, "quantum-value-trap")
			tags = append(tags, "ensemble-value-trap")
		} else if quantumTrapProb > 0.5 {
			// Quantum early warning
			tags = append(tags, "quantum-value-warning")
		}
	}

	// === NEW: TOTAL RETURN TAGS ===

	// Calculate total return using raw CAGR and dividend yield (both in decimal format: 0.15 = 15%)
	totalReturn := cagrRaw + dividendYield

	if totalReturn >= 0.18 {
		tags = append(tags, "excellent-total-return")
	} else if totalReturn >= 0.15 {
		tags = append(tags, "high-total-return")
	} else if totalReturn >= 0.12 {
		tags = append(tags, "moderate-total-return")
	}

	// Dividend total return (5% growth + 8% dividend example)
	if dividendYield >= 0.08 && cagrRaw >= 0.05 {
		tags = append(tags, "dividend-total-return")
	}

	// === NEW: REGIME-SPECIFIC TAGS ===

	// Bear market safe
	if volatility < 0.20 && fundamentalsScore > 0.70 && maxDrawdown < 20.0 {
		tags = append(tags, "regime-bear-safe")
	}

	// Bull market growth
	if cagrRaw > 0.12 && fundamentalsScore > 0.7 && momentumScore > 0 {
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

	// === NEW: RETURN-BASED FILTERING TAGS ===
	// These tags help calculators filter out low-return securities without duplicating logic

	// Get target return (default: 11% if not provided)
	targetReturn := input.TargetReturn
	if targetReturn == 0 {
		targetReturn = 0.11 // Default 11%
	}
	thresholdPct := input.TargetReturnThresholdPct
	if thresholdPct == 0 {
		thresholdPct = 0.70 // Default 70% (relaxed from 80% for 15-20 year horizon)
	}

	// Calculate absolute minimum CAGR threshold
	absoluteMinCAGR := math.Max(0.06, targetReturn*0.50)

	// Get raw CAGR value (from sub-scores "cagr_raw", in decimal: e.g., 0.15 = 15%)
	// Note: cagr_raw is already extracted at the top of the function
	// If not available, use the value we already extracted

	// If cagr_raw not available, try to get from scored CAGR (but this is less accurate)
	// The scored CAGR is 0-1, so we can't reliably convert it back to raw CAGR
	// For now, only tag if we have raw CAGR data
	if cagrRaw > 0 {
		// Tag securities below absolute minimum (hard filter)
		if cagrRaw < absoluteMinCAGR {
			tags = append(tags, "below-minimum-return")
		}

		// Removed: below-target-return tag (unused - below-minimum-return is the hard filter)

		// Tag securities meeting or exceeding target
		if cagrRaw >= targetReturn {
			tags = append(tags, "meets-target-return")
		}
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

// isPoorRiskAdjusted checks if a security has poor risk-adjusted returns
// Only uses raw risk metrics for accurate assessment - no fallback approximations
func isPoorRiskAdjusted(sharpeRatio, sortinoRatioRaw float64) bool {
	// If we have Sharpe ratio, check it
	if sharpeRatio > 0 && sharpeRatio < 0.5 {
		return true
	}
	// If we have Sortino ratio, check it
	if sortinoRatioRaw > 0 && sortinoRatioRaw < 0.5 {
		return true
	}
	// If we have neither, can't assess - don't tag as poor
	return false
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

// ============================================================================
// Multi-Path Quality Gate Evaluation Functions
// ============================================================================

// evaluatePath1Balanced checks balanced path with adaptive thresholds.
// Path 1: Balanced (relaxed, adaptive)
// Default: fundamentals >= 0.55 AND longTerm >= 0.45
// Thresholds can be adjusted by AdaptiveService based on market regime.
func evaluatePath1Balanced(fundamentals, longTerm, fundamentalsThreshold, longTermThreshold float64) bool {
	return fundamentals >= fundamentalsThreshold && longTerm >= longTermThreshold
}

// evaluatePath2ExceptionalExcellence checks for exceptional performance in either dimension.
// Path 2: Exceptional Excellence
// Condition: fundamentals >= 0.75 OR longTerm >= 0.75
// Allows one-dimensional excellence to compensate for weakness in other dimension.
func evaluatePath2ExceptionalExcellence(fundamentals, longTerm float64) bool {
	return fundamentals >= 0.75 || longTerm >= 0.75
}

// evaluatePath3QualityValuePlay checks quality value play path.
// Path 3: Quality Value Play
// Condition: fundamentals >= 0.60 AND opportunity >= 0.65 AND longTerm >= 0.30
// Identifies high-quality undervalued securities with temporary weakness.
func evaluatePath3QualityValuePlay(fundamentals, opportunity, longTerm float64) bool {
	return fundamentals >= 0.60 && opportunity >= 0.65 && longTerm >= 0.30
}

// evaluatePath4DividendIncomePlay checks dividend income play path.
// Path 4: Dividend Income Play
// Condition: fundamentals >= 0.55 AND dividendScore >= 0.65 AND dividendYield >= 0.035
// Identifies solid dividend payers for retirement income strategy.
func evaluatePath4DividendIncomePlay(fundamentals, dividendScore, dividendYield float64) bool {
	return fundamentals >= 0.55 && dividendScore >= 0.65 && dividendYield >= 0.035
}

// evaluatePath5RiskAdjustedExcellence checks risk-adjusted excellence path.
// Path 5: Risk-Adjusted Excellence
// Condition: longTerm >= 0.55 AND (sharpe >= 0.9 OR sortino >= 0.9) AND volatility <= 0.35
// Identifies securities with excellent risk-adjusted returns.
func evaluatePath5RiskAdjustedExcellence(longTerm, sharpe, sortino, volatility float64) bool {
	return longTerm >= 0.55 && (sharpe >= 0.9 || sortino >= 0.9) && volatility <= 0.35
}

// evaluatePath6CompositeMinimum checks composite minimum path.
// Path 6: Composite Minimum
// Condition: (0.6 * fundamentals + 0.4 * longTerm) >= 0.52 AND fundamentals >= 0.45
// Allows trade-offs between dimensions with minimum fundamentals floor.
func evaluatePath6CompositeMinimum(fundamentals, longTerm float64) bool {
	compositeScore := 0.6*fundamentals + 0.4*longTerm
	return compositeScore >= 0.52 && fundamentals >= 0.45
}

// evaluatePath7GrowthOpportunity checks growth opportunity path.
// Path 7: Growth Opportunity
// Condition: cagrRaw >= 0.13 AND fundamentals >= 0.50 AND volatility <= 0.40
// Identifies growth securities meeting 15-20 year retirement fund targets.
func evaluatePath7GrowthOpportunity(cagrRaw, fundamentals, volatility float64) bool {
	return cagrRaw >= 0.13 && fundamentals >= 0.50 && volatility <= 0.40
}
