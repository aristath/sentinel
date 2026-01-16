package domain

import (
	scoringdomain "github.com/aristath/sentinel/internal/modules/scoring/domain"
	"github.com/aristath/sentinel/internal/modules/universe"
)

// OpportunityContext contains all data needed by opportunity calculators
// to identify trading opportunities (buys, sells, rebalancing, etc.).
//
// CURRENCY INVARIANT: All monetary values are in EUR.
// Currency conversion happens at the input boundary before this context is created.
// After removing universe.Security: Uses universe.Security directly (single source of truth).
type OpportunityContext struct {
	// Portfolio state
	PortfolioContext       *scoringdomain.PortfolioContext `json:"portfolio_context"`
	EnrichedPositions      []EnrichedPosition              `json:"enriched_positions"` // REPLACES old Positions field
	Securities             []universe.Security             `json:"securities"`
	AvailableCashEUR       float64                         `json:"available_cash_eur"`
	TotalPortfolioValueEUR float64                         `json:"total_portfolio_value_eur"`

	// Market data (ALL PRICES IN EUR, ALL KEYS ARE ISIN)
	CurrentPrices map[string]float64           `json:"current_prices"` // Key: ISIN (e.g., "US0378331005"), Value: Price in EUR
	StocksByISIN  map[string]universe.Security `json:"stocks_by_isin"` // Key: ISIN (primary lookup)

	// Optional enrichment data
	SecurityScores       map[string]float64 `json:"security_scores,omitempty"`       // Final scores by ISIN (internal identifier)
	GeographyAllocations map[string]float64 `json:"geography_allocations,omitempty"` // Current allocations by geography
	GeographyWeights     map[string]float64 `json:"geography_weights,omitempty"`     // Target weights by geography
	TargetWeights        map[string]float64 `json:"target_weights,omitempty"`        // Optimizer target weights

	// Target return filtering data (for flexible penalty system)
	CAGRs                    map[string]float64 `json:"cagrs,omitempty"`                       // CAGR by ISIN (for target return filtering)
	LongTermScores           map[string]float64 `json:"long_term_scores,omitempty"`            // Long-term scores by ISIN (for quality override)
	StabilityScores          map[string]float64 `json:"stability_scores,omitempty"`            // Stability scores by ISIN (for quality override, replaces stability)
	TargetReturn             float64            `json:"target_return,omitempty"`               // Target annual return (default: 0.11 = 11%)
	TargetReturnThresholdPct float64            `json:"target_return_threshold_pct,omitempty"` // Threshold percentage (default: 0.80 = 80%)

	// Value trap detection data (for quality checks when tags disabled)
	// Note: P/E-based value trap detection removed - uses stability + long-term score based detection instead
	OpportunityScores map[string]float64 `json:"opportunity_scores,omitempty"` // Group score for opportunity (0-1) by ISIN
	MomentumScores    map[string]float64 `json:"momentum_scores,omitempty"`    // Momentum scores by ISIN (optional, derived from short-term)
	Volatility        map[string]float64 `json:"volatility,omitempty"`         // Volatility by ISIN (optional)
	RegimeScore       float64            `json:"regime_score,omitempty"`       // Current market regime score (single value, -1 to +1)

	// Risk metrics for evaluation
	Sharpe      map[string]float64 `json:"sharpe,omitempty"`       // Sharpe ratios by ISIN
	MaxDrawdown map[string]float64 `json:"max_drawdown,omitempty"` // Max drawdown by ISIN (negative values)

	// Constraints (ALL KEYS ARE ISIN)
	IneligibleISINs     map[string]bool `json:"ineligible_isins"`      // Key: ISIN - Can't sell these
	RecentlySoldISINs   map[string]bool `json:"recently_sold_isins"`   // Key: ISIN - Recently sold (cooldown)
	RecentlyBoughtISINs map[string]bool `json:"recently_bought_isins"` // Key: ISIN - Recently bought

	// Configuration
	TransactionCostFixed   float64 `json:"transaction_cost_fixed"`
	TransactionCostPercent float64 `json:"transaction_cost_percent"`
	AllowSell              bool    `json:"allow_sell"`
	AllowBuy               bool    `json:"allow_buy"`

	// Kelly-optimal position sizes (optional - if available from optimizer)
	KellySizes map[string]float64 `json:"kelly_sizes,omitempty"` // Kelly-optimal position sizes by ISIN (as fraction of portfolio)
}

// NewOpportunityContext creates a new OpportunityContext with defaults.
// After removing universe.Security: Uses universe.Security directly (single source of truth).
func NewOpportunityContext(
	portfolioContext *scoringdomain.PortfolioContext,
	enrichedPositions []EnrichedPosition,
	securities []universe.Security,
	availableCashEUR float64,
	totalPortfolioValueEUR float64,
	currentPrices map[string]float64,
) *OpportunityContext {
	// Build stocks by ISIN map (ONLY - no Symbol map)
	stocksByISIN := make(map[string]universe.Security, len(securities))
	for _, sec := range securities {
		if sec.ISIN != "" {
			stocksByISIN[sec.ISIN] = sec
		}
	}

	return &OpportunityContext{
		PortfolioContext:       portfolioContext,
		EnrichedPositions:      enrichedPositions,
		Securities:             securities,
		AvailableCashEUR:       availableCashEUR,
		TotalPortfolioValueEUR: totalPortfolioValueEUR,
		CurrentPrices:          currentPrices,
		StocksByISIN:           stocksByISIN,
		IneligibleISINs:        make(map[string]bool),
		RecentlySoldISINs:      make(map[string]bool),
		RecentlyBoughtISINs:    make(map[string]bool),
		TransactionCostFixed:   2.0,
		TransactionCostPercent: 0.002,
		AllowSell:              true,
		AllowBuy:               true,
	}
}

// ApplyConfig applies configuration values to the OpportunityContext.
func (ctx *OpportunityContext) ApplyConfig(config *PlannerConfiguration) {
	if config == nil {
		return
	}
	ctx.TransactionCostFixed = config.TransactionCostFixed
	ctx.TransactionCostPercent = config.TransactionCostPercent
	ctx.AllowSell = config.AllowSell
	ctx.AllowBuy = config.AllowBuy
}

// CalculateMinTradeAmount calculates the minimum trade amount where transaction costs are acceptable.
// Uses the same formula as rebalancing.CalculateMinTradeAmount:
//
//	minTrade = fixedCost / (maxCostRatio - transactionCostPercent)
//
// With default 1% max cost ratio, 2 EUR fixed, 0.2% variable:
//
//	minTrade = 2 / (0.01 - 0.002) = 2 / 0.008 = 250 EUR
//
// Args:
//
//	maxCostRatio: Maximum acceptable cost-to-trade ratio (default 0.01 = 1%)
//
// Returns:
//
//	Minimum trade amount in EUR
func (ctx *OpportunityContext) CalculateMinTradeAmount(maxCostRatio float64) float64 {
	if maxCostRatio <= 0 {
		maxCostRatio = 0.01 // Default 1%
	}
	denominator := maxCostRatio - ctx.TransactionCostPercent
	if denominator <= 0 {
		// If variable cost exceeds max ratio, return a high minimum
		return 1000.0
	}
	return ctx.TransactionCostFixed / denominator
}

// EvaluationContext contains all data needed to simulate and score action sequences.
// After removing universe.Security: Uses universe.Security directly (single source of truth).
type EvaluationContext struct {
	// Portfolio state (same as OpportunityContext)
	PortfolioContext       *scoringdomain.PortfolioContext `json:"portfolio_context"`
	EnrichedPositions      []EnrichedPosition              `json:"enriched_positions"` // REPLACES old Positions field
	Securities             []universe.Security             `json:"securities"`
	AvailableCashEUR       float64                         `json:"available_cash_eur"`
	TotalPortfolioValueEUR float64                         `json:"total_portfolio_value_eur"`

	// Market data (ALL KEYS ARE ISIN)
	CurrentPrices map[string]float64           `json:"current_prices"` // Key: ISIN (e.g., "US0378331005")
	StocksByISIN  map[string]universe.Security `json:"stocks_by_isin"` // Key: ISIN (primary identifier)

	// Configuration
	TransactionCostFixed   float64 `json:"transaction_cost_fixed"`
	TransactionCostPercent float64 `json:"transaction_cost_percent"`

	// Optional: Price adjustment scenarios for stochastic evaluation (Keys: ISIN)
	PriceAdjustments map[string]float64 `json:"price_adjustments,omitempty"`
}

// NewEvaluationContext creates a new EvaluationContext with defaults.
// After removing universe.Security: Uses universe.Security directly (single source of truth).
func NewEvaluationContext(
	portfolioContext *scoringdomain.PortfolioContext,
	enrichedPositions []EnrichedPosition,
	securities []universe.Security,
	availableCashEUR float64,
	totalPortfolioValueEUR float64,
	currentPrices map[string]float64,
) *EvaluationContext {
	// Build stocks by ISIN map (ONLY - no Symbol map)
	stocksByISIN := make(map[string]universe.Security, len(securities))
	for _, sec := range securities {
		if sec.ISIN != "" {
			stocksByISIN[sec.ISIN] = sec
		}
	}

	return &EvaluationContext{
		PortfolioContext:       portfolioContext,
		EnrichedPositions:      enrichedPositions,
		Securities:             securities,
		AvailableCashEUR:       availableCashEUR,
		TotalPortfolioValueEUR: totalPortfolioValueEUR,
		CurrentPrices:          currentPrices,
		StocksByISIN:           stocksByISIN,
		TransactionCostFixed:   2.0,
		TransactionCostPercent: 0.002,
	}
}

// ApplyConfig applies configuration values to the EvaluationContext.
func (ctx *EvaluationContext) ApplyConfig(config *PlannerConfiguration) {
	if config == nil {
		return
	}
	ctx.TransactionCostFixed = config.TransactionCostFixed
	ctx.TransactionCostPercent = config.TransactionCostPercent
}

// PlanningContext combines opportunity and evaluation contexts with planner-specific settings.
type PlanningContext struct {
	// Opportunity identification context
	OpportunityContext *OpportunityContext `json:"opportunity_context"`

	// Evaluation context
	EvaluationContext *EvaluationContext `json:"evaluation_context"`

	// Planner configuration
	MaxDepth                    int     `json:"max_depth"`
	MaxOpportunitiesPerCategory int     `json:"max_opportunities_per_category"`
	EnableDiverseSelection      bool    `json:"enable_diverse_selection"`
	DiversityWeight             float64 `json:"diversity_weight"`

	// Advanced settings
	EvaluationMode      string    `json:"evaluation_mode"`   // "single_objective", "multi_objective", "stochastic", "monte_carlo"
	StochasticShifts    []float64 `json:"stochastic_shifts"` // Price shift scenarios
	MonteCarloPathCount int       `json:"monte_carlo_path_count"`

	// Module enablement (can be overridden by configuration)
	EnableCombinatorial    bool `json:"enable_combinatorial"`
	EnableAdaptivePatterns bool `json:"enable_adaptive_patterns"`
}

// NewPlanningContext creates a PlanningContext with default settings.
func NewPlanningContext(
	opportunityContext *OpportunityContext,
	evaluationContext *EvaluationContext,
) *PlanningContext {
	return &PlanningContext{
		OpportunityContext:          opportunityContext,
		EvaluationContext:           evaluationContext,
		MaxDepth:                    5,
		MaxOpportunitiesPerCategory: 5,
		EnableDiverseSelection:      true,
		DiversityWeight:             0.3,
		EvaluationMode:              "single_objective",
		StochasticShifts:            []float64{-0.10, -0.05, 0.0, 0.05, 0.10},
		MonteCarloPathCount:         100,
		EnableCombinatorial:         true,
		EnableAdaptivePatterns:      true,
	}
}

// FromOpportunityContext creates a PlanningContext from an OpportunityContext.
// Automatically creates EvaluationContext from the same data.
func FromOpportunityContext(opportunityCtx *OpportunityContext) *PlanningContext {
	evaluationCtx := NewEvaluationContext(
		opportunityCtx.PortfolioContext,
		opportunityCtx.EnrichedPositions,
		opportunityCtx.Securities,
		opportunityCtx.AvailableCashEUR,
		opportunityCtx.TotalPortfolioValueEUR,
		opportunityCtx.CurrentPrices,
	)

	return NewPlanningContext(opportunityCtx, evaluationCtx)
}
