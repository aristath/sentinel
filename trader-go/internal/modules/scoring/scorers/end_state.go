package scorers

import (
	"math"

	"github.com/aristath/arduino-trader/internal/modules/scoring"
)

// EndStateScorer provides scoring functions for holistic planning
// Faithful translation from Python: app/modules/scoring/domain/end_state.py
//
// This module provides scoring functions that evaluate the overall health
// of a portfolio after a sequence of trades, focusing on:
// - Total Return (CAGR + dividends combined)
// - Long-term Promise (consistency, financials, dividend stability)
// - Stability (low volatility, minimal drawdown)
//
// Used by the holistic planner to evaluate and compare action sequences.
type EndStateScorer struct{}

// EndStateWeights represents risk-adjusted weights for end-state scoring
type EndStateWeights struct {
	WeightTotalReturn     float64 `json:"weight_total_return"`
	WeightDiversification float64 `json:"weight_diversification"`
	WeightLongTermPromise float64 `json:"weight_long_term_promise"`
	WeightStability       float64 `json:"weight_stability"`
	WeightOpinion         float64 `json:"weight_opinion"`
}

// TotalReturnScore represents total return scoring components
type TotalReturnScore struct {
	CAGR          float64 `json:"cagr"`
	DividendYield float64 `json:"dividend_yield"`
	TotalReturn   float64 `json:"total_return"`
	Score         float64 `json:"score"`
}

// LongTermPromiseScore represents long-term promise components
type LongTermPromiseScore struct {
	Consistency         float64 `json:"consistency"`
	FinancialStrength   float64 `json:"financial_strength"`
	DividendConsistency float64 `json:"dividend_consistency"`
	Sortino             float64 `json:"sortino"`
	Score               float64 `json:"score"`
}

// StabilityScore represents stability components
type StabilityScore struct {
	Volatility float64 `json:"volatility"`
	Drawdown   float64 `json:"drawdown"`
	Sharpe     float64 `json:"sharpe"`
	Score      float64 `json:"score"`
}

// PortfolioEndStateScore represents complete end-state analysis
type PortfolioEndStateScore struct {
	RiskProfile string `json:"risk_profile"`
	Error       string `json:"error,omitempty"`
	TotalReturn struct {
		WeightedScore float64 `json:"weighted_score"`
		Weight        float64 `json:"weight"`
		Contribution  float64 `json:"contribution"`
	} `json:"total_return"`
	Diversification struct {
		Score        float64 `json:"score"`
		Weight       float64 `json:"weight"`
		Contribution float64 `json:"contribution"`
	} `json:"diversification"`
	LongTermPromise struct {
		WeightedScore float64 `json:"weighted_score"`
		Weight        float64 `json:"weight"`
		Contribution  float64 `json:"contribution"`
	} `json:"long_term_promise"`
	Stability struct {
		WeightedScore float64 `json:"weighted_score"`
		Weight        float64 `json:"weight"`
		Contribution  float64 `json:"contribution"`
	} `json:"stability"`
	Opinion struct {
		Score        float64 `json:"score"`
		Weight       float64 `json:"weight"`
		Contribution float64 `json:"contribution"`
	} `json:"opinion"`
	EndStateScore float64 `json:"end_state_score"`
}

// End-state scoring weights (default/balanced profile)
const (
	weightTotalReturnDefault     = 0.35
	weightDiversificationDefault = 0.25
	weightLongTermPromiseDefault = 0.20
	weightStabilityDefault       = 0.15
	weightOpinionDefault         = 0.05

	// Long-term promise sub-weights
	promiseWeightConsistency       = 0.35
	promiseWeightFinancials        = 0.25
	promiseWeightDividendStability = 0.25
	promiseWeightSortino           = 0.15

	// Stability sub-weights
	stabilityWeightVolatility = 0.50
	stabilityWeightDrawdown   = 0.30
	stabilityWeightSharpe     = 0.20
)

// NewEndStateScorer creates a new end-state scorer
func NewEndStateScorer() *EndStateScorer {
	return &EndStateScorer{}
}

// GetRiskProfileWeights returns scoring weights adjusted for risk profile
//
// Args:
//
//	riskProfile: "conservative", "balanced", or "aggressive"
//
// Returns:
//
//	EndStateWeights with weights that sum to 1.0
func (es *EndStateScorer) GetRiskProfileWeights(riskProfile string) EndStateWeights {
	switch riskProfile {
	case "conservative":
		// Conservative: Emphasize stability and diversification, reduce return focus
		return EndStateWeights{
			WeightTotalReturn:     0.25,
			WeightDiversification: 0.30,
			WeightLongTermPromise: 0.20,
			WeightStability:       0.20,
			WeightOpinion:         0.05,
		}
	case "aggressive":
		// Aggressive: Emphasize return and promise, reduce stability focus
		return EndStateWeights{
			WeightTotalReturn:     0.45,
			WeightDiversification: 0.20,
			WeightLongTermPromise: 0.25,
			WeightStability:       0.05,
			WeightOpinion:         0.05,
		}
	default: // balanced
		return EndStateWeights{
			WeightTotalReturn:     weightTotalReturnDefault,
			WeightDiversification: weightDiversificationDefault,
			WeightLongTermPromise: weightLongTermPromiseDefault,
			WeightStability:       weightStabilityDefault,
			WeightOpinion:         weightOpinionDefault,
		}
	}
}

// ScoreTotalReturn calculates bell curve scoring for total return
//
// Peak at target (default 12%). Uses asymmetric Gaussian.
//
// Args:
//
//	totalReturn: Total return value
//	target: Target return (default 12%)
//
// Returns:
//
//	Score from 0.15 to 1.0
func (es *EndStateScorer) ScoreTotalReturn(totalReturn, target float64) float64 {
	if totalReturn <= 0 {
		return scoring.BellCurveFloor
	}

	// Use slightly wider sigma for total return (more forgiving than CAGR)
	var sigma float64
	if totalReturn < target {
		sigma = scoring.BellCurveSigmaLeft
	} else {
		sigma = scoring.BellCurveSigmaRight * 1.2
	}

	rawScore := math.Exp(-math.Pow(totalReturn-target, 2) / (2 * math.Pow(sigma, 2)))

	return scoring.BellCurveFloor + rawScore*(1-scoring.BellCurveFloor)
}

// CalculateTotalReturnScore calculates total return score (CAGR + dividend yield combined)
//
// Args:
//
//	metrics: Pre-fetched metrics dict containing CAGR_5Y and DIVIDEND_YIELD
//
// Returns:
//
//	TotalReturnScore with all components
func (es *EndStateScorer) CalculateTotalReturnScore(metrics map[string]float64) TotalReturnScore {
	// Get CAGR from metrics dict
	cagr, hasCagr := metrics["CAGR_5Y"]
	if !hasCagr {
		cagr = 0.0
	}

	// Get dividend yield from metrics dict
	dividendYield, hasDiv := metrics["DIVIDEND_YIELD"]
	if !hasDiv {
		dividendYield = 0.0
	}

	// Calculate total return
	totalReturn := cagr + dividendYield

	// Score it
	score := es.ScoreTotalReturn(totalReturn, 0.12)

	return TotalReturnScore{
		CAGR:          round4(cagr),
		DividendYield: round4(dividendYield),
		TotalReturn:   round4(totalReturn),
		Score:         round3(score),
	}
}

// deriveDividendConsistencyFromPayout derives dividend consistency score from payout ratio
func deriveDividendConsistencyFromPayout(payout float64) float64 {
	if payout >= 0.3 && payout <= 0.6 {
		return 1.0
	} else if payout < 0.3 {
		return 0.5 + (payout/0.3)*0.5
	} else if payout <= 0.8 {
		return 1.0 - ((payout-0.6)/0.2)*0.3
	}
	return 0.4
}

// convertSortinoToScore converts Sortino ratio to score (0-1)
func convertSortinoToScore(sortino float64) float64 {
	if sortino >= 2.0 {
		return 1.0
	} else if sortino >= 1.5 {
		return 0.8 + (sortino-1.5)*0.4
	} else if sortino >= 1.0 {
		return 0.6 + (sortino-1.0)*0.4
	} else if sortino >= 0 {
		return sortino * 0.6
	}
	return 0.0
}

// CalculateLongTermPromise calculates long-term promise score
//
// Combines:
// - Consistency (35%): 5Y vs 10Y CAGR similarity
// - Financial Strength (25%): Margins, debt, liquidity
// - Dividend Consistency (25%): No big cuts, sustainable payout
// - Sortino (15%): Good returns with low downside risk
//
// Args:
//
//	metrics: Pre-fetched metrics dict containing CONSISTENCY_SCORE, FINANCIAL_STRENGTH,
//	         DIVIDEND_CONSISTENCY (or PAYOUT_RATIO), and SORTINO
//
// Returns:
//
//	LongTermPromiseScore with all components
func (es *EndStateScorer) CalculateLongTermPromise(metrics map[string]float64) LongTermPromiseScore {
	// Get consistency score from metrics
	consistencyScore, hasConsistency := metrics["CONSISTENCY_SCORE"]
	if !hasConsistency {
		consistencyScore = 0.5
	}

	// Get financial strength from metrics
	financialStrength, hasFinancial := metrics["FINANCIAL_STRENGTH"]
	if !hasFinancial {
		financialStrength = 0.5
	}

	// Get dividend consistency from metrics (or derive from payout ratio)
	dividendConsistency, hasDivConsistency := metrics["DIVIDEND_CONSISTENCY"]
	if !hasDivConsistency {
		payout, hasPayout := metrics["PAYOUT_RATIO"]
		if hasPayout {
			dividendConsistency = deriveDividendConsistencyFromPayout(payout)
		} else {
			dividendConsistency = 0.5
		}
	}

	// Get Sortino and convert to score
	sortinoScore := 0.5
	sortinoRaw, hasSortino := metrics["SORTINO"]
	if hasSortino {
		sortinoScore = convertSortinoToScore(sortinoRaw)
	}

	total := consistencyScore*promiseWeightConsistency +
		financialStrength*promiseWeightFinancials +
		dividendConsistency*promiseWeightDividendStability +
		sortinoScore*promiseWeightSortino

	return LongTermPromiseScore{
		Consistency:         round3(consistencyScore),
		FinancialStrength:   round3(financialStrength),
		DividendConsistency: round3(dividendConsistency),
		Sortino:             round3(sortinoScore),
		Score:               round3(math.Min(1.0, total)),
	}
}

// convertVolatilityToScore converts volatility to score (inverse - lower is better)
func convertVolatilityToScore(volatility float64) float64 {
	if volatility <= 0.15 {
		return 1.0
	} else if volatility <= 0.25 {
		return 1.0 - ((volatility-0.15)/0.10)*0.3
	} else if volatility <= 0.40 {
		return 0.7 - ((volatility-0.25)/0.15)*0.4
	}
	return math.Max(0.1, 0.3-(volatility-0.40))
}

// convertDrawdownToScore converts max drawdown to score
func convertDrawdownToScore(maxDD float64) float64 {
	ddPct := math.Abs(maxDD)
	if ddPct <= 0.10 {
		return 1.0
	} else if ddPct <= 0.20 {
		return 0.8 + (0.20-ddPct)*2
	} else if ddPct <= 0.30 {
		return 0.6 + (0.30-ddPct)*2
	} else if ddPct <= 0.50 {
		return 0.2 + (0.50-ddPct)*2
	}
	return math.Max(0.0, 0.2-(ddPct-0.50))
}

// convertSharpeToScore converts Sharpe ratio to score
func convertSharpeToScore(sharpe float64) float64 {
	if sharpe >= 2.0 {
		return 1.0
	} else if sharpe >= 1.0 {
		return 0.7 + (sharpe-1.0)*0.3
	} else if sharpe >= 0.5 {
		return 0.4 + (sharpe-0.5)*0.6
	} else if sharpe >= 0 {
		return sharpe * 0.8
	}
	return 0.0
}

// CalculateStabilityScore calculates stability score
//
// Combines:
// - Inverse Volatility (50%): Lower volatility = higher score
// - Drawdown Score (30%): Lower max drawdown = higher score
// - Sharpe Score (20%): Higher risk-adjusted returns = higher score
//
// Args:
//
//	metrics: Pre-fetched metrics dict containing VOLATILITY_ANNUAL, MAX_DRAWDOWN, and SHARPE
//
// Returns:
//
//	StabilityScore with all components
func (es *EndStateScorer) CalculateStabilityScore(metrics map[string]float64) StabilityScore {
	// Get volatility and convert to score
	volatilityScore := 0.5
	volatilityRaw, hasVol := metrics["VOLATILITY_ANNUAL"]
	if hasVol && volatilityRaw > 0 {
		volatilityScore = convertVolatilityToScore(volatilityRaw)
	}

	// Get drawdown and convert to score
	drawdownScore := 0.5
	maxDD, hasDD := metrics["MAX_DRAWDOWN"]
	if hasDD {
		drawdownScore = convertDrawdownToScore(maxDD)
	}

	// Get Sharpe and convert to score
	sharpeScore := 0.5
	sharpeRaw, hasSharpe := metrics["SHARPE"]
	if hasSharpe {
		sharpeScore = convertSharpeToScore(sharpeRaw)
	}

	total := volatilityScore*stabilityWeightVolatility +
		drawdownScore*stabilityWeightDrawdown +
		sharpeScore*stabilityWeightSharpe

	return StabilityScore{
		Volatility: round3(volatilityScore),
		Drawdown:   round3(drawdownScore),
		Sharpe:     round3(sharpeScore),
		Score:      round3(math.Min(1.0, total)),
	}
}

// CalculatePortfolioEndStateScore calculates end-state score for an entire portfolio
//
// This is the main function used by the holistic planner to evaluate
// the quality of a portfolio after executing a sequence of trades.
//
// Args:
//
//	positions: Map of symbol -> position value in EUR
//	totalValue: Total portfolio value in EUR
//	diversificationScore: Pre-calculated diversification score (0-1)
//	metricsCache: Pre-fetched metrics dict mapping symbol -> metrics dict
//	opinionScore: Average analyst opinion score (default 0.5)
//	riskProfile: "conservative", "balanced", or "aggressive"
//
// Returns:
//
//	PortfolioEndStateScore with detailed breakdown
func (es *EndStateScorer) CalculatePortfolioEndStateScore(
	positions map[string]float64,
	totalValue float64,
	diversificationScore float64,
	metricsCache map[string]map[string]float64,
	opinionScore float64,
	riskProfile string,
) PortfolioEndStateScore {
	result := PortfolioEndStateScore{
		RiskProfile: riskProfile,
	}

	if totalValue <= 0 || len(positions) == 0 {
		result.Error = "Invalid portfolio data"
		result.EndStateScore = 0.5
		return result
	}

	// Calculate weighted averages across all positions
	weightedTotalReturn := 0.0
	weightedPromise := 0.0
	weightedStability := 0.0

	for symbol, value := range positions {
		if value <= 0 {
			continue
		}

		weight := value / totalValue

		// Get metrics for this symbol (use empty dict if missing)
		metrics, hasMetrics := metricsCache[symbol]
		if !hasMetrics {
			metrics = make(map[string]float64)
		}

		// Get scores for this position using cached metrics
		trScore := es.CalculateTotalReturnScore(metrics)
		promiseScore := es.CalculateLongTermPromise(metrics)
		stabScore := es.CalculateStabilityScore(metrics)

		weightedTotalReturn += trScore.Score * weight
		weightedPromise += promiseScore.Score * weight
		weightedStability += stabScore.Score * weight
	}

	// Get risk-adjusted weights
	weights := es.GetRiskProfileWeights(riskProfile)

	// Calculate final end-state score with risk-adjusted weights
	endStateScore := weightedTotalReturn*weights.WeightTotalReturn +
		diversificationScore*weights.WeightDiversification +
		weightedPromise*weights.WeightLongTermPromise +
		weightedStability*weights.WeightStability +
		opinionScore*weights.WeightOpinion

	// Build detailed breakdown
	result.TotalReturn.WeightedScore = round3(weightedTotalReturn)
	result.TotalReturn.Weight = weights.WeightTotalReturn
	result.TotalReturn.Contribution = round3(weightedTotalReturn * weights.WeightTotalReturn)

	result.Diversification.Score = round3(diversificationScore)
	result.Diversification.Weight = weights.WeightDiversification
	result.Diversification.Contribution = round3(diversificationScore * weights.WeightDiversification)

	result.LongTermPromise.WeightedScore = round3(weightedPromise)
	result.LongTermPromise.Weight = weights.WeightLongTermPromise
	result.LongTermPromise.Contribution = round3(weightedPromise * weights.WeightLongTermPromise)

	result.Stability.WeightedScore = round3(weightedStability)
	result.Stability.Weight = weights.WeightStability
	result.Stability.Contribution = round3(weightedStability * weights.WeightStability)

	result.Opinion.Score = round3(opinionScore)
	result.Opinion.Weight = weights.WeightOpinion
	result.Opinion.Contribution = round3(opinionScore * weights.WeightOpinion)

	result.EndStateScore = round3(math.Min(1.0, endStateScore))

	return result
}
