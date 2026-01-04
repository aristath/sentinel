package scoring

// Scoring Constants - All thresholds and weights for scoring calculations
// Faithful translation from Python: app/modules/scoring/domain/constants.py

// =============================================================================
// Quality Score Constants
// =============================================================================

const (
	// Bell curve target for total return (CAGR + dividend)
	// 11% is optimal for ~€1M retirement goal over 20 years
	OptimalCAGR               = 0.11
	DefaultTargetAnnualReturn = 0.11

	// Bell curve shape parameters (asymmetric Gaussian)
	BellCurveSigmaLeft  = 0.06 // Steeper rise (0% to peak)
	BellCurveSigmaRight = 0.10 // Gentler fall (peak to high growth)
	BellCurveFloor      = 0.15 // Minimum score for any positive return

	// Dividend thresholds for DRIP priority bonus
	HighDividendThreshold = 0.06 // 6%+ yield gets max bonus (+0.10)
	MidDividendThreshold  = 0.03 // 3%+ yield gets mid bonus (+0.07)
	LowDividendBonus      = 0.03
	MidDividendBonus      = 0.07
	HighDividendBonus     = 0.10

	// Dividend reinvestment strategy threshold
	HighDividendReinvestmentThreshold = 0.03 // 3%+ yield: reinvest in same security

	// Quality score component weights (must sum to 1.0)
	QualityWeightTotalReturn       = 0.40
	QualityWeightConsistency       = 0.20
	QualityWeightFinancialStrength = 0.20
	QualityWeightSharpe            = 0.10
	QualityWeightMaxDrawdown       = 0.10

	// Sharpe ratio thresholds
	SharpeExcellent = 2.0 // Score = 1.0
	SharpeGood      = 1.0 // Score = 0.7
	SharpeOK        = 0.5 // Score = 0.4

	// Max drawdown thresholds (as positive percentages)
	DrawdownExcellent = 0.10 // <10% drawdown = 1.0
	DrawdownGood      = 0.20 // <20% drawdown = 0.8+
	DrawdownOK        = 0.30 // <30% drawdown = 0.6+
	DrawdownPoor      = 0.50 // <50% drawdown = 0.2+
)

// =============================================================================
// Opportunity Score Constants
// =============================================================================

const (
	// Market average P/E for comparison
	DefaultMarketAvgPE = 22

	// Forward-looking market indicator thresholds
	VIXLow           = 15.0 // Low volatility = optimistic
	VIXNormal        = 20.0 // Normal volatility
	VIXHigh          = 30.0 // High volatility = pessimistic
	VIXAdjustmentMax = 0.10 // Max ±10% adjustment for VIX

	// Yield curve slope thresholds
	YieldCurveNormal        = 0.01  // 1%+ slope = normal (expansionary)
	YieldCurveFlat          = 0.0   // Flat curve
	YieldCurveInverted      = -0.01 // Negative = inverted (recession signal)
	YieldCurveAdjustmentMax = 0.15  // Max ±15% adjustment for yield curve

	// Market P/E thresholds (vs historical average of 22)
	PECheap         = 18.0 // Below average = cheap market
	PEFair          = 22.0 // At average = fair value
	PEExpensive     = 26.0 // Above average = expensive market
	PEAdjustmentMax = 0.10 // Max ±10% adjustment for P/E

	// 52-week high thresholds
	BelowHighExcellent = 0.30 // 30%+ below = 1.0
	BelowHighGood      = 0.20 // 20-30% below = 0.8-1.0
	BelowHighOK        = 0.10 // 10-20% below = 0.5-0.8

	// EMA distance thresholds
	EMAVeryBelow = -0.10 // 10%+ below EMA = 1.0
	EMABelow     = -0.05 // 5-10% below = 0.7-1.0
	EMAVeryAbove = 0.10  // 10%+ above = 0.2

	// RSI thresholds
	RSIOversold   = 30 // Below = 1.0 (buy signal)
	RSIOverbought = 70 // Above = 0.0 (sell signal)

	// Opportunity score component weights (must sum to 1.0)
	OpportunityWeight52WHigh   = 0.30
	OpportunityWeightEMA       = 0.25
	OpportunityWeightPE        = 0.25
	OpportunityWeightRSI       = 0.10
	OpportunityWeightBollinger = 0.10
)

// =============================================================================
// Combined Score Weights
// =============================================================================

const (
	// Final score weights for BUY decisions (must sum to 1.0)
	ScoreWeightQuality       = 0.35
	ScoreWeightOpportunity   = 0.35
	ScoreWeightAnalyst       = 0.05 // Reduced from 0.15 - tiebreaker only
	ScoreWeightAllocationFit = 0.25 // Increased from 0.15 - prioritize diversification

	// Without allocation fit, these 3 sum to 0.75
	ScoreWeightBase = 0.75 // Quality + Opportunity + Analyst
)

// =============================================================================
// Allocation Fit Constants
// =============================================================================

const (
	// Allocation fit component weights (must sum to 1.0)
	AllocationWeightGeography     = 0.40
	AllocationWeightIndustry      = 0.30
	AllocationWeightAveragingDown = 0.30

	// Averaging down boost for positions underwater
	MaxCostBasisBoost       = 0.40 // Max boost at 20% loss
	CostBasisBoostThreshold = 0.20 // No boost beyond 20% loss

	// Concentration limits
	ConcentrationHigh = 0.10 // >10% = reduce enthusiasm
	ConcentrationMed  = 0.05 // 5-10% = slight reduction
)

// =============================================================================
// Sell Score Constants
// =============================================================================

const (
	// Hard blocks (NEVER sell if any apply)
	DefaultMinHoldDays      = 90    // 3 months minimum hold
	DefaultSellCooldownDays = 180   // 6 months between sells
	DefaultMaxLossThreshold = -0.20 // Never sell if down more than 20%
	DefaultMinSellValueEUR  = 100.0 // Minimum sell value in EUR

	// Sell quantity limits
	MinSellPct = 0.10 // Minimum 10% of position
	MaxSellPct = 0.50 // Maximum 50% of position

	// Target annual return range (ideal performance)
	TargetReturnMin = 0.08 // 8%
	TargetReturnMax = 0.15 // 15%

	// Sell score component weights (must sum to 1.0)
	SellWeightUnderperformance = 0.35 // Primary factor
	SellWeightTimeHeld         = 0.18
	SellWeightPortfolioBalance = 0.18
	SellWeightInstability      = 0.14
	SellWeightDrawdown         = 0.15 // PyFolio-based drawdown analysis

	// Instability detection thresholds
	InstabilityRateVeryHot = 0.50 // >50% annualized = 1.0
	InstabilityRateHot     = 0.30 // >30% = 0.7
	InstabilityRateWarm    = 0.20 // >20% = 0.4

	VolatilitySpikeHigh = 2.0 // Vol doubled = 1.0
	VolatilitySpikeMed  = 1.5 // Vol up 50% = 0.7
	VolatilitySpikeLow  = 1.2 // Vol up 20% = 0.4

	ValuationStretchHigh = 0.30 // >30% above MA = 1.0
	ValuationStretchMed  = 0.20 // >20% = 0.7
	ValuationStretchLow  = 0.10 // >10% = 0.4
)

// =============================================================================
// Technical Indicator Parameters
// =============================================================================

const (
	TradingDaysPerYear = 252
	EMALength          = 200
	RSILength          = 14
	BollingerLength    = 20
	BollingerStd       = 2

	// Minimum data requirements
	MinDaysForOpportunity = 50
	MinMonthsForCAGR      = 12
	MinDaysForVolatility  = 30
)

// =============================================================================
// Holistic Planning Constants
// =============================================================================

const (
	// Windfall detection thresholds
	WindfallExcessHigh      = 0.50 // 50%+ above expected = high windfall
	WindfallExcessMedium    = 0.25 // 25-50% above expected = medium windfall
	WindfallSellPctHigh     = 0.40 // Sell 40% on high windfall
	WindfallSellPctMedium   = 0.20 // Sell 20% on medium windfall
	ConsistentDoubleSellPct = 0.30 // Sell 30% on consistent doubler

	// Dividend cut threshold
	DividendCutThreshold = 0.20 // 20% YoY cut = "big cut"
)

// =============================================================================
// Portfolio Optimization Constants
// =============================================================================

const (
	// Target return for Mean-Variance optimization
	OptimizerTargetReturn = 0.11 // 11% annual target

	// Expected returns calculation weights
	ExpectedReturnsCAGRWeight  = 0.70 // 70% historical CAGR
	ExpectedReturnsScoreWeight = 0.30 // 30% score-adjusted

	// Covariance matrix parameters
	CovarianceLookbackDays = 365 // 1 year of daily returns
	CovarianceMinHistory   = 60  // Minimum days needed for covariance

	// Weight cutoffs
	OptimizerWeightCutoff = 0.005 // Ignore weights below 0.5%
	MaxConcentration      = 0.20  // Maximum 20% in any single security

	// Expected return bounds (clamp to reasonable range)
	ExpectedReturnMin = -0.10 // -10% floor
	ExpectedReturnMax = 0.30  // +30% ceiling

	// Allocation tolerance bands for sector constraints
	GeoAllocationTolerance = 0.10 // +/- 10% from target
	IndAllocationTolerance = 0.15 // +/- 15% from target

	// Hard concentration limits (safety guardrails)
	MaxCountryConcentration  = 0.35 // 35% max per country
	MaxSectorConcentration   = 0.30 // 30% max per sector
	MaxPositionConcentration = 0.15 // 15% max per position

	// Alert thresholds (80% of caps)
	CountryAlertThreshold  = 0.28 // Alert at 28% (80% of 35%)
	SectorAlertThreshold   = 0.24 // Alert at 24% (80% of 30%)
	PositionAlertThreshold = 0.12 // Alert at 12% (80% of 15%)
)
