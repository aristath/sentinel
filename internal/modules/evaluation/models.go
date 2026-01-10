package evaluation

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
	Side     TradeSide `json:"side"`
	ISIN     string    `json:"isin"`      // International Securities Identification Number (PRIMARY identifier)
	Symbol   string    `json:"symbol"`    // Security symbol (BOUNDARY identifier for APIs/UI)
	Name     string    `json:"name"`
	Currency string    `json:"currency"`
	Reason   string    `json:"reason"`
	Tags     []string  `json:"tags"`
	Quantity int       `json:"quantity"`
	Price    float64   `json:"price"`
	ValueEUR float64   `json:"value_eur"`
	Priority float64   `json:"priority"`
}

// Security represents a security in the investment universe
// (simplified version with only fields needed for evaluation)
type Security struct {
	ISIN     string  `json:"isin"`     // International Securities Identification Number (PRIMARY identifier)
	Symbol   string  `json:"symbol"`   // Security symbol (BOUNDARY identifier for APIs/UI)
	Name     string  `json:"name"`     // Security name
	Country  *string `json:"country"`  // Country (optional)
	Industry *string `json:"industry"` // Industry (optional)
	Currency string  `json:"currency"` // Trading currency
}

// Position represents a current position in a security
type Position struct {
	Symbol         string  `json:"symbol"`
	Currency       string  `json:"currency"`
	Quantity       float64 `json:"quantity"`
	AvgPrice       float64 `json:"avg_price"`
	CurrencyRate   float64 `json:"currency_rate"`
	CurrentPrice   float64 `json:"current_price"`
	MarketValueEUR float64 `json:"market_value_eur"`
}

// PortfolioContext contains portfolio state for allocation fit calculations
type PortfolioContext struct {
	CountryWeights         map[string]float64 `json:"country_weights"`
	IndustryWeights        map[string]float64 `json:"industry_weights"`
	Positions              map[string]float64 `json:"positions"`
	SecurityCountries      map[string]string  `json:"security_countries,omitempty"`
	SecurityIndustries     map[string]string  `json:"security_industries,omitempty"`
	SecurityScores         map[string]float64 `json:"security_scores,omitempty"`
	SecurityDividends      map[string]float64 `json:"security_dividends,omitempty"`
	CountryToGroup         map[string]string  `json:"country_to_group,omitempty"`
	IndustryToGroup        map[string]string  `json:"industry_to_group,omitempty"`
	PositionAvgPrices      map[string]float64 `json:"position_avg_prices,omitempty"`
	CurrentPrices          map[string]float64 `json:"current_prices,omitempty"`
	OptimizerTargetWeights map[string]float64 `json:"optimizer_target_weights,omitempty"` // Optimizer target allocations
	TotalValue             float64            `json:"total_value"`
}

// EvaluationContext contains all data needed to simulate and score action sequences
type EvaluationContext struct {
	PortfolioContext       PortfolioContext    `json:"portfolio_context"`
	CurrentPrices          map[string]float64  `json:"current_prices"`
	StocksBySymbol         map[string]Security `json:"stocks_by_symbol"`
	PriceAdjustments       map[string]float64  `json:"price_adjustments,omitempty"`
	Positions              []Position          `json:"positions"`
	Securities             []Security          `json:"securities"`
	AvailableCashEUR       float64             `json:"available_cash_eur"`
	TotalPortfolioValueEUR float64             `json:"total_portfolio_value_eur"`
	TransactionCostFixed   float64             `json:"transaction_cost_fixed"`
	TransactionCostPercent float64             `json:"transaction_cost_percent"`
	CostPenaltyFactor      float64             `json:"cost_penalty_factor"`
}

// SequenceEvaluationResult represents the result of evaluating a single sequence
type SequenceEvaluationResult struct {
	EndPortfolio     PortfolioContext  `json:"end_portfolio"`
	Sequence         []ActionCandidate `json:"sequence"`
	Score            float64           `json:"score"`
	EndCashEUR       float64           `json:"end_cash_eur"`
	TransactionCosts float64           `json:"transaction_costs"`
	Feasible         bool              `json:"feasible"`
}

// BatchEvaluationRequest represents a request to evaluate multiple sequences
type BatchEvaluationRequest struct {
	Sequences         [][]ActionCandidate `json:"sequences"`
	EvaluationContext EvaluationContext   `json:"evaluation_context"`
}

// BatchEvaluationResponse represents the response from batch evaluation
type BatchEvaluationResponse struct {
	Results []SequenceEvaluationResult `json:"results"` // Results for each sequence
	Errors  []string                   `json:"errors"`  // Any errors encountered (per-sequence)
}

// MonteCarloRequest represents a Monte Carlo simulation request
type MonteCarloRequest struct {
	SymbolVolatilities map[string]float64 `json:"symbol_volatilities"`
	Sequence           []ActionCandidate  `json:"sequence"`
	EvaluationContext  EvaluationContext  `json:"evaluation_context"`
	Paths              int                `json:"paths"`
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
	Weights           map[string]float64 `json:"weights"`
	Sequence          []ActionCandidate  `json:"sequence"`
	Shifts            []float64          `json:"shifts"`
	EvaluationContext EvaluationContext  `json:"evaluation_context"`
}

// StochasticResult represents the result of stochastic scenario evaluation
type StochasticResult struct {
	ScenarioScores     map[string]float64 `json:"scenario_scores"`
	ScenariosEvaluated int                `json:"scenarios_evaluated"`
	BaseScore          float64            `json:"base_score"`
	WorstCase          float64            `json:"worst_case"`
	BestCase           float64            `json:"best_case"`
	WeightedScore      float64            `json:"weighted_score"`
}

// BatchSimulationRequest represents a request to simulate multiple sequences
type BatchSimulationRequest struct {
	Sequences         [][]ActionCandidate `json:"sequences"`
	EvaluationContext EvaluationContext   `json:"evaluation_context"`
}

// SimulationResult represents the result of simulating a single sequence
type SimulationResult struct {
	EndPortfolio PortfolioContext  `json:"end_portfolio"`
	Sequence     []ActionCandidate `json:"sequence"`
	EndCashEUR   float64           `json:"end_cash_eur"`
	Feasible     bool              `json:"feasible"`
}

// BatchSimulationResponse represents the response from batch simulation
type BatchSimulationResponse struct {
	Results []SimulationResult `json:"results"` // Results for each sequence
}
