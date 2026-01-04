package models

// TradeSide represents the direction of a trade (BUY or SELL)
type TradeSide string

const (
	TradeSideBuy  TradeSide = "BUY"
	TradeSideSell TradeSide = "SELL"
)

// IsBuy checks if this trade side is BUY
func (t TradeSide) IsBuy() bool {
	return t == TradeSideBuy
}

// IsSell checks if this trade side is SELL
func (t TradeSide) IsSell() bool {
	return t == TradeSideSell
}

// ActionCandidate represents a potential trade action with associated metadata
// for priority-based selection and sequencing.
type ActionCandidate struct {
	Side     TradeSide `json:"side"`      // Trade direction ("BUY" or "SELL")
	Symbol   string    `json:"symbol"`    // Security symbol
	Name     string    `json:"name"`      // Security name for display
	Quantity int       `json:"quantity"`  // Number of units to trade
	Price    float64   `json:"price"`     // Price per unit
	ValueEUR float64   `json:"value_eur"` // Total value in EUR
	Currency string    `json:"currency"`  // Trading currency
	Priority float64   `json:"priority"`  // Higher values indicate higher priority
	Reason   string    `json:"reason"`    // Human-readable explanation for this action
	Tags     []string  `json:"tags"`      // Classification tags (e.g., ["windfall", "underweight_asia"])
}

// Security represents a security in the investment universe
// (simplified version with only fields needed for evaluation)
type Security struct {
	Symbol   string  `json:"symbol"`   // Security symbol
	Name     string  `json:"name"`     // Security name
	Country  *string `json:"country"`  // Country (optional)
	Industry *string `json:"industry"` // Industry (optional)
	Currency string  `json:"currency"` // Trading currency
}

// Position represents a current position in a security
type Position struct {
	Symbol         string  `json:"symbol"`           // Security symbol
	Quantity       float64 `json:"quantity"`         // Number of shares
	AvgPrice       float64 `json:"avg_price"`        // Average purchase price
	Currency       string  `json:"currency"`         // Position currency
	CurrencyRate   float64 `json:"currency_rate"`    // Currency conversion rate to EUR
	CurrentPrice   float64 `json:"current_price"`    // Current market price
	MarketValueEUR float64 `json:"market_value_eur"` // Market value in EUR
}

// PortfolioContext contains portfolio state for allocation fit calculations
type PortfolioContext struct {
	// Core portfolio weights and positions
	CountryWeights  map[string]float64 `json:"country_weights"`  // group_name -> weight (-1 to +1)
	IndustryWeights map[string]float64 `json:"industry_weights"` // group_name -> weight (-1 to +1)
	Positions       map[string]float64 `json:"positions"`        // symbol -> position_value in EUR
	TotalValue      float64            `json:"total_value"`      // Total portfolio value in EUR

	// Additional data for portfolio scoring
	SecurityCountries  map[string]string  `json:"security_countries,omitempty"`  // symbol -> country (individual)
	SecurityIndustries map[string]string  `json:"security_industries,omitempty"` // symbol -> industry (individual)
	SecurityScores     map[string]float64 `json:"security_scores,omitempty"`     // symbol -> quality_score
	SecurityDividends  map[string]float64 `json:"security_dividends,omitempty"`  // symbol -> dividend_yield

	// Group mappings (for mapping individual countries/industries to groups)
	CountryToGroup  map[string]string `json:"country_to_group,omitempty"`  // country -> group_name
	IndustryToGroup map[string]string `json:"industry_to_group,omitempty"` // industry -> group_name

	// Cost basis data for averaging down
	PositionAvgPrices map[string]float64 `json:"position_avg_prices,omitempty"` // symbol -> avg_purchase_price
	CurrentPrices     map[string]float64 `json:"current_prices,omitempty"`      // symbol -> current_market_price
}

// EvaluationContext contains all data needed to simulate and score action sequences
type EvaluationContext struct {
	// Portfolio state
	PortfolioContext       PortfolioContext `json:"portfolio_context"`
	Positions              []Position       `json:"positions"`
	Securities             []Security       `json:"securities"`
	AvailableCashEUR       float64          `json:"available_cash_eur"`
	TotalPortfolioValueEUR float64          `json:"total_portfolio_value_eur"`

	// Market data
	CurrentPrices  map[string]float64  `json:"current_prices"`   // symbol -> current price
	StocksBySymbol map[string]Security `json:"stocks_by_symbol"` // symbol -> Security (computed)

	// Configuration
	TransactionCostFixed   float64 `json:"transaction_cost_fixed"`   // Fixed transaction cost (EUR)
	TransactionCostPercent float64 `json:"transaction_cost_percent"` // Percentage transaction cost (0.002 = 0.2%)
	CostPenaltyFactor      float64 `json:"cost_penalty_factor"`      // Penalty factor for transaction costs (0.0 = no penalty, 0.1 = default)

	// Optional: Price adjustment scenarios for stochastic evaluation
	PriceAdjustments map[string]float64 `json:"price_adjustments,omitempty"` // symbol -> multiplier (e.g., 1.05 for +5%)
}

// SequenceEvaluationResult represents the result of evaluating a single sequence
type SequenceEvaluationResult struct {
	Sequence         []ActionCandidate `json:"sequence"`          // The sequence that was evaluated
	Score            float64           `json:"score"`             // Total score
	EndCashEUR       float64           `json:"end_cash_eur"`      // Final cash after sequence
	EndPortfolio     PortfolioContext  `json:"end_portfolio"`     // Final portfolio state
	TransactionCosts float64           `json:"transaction_costs"` // Total transaction costs incurred
	Feasible         bool              `json:"feasible"`          // Whether the sequence was feasible
}

// BatchEvaluationRequest represents a request to evaluate multiple sequences
type BatchEvaluationRequest struct {
	Sequences         [][]ActionCandidate `json:"sequences"`          // List of sequences to evaluate
	EvaluationContext EvaluationContext   `json:"evaluation_context"` // Context for evaluation
}

// BatchEvaluationResponse represents the response from batch evaluation
type BatchEvaluationResponse struct {
	Results []SequenceEvaluationResult `json:"results"` // Results for each sequence
	Errors  []string                   `json:"errors"`  // Any errors encountered (per-sequence)
}

// HealthResponse represents the health check response
type HealthResponse struct {
	Status  string `json:"status"`  // "healthy" or "unhealthy"
	Version string `json:"version"` // Service version
}

// MonteCarloRequest represents a Monte Carlo simulation request
type MonteCarloRequest struct {
	Sequence           []ActionCandidate  `json:"sequence"`            // Sequence to evaluate
	EvaluationContext  EvaluationContext  `json:"evaluation_context"`  // Context for evaluation
	Paths              int                `json:"paths"`               // Number of Monte Carlo paths (100-500)
	SymbolVolatilities map[string]float64 `json:"symbol_volatilities"` // Annual volatility per symbol (e.g., 0.25 for 25%)
}

// MonteCarloResult represents the result of Monte Carlo simulation
type MonteCarloResult struct {
	PathsEvaluated int     `json:"paths_evaluated"` // Number of paths evaluated
	AvgScore       float64 `json:"avg_score"`       // Average score across paths
	WorstScore     float64 `json:"worst_score"`     // Minimum score (worst case)
	BestScore      float64 `json:"best_score"`      // Maximum score (best case)
	P10Score       float64 `json:"p10_score"`       // 10th percentile score
	P90Score       float64 `json:"p90_score"`       // 90th percentile score
	FinalScore     float64 `json:"final_score"`     // Conservative score: worst*0.4 + p10*0.3 + avg*0.3
}

// StochasticRequest represents a stochastic price scenario request
type StochasticRequest struct {
	Sequence          []ActionCandidate  `json:"sequence"`           // Sequence to evaluate
	EvaluationContext EvaluationContext  `json:"evaluation_context"` // Context for evaluation
	Shifts            []float64          `json:"shifts"`             // Price shift scenarios (e.g., [-0.10, -0.05, 0.0, 0.05, 0.10])
	Weights           map[string]float64 `json:"weights"`            // Weights per scenario (e.g., {"0.0": 0.40, "-0.10": 0.15})
}

// StochasticResult represents the result of stochastic scenario evaluation
type StochasticResult struct {
	ScenariosEvaluated int                `json:"scenarios_evaluated"` // Number of scenarios evaluated
	BaseScore          float64            `json:"base_score"`          // Score for 0% scenario
	WorstCase          float64            `json:"worst_case"`          // Score for worst scenario (-10%)
	BestCase           float64            `json:"best_case"`           // Score for best scenario (+10%)
	WeightedScore      float64            `json:"weighted_score"`      // Weighted average of all scenarios
	ScenarioScores     map[string]float64 `json:"scenario_scores"`     // Scores for each scenario (shift -> score)
}

// BatchSimulationRequest represents a request to simulate multiple sequences
type BatchSimulationRequest struct {
	Sequences         [][]ActionCandidate `json:"sequences"`          // List of sequences to simulate
	EvaluationContext EvaluationContext   `json:"evaluation_context"` // Context for simulation
}

// SimulationResult represents the result of simulating a single sequence
type SimulationResult struct {
	Sequence     []ActionCandidate `json:"sequence"`      // The sequence that was simulated
	EndPortfolio PortfolioContext  `json:"end_portfolio"` // Final portfolio state
	EndCashEUR   float64           `json:"end_cash_eur"`  // Final cash after sequence
	Feasible     bool              `json:"feasible"`      // Whether the sequence was feasible
}

// BatchSimulationResponse represents the response from batch simulation
type BatchSimulationResponse struct {
	Results []SimulationResult `json:"results"` // Results for each sequence
}
