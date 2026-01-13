package settings

// ============================================================================
// EVALUATION WEIGHTS
// ============================================================================

// EvaluationWeights holds the adjusted weights for portfolio evaluation scoring.
// These weights sum to 1.0 after normalization and control how different aspects
// of the end portfolio state are weighted in the evaluation function.
//
// Pure end-state scoring philosophy:
// - Portfolio Quality (35%): Total return, long-term promise, stability
// - Diversification & Alignment (30%): Geographic, industry, optimizer alignment
// - Risk-Adjusted Metrics (25%): Sharpe, volatility, drawdown
// - End-State Improvement (10%): How much the portfolio improved vs start
type EvaluationWeights struct {
	PortfolioQuality         float64 // Weight for total return, long-term promise, stability
	DiversificationAlignment float64 // Weight for geographic, industry, optimizer alignment
	RiskAdjustedMetrics      float64 // Weight for Sharpe, volatility, drawdown
	EndStateImprovement      float64 // Weight for improvement from start to end state
}

// Normalize adjusts weights to sum to 1.0
func (w EvaluationWeights) Normalize() EvaluationWeights {
	sum := w.PortfolioQuality + w.DiversificationAlignment +
		w.RiskAdjustedMetrics + w.EndStateImprovement

	if sum == 0 {
		// Default weights for pure end-state scoring
		return EvaluationWeights{
			PortfolioQuality:         0.35,
			DiversificationAlignment: 0.30,
			RiskAdjustedMetrics:      0.25,
			EndStateImprovement:      0.10,
		}
	}

	return EvaluationWeights{
		PortfolioQuality:         w.PortfolioQuality / sum,
		DiversificationAlignment: w.DiversificationAlignment / sum,
		RiskAdjustedMetrics:      w.RiskAdjustedMetrics / sum,
		EndStateImprovement:      w.EndStateImprovement / sum,
	}
}

// ============================================================================
// CORE TRADING PARAMS
// ============================================================================

// ProfitTakingParams holds adjusted profit-taking thresholds
type ProfitTakingParams struct {
	MinGainThreshold  float64 // Minimum gain before considering taking profits
	WindfallThreshold float64 // Threshold for windfall (exceptional) gains
	SellPercentage    float64 // Percentage of position to sell
}

// AveragingDownParams holds adjusted averaging down thresholds
type AveragingDownParams struct {
	MaxLossThreshold float64 // Maximum loss threshold for averaging down
	MinLossThreshold float64 // Minimum loss to trigger averaging down consideration
	Percent          float64 // Percentage of position to add when averaging down
}

// OpportunityBuysParams holds adjusted opportunity buy thresholds
type OpportunityBuysParams struct {
	MinScore                 float64 // Minimum quality score for buys
	MaxValuePerPosition      float64 // Maximum value per position
	MaxPositions             int     // Maximum number of positions to consider
	TargetReturnThresholdPct float64 // Target return threshold as percentage
}

// ============================================================================
// KELLY SIZING
// ============================================================================

// KellyParams holds adjusted Kelly criterion parameters
type KellyParams struct {
	FixedFractional           float64 // Kelly fraction multiplier
	MinPositionSize           float64 // Minimum position size as fraction
	MaxPositionSize           float64 // Maximum position size as fraction
	BearReduction             float64 // Position reduction factor in bear markets
	BaseMultiplier            float64 // Base Kelly multiplier
	ConfidenceAdjustmentRange float64 // Range for confidence adjustments
	RegimeAdjustmentRange     float64 // Range for regime adjustments
	MinMultiplier             float64 // Minimum multiplier floor
	MaxMultiplier             float64 // Maximum multiplier ceiling
	BearMaxReduction          float64 // Maximum reduction in bear markets
	BullThreshold             float64 // Threshold for bull market regime
	BearThreshold             float64 // Threshold for bear market regime (negative)
}

// ============================================================================
// RISK MANAGEMENT
// ============================================================================

// RiskManagementParams holds adjusted risk management parameters
type RiskManagementParams struct {
	MinHoldDays          int     // Minimum days to hold before selling
	SellCooldownDays     int     // Days between sell operations
	MaxLossThreshold     float64 // Maximum loss before forced action
	MaxSellPercentage    float64 // Maximum percentage to sell at once
	MinTimeBetweenTrades int     // Minimum minutes between trades
	MaxTradesPerDay      int     // Maximum trades per day
	MaxTradesPerWeek     int     // Maximum trades per week
}

// ============================================================================
// QUALITY GATES
// ============================================================================

// QualityGateParams holds adjusted quality gate thresholds
type QualityGateParams struct {
	FundamentalsThreshold float64 // Minimum fundamentals score
	LongTermThreshold     float64 // Minimum long-term score
	ExceptionalThreshold  float64 // Threshold for exceptional quality
	AbsoluteMinCAGR       float64 // Absolute minimum CAGR requirement
}

// ============================================================================
// REBALANCING
// ============================================================================

// RebalancingParams holds adjusted rebalancing thresholds
type RebalancingParams struct {
	MinOverweightThreshold  float64 // Minimum overweight to trigger rebalance
	PositionDriftThreshold  float64 // Position drift threshold
	CashThresholdMultiplier float64 // Multiplier for cash threshold
}

// ============================================================================
// VOLATILITY
// ============================================================================

// VolatilityParams holds adjusted volatility acceptance thresholds
type VolatilityParams struct {
	VolatileThreshold     float64 // Threshold for "volatile" label
	HighThreshold         float64 // Threshold for "high volatility"
	MaxAcceptable         float64 // Maximum acceptable volatility
	MaxAcceptableDrawdown float64 // Maximum acceptable drawdown
}

// ============================================================================
// TRANSACTION EFFICIENCY
// ============================================================================

// TransactionParams holds adjusted transaction efficiency parameters
type TransactionParams struct {
	MaxCostRatio     float64 // Maximum cost ratio for transactions
	LimitOrderBuffer float64 // Buffer for limit orders
}

// ============================================================================
// PRIORITY BOOSTS
// ============================================================================

// ProfitTakingBoosts holds priority multipliers for profit-taking opportunities
type ProfitTakingBoosts struct {
	WindfallPriority float64 // Boost for windfall opportunities
	BubbleRisk       float64 // Boost for bubble risk positions
	NeedsRebalance   float64 // Boost for positions needing rebalance
	Overweight       float64 // Boost for overweight positions
	Overvalued       float64 // Boost for overvalued positions
	Near52wHigh      float64 // Boost for positions near 52-week high
}

// AveragingDownBoosts holds priority multipliers for averaging down opportunities
type AveragingDownBoosts struct {
	QualityValue      float64 // Boost for quality value opportunities
	RecoveryCandidate float64 // Boost for recovery candidates
	HighQuality       float64 // Boost for high quality positions
	ValueOpportunity  float64 // Boost for value opportunities
}

// OpportunityBuyBoosts holds priority multipliers for buy opportunities
type OpportunityBuyBoosts struct {
	QuantumWarningPenalty              float64 // Penalty for quantum warnings
	QualityValueBuy                    float64 // Boost for quality value buys
	HighQualityValue                   float64 // Boost for high quality value
	DeepValue                          float64 // Boost for deep value
	OversoldQuality                    float64 // Boost for oversold quality
	ExcellentReturns                   float64 // Boost for excellent returns
	HighReturns                        float64 // Boost for high returns
	QualityHighCAGR                    float64 // Boost for quality with high CAGR
	DividendGrower                     float64 // Boost for dividend growers
	HighDividend                       float64 // Boost for high dividend
	QualityPenaltyReductionExceptional float64 // Penalty reduction for exceptional quality
	QualityPenaltyReductionHigh        float64 // Penalty reduction for high quality
}

// RegimeBoosts holds priority multipliers for regime-based adjustments
type RegimeBoosts struct {
	LowRisk            float64 // Boost for low-risk positions
	MediumRisk         float64 // Boost for medium-risk positions
	HighRiskPenalty    float64 // Penalty for high-risk positions
	GrowthBull         float64 // Boost for growth in bull markets
	ValueBear          float64 // Boost for value in bear markets
	DividendSideways   float64 // Boost for dividends in sideways markets
	StrongFundamentals float64 // Boost for strong fundamentals
}

// ============================================================================
// TAG ASSIGNER THRESHOLDS
// ============================================================================

// ValueThresholds holds value-related tag thresholds
type ValueThresholds struct {
	ValueOpportunityDiscountPct float64 // Discount % for value opportunity
	DeepValueDiscountPct        float64 // Discount % for deep value
	DeepValueExtremePct         float64 // Discount % for extreme deep value
	UndervaluedPEThreshold      float64 // PE threshold for undervalued (negative)
	Below52wHighThreshold       float64 // % below 52-week high threshold
}

// QualityThresholds holds quality-related tag thresholds
type QualityThresholds struct {
	HighQualityFundamentals     float64 // Fundamentals score for high quality
	HighQualityLongTerm         float64 // Long-term score for high quality
	StableFundamentals          float64 // Fundamentals score for stable
	StableVolatilityMax         float64 // Maximum volatility for stable
	StableConsistency           float64 // Consistency score for stable
	ConsistentGrowerConsistency float64 // Consistency for consistent grower
	ConsistentGrowerCAGR        float64 // Minimum CAGR for consistent grower
	StrongFundamentalsThreshold float64 // Threshold for strong fundamentals
}

// TechnicalThresholds holds technical indicator thresholds
type TechnicalThresholds struct {
	RSIOversold               float64 // RSI level for oversold
	RSIOverbought             float64 // RSI level for overbought
	RecoveryMomentumThreshold float64 // Momentum threshold for recovery
	RecoveryFundamentalsMin   float64 // Minimum fundamentals for recovery
	RecoveryDiscountMin       float64 // Minimum discount for recovery
}

// DividendThresholds holds dividend-related tag thresholds
type DividendThresholds struct {
	HighDividendYield        float64 // Yield threshold for high dividend
	DividendOpportunityScore float64 // Score threshold for dividend opportunity
	DividendOpportunityYield float64 // Yield threshold for dividend opportunity
	DividendConsistencyScore float64 // Consistency score for dividend
}

// DangerThresholds holds danger/warning tag thresholds
type DangerThresholds struct {
	OvervaluedPEThreshold    float64 // PE threshold for overvalued
	OvervaluedNearHighPct    float64 // % near high for overvalued
	UnsustainableGainsReturn float64 // Return threshold for unsustainable
	ValuationStretchEMA      float64 // EMA stretch for valuation
	UnderperformingDays      int     // Days for underperforming
	StagnantReturnThreshold  float64 // Return threshold for stagnant
	StagnantDaysThreshold    int     // Days threshold for stagnant
}

// PortfolioRiskThresholds holds portfolio risk tag thresholds
type PortfolioRiskThresholds struct {
	OverweightDeviation        float64 // Deviation threshold for overweight
	OverweightAbsolute         float64 // Absolute threshold for overweight
	ConcentrationRiskThreshold float64 // Threshold for concentration risk
	NeedsRebalanceDeviation    float64 // Deviation for needs rebalance
}

// RiskProfileThresholds holds risk profile classification thresholds
type RiskProfileThresholds struct {
	LowRiskVolatilityMax          float64 // Max volatility for low risk
	LowRiskFundamentalsMin        float64 // Min fundamentals for low risk
	LowRiskDrawdownMax            float64 // Max drawdown for low risk
	MediumRiskVolatilityMin       float64 // Min volatility for medium risk
	MediumRiskVolatilityMax       float64 // Max volatility for medium risk
	MediumRiskFundamentalsMin     float64 // Min fundamentals for medium risk
	HighRiskVolatilityThreshold   float64 // Volatility threshold for high risk
	HighRiskFundamentalsThreshold float64 // Fundamentals threshold for high risk
}

// BubbleTrapThresholds holds bubble and value trap detection thresholds
type BubbleTrapThresholds struct {
	BubbleCAGRThreshold         float64 // CAGR threshold for bubble
	BubbleSharpeThreshold       float64 // Sharpe threshold for bubble
	BubbleVolatilityThreshold   float64 // Volatility threshold for bubble
	BubbleFundamentalsThreshold float64 // Fundamentals threshold for bubble
	ValueTrapFundamentals       float64 // Fundamentals threshold for value trap
	ValueTrapLongTerm           float64 // Long-term threshold for value trap
	ValueTrapMomentum           float64 // Momentum threshold for value trap
	ValueTrapVolatility         float64 // Volatility threshold for value trap
	QuantumBubbleHighProb       float64 // High probability for quantum bubble
	QuantumBubbleWarningProb    float64 // Warning probability for quantum bubble
	QuantumTrapHighProb         float64 // High probability for quantum trap
	QuantumTrapWarningProb      float64 // Warning probability for quantum trap
}

// TotalReturnThresholds holds total return classification thresholds
type TotalReturnThresholds struct {
	ExcellentTotalReturn     float64 // Threshold for excellent return
	HighTotalReturn          float64 // Threshold for high return
	ModerateTotalReturn      float64 // Threshold for moderate return
	DividendTotalReturnYield float64 // Yield threshold for dividend return
	DividendTotalReturnCAGR  float64 // CAGR threshold for dividend return
}

// RegimeThresholds holds regime-specific tag thresholds
type RegimeThresholds struct {
	BearSafeVolatility       float64 // Volatility threshold for bear-safe
	BearSafeFundamentals     float64 // Fundamentals threshold for bear-safe
	BearSafeDrawdown         float64 // Drawdown threshold for bear-safe
	BullGrowthCAGR           float64 // CAGR threshold for bull growth
	BullGrowthFundamentals   float64 // Fundamentals threshold for bull growth
	RegimeVolatileVolatility float64 // Volatility threshold for regime volatile
}

// ============================================================================
// EVALUATION SCORING
// ============================================================================

// ScoringParams holds evaluation scoring parameters for pure end-state scoring.
// These parameters control thresholds for various scoring components.
type ScoringParams struct {
	DeviationScale       float64 // Scale for deviation penalties (diversification)
	RegimeBullThreshold  float64 // Threshold for bull regime (for regime-adaptive weights)
	RegimeBearThreshold  float64 // Threshold for bear regime (negative, for regime-adaptive weights)
	VolatilityExcellent  float64 // Volatility threshold for excellent score
	VolatilityGood       float64 // Volatility threshold for good score
	VolatilityAcceptable float64 // Volatility threshold for acceptable score
	DrawdownExcellent    float64 // Drawdown threshold for excellent score
	DrawdownGood         float64 // Drawdown threshold for good score
	DrawdownAcceptable   float64 // Drawdown threshold for acceptable score
	SharpeExcellent      float64 // Sharpe ratio for excellent score
	SharpeGood           float64 // Sharpe ratio for good score
	SharpeAcceptable     float64 // Sharpe ratio for acceptable score
}
