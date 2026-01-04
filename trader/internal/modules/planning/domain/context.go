package domain

import (
	"github.com/aristath/arduino-trader/internal/domain"
	scoringdomain "github.com/aristath/arduino-trader/internal/modules/scoring/domain"
)

// OpportunityContext contains all data needed by opportunity calculators
// to identify trading opportunities (buys, sells, rebalancing, etc.).
type OpportunityContext struct {
	// Portfolio state
	PortfolioContext       *scoringdomain.PortfolioContext `json:"portfolio_context"`
	Positions              []domain.Position               `json:"positions"`
	Securities             []domain.Security               `json:"securities"`
	AvailableCashEUR       float64                         `json:"available_cash_eur"`
	TotalPortfolioValueEUR float64                         `json:"total_portfolio_value_eur"`

	// Market data
	CurrentPrices  map[string]float64         `json:"current_prices"`
	StocksBySymbol map[string]domain.Security `json:"stocks_by_symbol"`

	// Optional enrichment data
	SecurityScores     map[string]float64 `json:"security_scores,omitempty"`     // Final scores by symbol
	CountryAllocations map[string]float64 `json:"country_allocations,omitempty"` // Current allocations
	CountryToGroup     map[string]string  `json:"country_to_group,omitempty"`    // Country groupings
	CountryWeights     map[string]float64 `json:"country_weights,omitempty"`     // Target weights by country
	TargetWeights      map[string]float64 `json:"target_weights,omitempty"`      // Optimizer target weights

	// Constraints
	IneligibleSymbols map[string]bool `json:"ineligible_symbols"` // Can't sell these
	RecentlySold      map[string]bool `json:"recently_sold"`      // Recently sold (cooldown)
	RecentlyBought    map[string]bool `json:"recently_bought"`    // Recently bought

	// Configuration
	TransactionCostFixed   float64 `json:"transaction_cost_fixed"`
	TransactionCostPercent float64 `json:"transaction_cost_percent"`
	AllowSell              bool    `json:"allow_sell"`
	AllowBuy               bool    `json:"allow_buy"`
}

// NewOpportunityContext creates a new OpportunityContext with defaults.
func NewOpportunityContext(
	portfolioContext *scoringdomain.PortfolioContext,
	positions []domain.Position,
	securities []domain.Security,
	availableCashEUR float64,
	totalPortfolioValueEUR float64,
	currentPrices map[string]float64,
) *OpportunityContext {
	// Build stocks by symbol map
	stocksBySymbol := make(map[string]domain.Security, len(securities))
	for _, sec := range securities {
		stocksBySymbol[sec.Symbol] = sec
	}

	return &OpportunityContext{
		PortfolioContext:       portfolioContext,
		Positions:              positions,
		Securities:             securities,
		AvailableCashEUR:       availableCashEUR,
		TotalPortfolioValueEUR: totalPortfolioValueEUR,
		CurrentPrices:          currentPrices,
		StocksBySymbol:         stocksBySymbol,
		IneligibleSymbols:      make(map[string]bool),
		RecentlySold:           make(map[string]bool),
		RecentlyBought:         make(map[string]bool),
		TransactionCostFixed:   2.0,
		TransactionCostPercent: 0.002,
		AllowSell:              true,
		AllowBuy:               true,
	}
}

// EvaluationContext contains all data needed to simulate and score action sequences.
type EvaluationContext struct {
	// Portfolio state (same as OpportunityContext)
	PortfolioContext       *scoringdomain.PortfolioContext `json:"portfolio_context"`
	Positions              []domain.Position               `json:"positions"`
	Securities             []domain.Security               `json:"securities"`
	AvailableCashEUR       float64                         `json:"available_cash_eur"`
	TotalPortfolioValueEUR float64                         `json:"total_portfolio_value_eur"`

	// Market data
	CurrentPrices  map[string]float64         `json:"current_prices"`
	StocksBySymbol map[string]domain.Security `json:"stocks_by_symbol"`

	// Configuration
	TransactionCostFixed   float64 `json:"transaction_cost_fixed"`
	TransactionCostPercent float64 `json:"transaction_cost_percent"`

	// Optional: Price adjustment scenarios for stochastic evaluation
	PriceAdjustments map[string]float64 `json:"price_adjustments,omitempty"`
}

// NewEvaluationContext creates a new EvaluationContext with defaults.
func NewEvaluationContext(
	portfolioContext *scoringdomain.PortfolioContext,
	positions []domain.Position,
	securities []domain.Security,
	availableCashEUR float64,
	totalPortfolioValueEUR float64,
	currentPrices map[string]float64,
) *EvaluationContext {
	// Build stocks by symbol map
	stocksBySymbol := make(map[string]domain.Security, len(securities))
	for _, sec := range securities {
		stocksBySymbol[sec.Symbol] = sec
	}

	return &EvaluationContext{
		PortfolioContext:       portfolioContext,
		Positions:              positions,
		Securities:             securities,
		AvailableCashEUR:       availableCashEUR,
		TotalPortfolioValueEUR: totalPortfolioValueEUR,
		CurrentPrices:          currentPrices,
		StocksBySymbol:         stocksBySymbol,
		TransactionCostFixed:   2.0,
		TransactionCostPercent: 0.002,
	}
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
	PriorityThreshold           float64 `json:"priority_threshold"`
	EnableDiverseSelection      bool    `json:"enable_diverse_selection"`
	DiversityWeight             float64 `json:"diversity_weight"`

	// Advanced settings
	BeamWidth           int       `json:"beam_width"`        // For beam search in multi-objective mode
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
		PriorityThreshold:           0.3,
		EnableDiverseSelection:      true,
		DiversityWeight:             0.3,
		BeamWidth:                   10,
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
		opportunityCtx.Positions,
		opportunityCtx.Securities,
		opportunityCtx.AvailableCashEUR,
		opportunityCtx.TotalPortfolioValueEUR,
		opportunityCtx.CurrentPrices,
	)

	return NewPlanningContext(opportunityCtx, evaluationCtx)
}
