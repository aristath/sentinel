package domain

// ActionCandidate represents a potential trade action with associated metadata
// for priority-based selection and sequencing.
type ActionCandidate struct {
	Side     string   `json:"side"`      // Trade direction ("BUY" or "SELL")
	Symbol   string   `json:"symbol"`    // Security symbol
	Name     string   `json:"name"`      // Security name for display
	Quantity int      `json:"quantity"`  // Number of units to trade
	Price    float64  `json:"price"`     // Price per unit
	ValueEUR float64  `json:"value_eur"` // Total value in EUR
	Currency string   `json:"currency"`  // Trading currency
	Priority float64  `json:"priority"`  // Higher values indicate higher priority
	Reason   string   `json:"reason"`    // Human-readable explanation for this action
	Tags     []string `json:"tags"`      // Classification tags (e.g., ["windfall", "underweight_asia"])
}

// HolisticStep represents a single step in a holistic plan.
type HolisticStep struct {
	StepNumber      int      `json:"step_number"`       // Step sequence number (1-based)
	Side            string   `json:"side"`              // "BUY" or "SELL"
	Symbol          string   `json:"symbol"`            // Security symbol
	Name            string   `json:"name"`              // Security name
	Quantity        int      `json:"quantity"`          // Number of units to trade
	EstimatedPrice  float64  `json:"estimated_price"`   // Estimated price per unit
	EstimatedValue  float64  `json:"estimated_value"`   // Estimated total value in EUR
	Currency        string   `json:"currency"`          // Trading currency
	Reason          string   `json:"reason"`            // Why this action is recommended
	Narrative       string   `json:"narrative"`         // Human-readable explanation
	IsWindfall      bool     `json:"is_windfall"`       // Whether this is windfall profit-taking
	IsAveragingDown bool     `json:"is_averaging_down"` // Whether this is averaging down
	ContributesTo   []string `json:"contributes_to"`    // Goals addressed by this step
}

// HolisticPlan represents a complete holistic plan with end-state scoring.
type HolisticPlan struct {
	Steps            []HolisticStep     `json:"steps"`             // Sequence of actions to execute
	CurrentScore     float64            `json:"current_score"`     // Current portfolio score
	EndStateScore    float64            `json:"end_state_score"`   // Expected score after execution
	Improvement      float64            `json:"improvement"`       // Score improvement (end - current)
	NarrativeSummary string             `json:"narrative_summary"` // Human-readable plan summary
	ScoreBreakdown   map[string]float64 `json:"score_breakdown"`   // Detailed score components
	CashRequired     float64            `json:"cash_required"`     // Total cash needed for buys
	CashGenerated    float64            `json:"cash_generated"`    // Total cash from sells
	Feasible         bool               `json:"feasible"`          // Whether plan can be executed
}

// ActionSequence represents a sequence of actions for evaluation.
// This is used internally during planning before converting to HolisticPlan.
type ActionSequence struct {
	Actions      []ActionCandidate `json:"actions"`       // Sequence of actions
	Priority     float64           `json:"priority"`      // Aggregate priority
	Depth        int               `json:"depth"`         // Number of actions in sequence
	PatternType  string            `json:"pattern_type"`  // Pattern that generated this sequence
	SequenceHash string            `json:"sequence_hash"` // MD5 hash for deduplication
}

// EvaluationResult represents the result of evaluating an action sequence.
type EvaluationResult struct {
	SequenceHash         string             `json:"sequence_hash"`
	PortfolioHash        string             `json:"portfolio_hash,omitempty"` // Portfolio snapshot this evaluation is for
	EndScore             float64            `json:"end_score"`                // Final portfolio score
	ScoreBreakdown       map[string]float64 `json:"breakdown"`                // Detailed score components
	EndCash              float64            `json:"end_cash"`                 // Cash balance after sequence
	EndContextPositions  map[string]float64 `json:"end_context_positions"`    // Position quantities after sequence
	DiversificationScore float64            `json:"div_score"`                // Diversification component
	TotalValue           float64            `json:"total_value"`              // Total portfolio value
	Feasible             bool               `json:"feasible"`                 // Whether sequence is executable
	Error                string             `json:"error,omitempty"`          // Error message if evaluation failed
}

// OpportunityCategory represents different types of trading opportunities.
type OpportunityCategory string

const (
	OpportunityCategoryProfitTaking    OpportunityCategory = "profit_taking"
	OpportunityCategoryAveragingDown   OpportunityCategory = "averaging_down"
	OpportunityCategoryOpportunityBuys OpportunityCategory = "opportunity_buys"
	OpportunityCategoryRebalanceSells  OpportunityCategory = "rebalance_sells"
	OpportunityCategoryRebalanceBuys   OpportunityCategory = "rebalance_buys"
	OpportunityCategoryWeightBased     OpportunityCategory = "weight_based"
)

// OpportunitiesByCategory organizes action candidates by their category.
type OpportunitiesByCategory map[OpportunityCategory][]ActionCandidate
