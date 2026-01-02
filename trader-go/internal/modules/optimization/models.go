package optimization

import "time"

// Main result types

// Result contains the complete optimization result.
type Result struct {
	Timestamp              time.Time
	TargetReturn           float64
	AchievedExpectedReturn *float64
	BlendUsed              float64
	FallbackUsed           *string // "min_volatility", "efficient_risk", "max_sharpe", "hrp"
	TargetWeights          map[string]float64
	WeightChanges          []WeightChange
	HighCorrelations       []CorrelationPair
	ConstraintsSummary     ConstraintsSummary
	Success                bool
	Error                  *string
}

// WeightChange represents a change in portfolio weight for a security.
type WeightChange struct {
	Symbol        string
	CurrentWeight float64
	TargetWeight  float64
	Change        float64
	Reason        *string
}

// CorrelationPair represents a pair of highly correlated securities.
type CorrelationPair struct {
	Symbol1     string
	Symbol2     string
	Correlation float64
}

// ConstraintsSummary summarizes the constraints used in optimization.
type ConstraintsSummary struct {
	TotalSecurities      int
	SecuritiesWithBounds int
	CountryConstraints   int
	IndustryConstraints  int
	TotalMinWeight       float64
	TotalMaxWeight       float64
}

// Input types

// PortfolioState represents the current state of the portfolio for optimization.
type PortfolioState struct {
	Securities      []Security
	Positions       map[string]Position
	PortfolioValue  float64
	CurrentPrices   map[string]float64
	CashBalance     float64
	CountryTargets  map[string]float64
	IndustryTargets map[string]float64
	DividendBonuses map[string]float64
}

// Security represents a security in the portfolio (placeholder - actual definition elsewhere).
type Security struct {
	Symbol             string
	Country            string
	Industry           string
	MinPortfolioTarget float64
	MaxPortfolioTarget float64
	AllowBuy           bool
	AllowSell          bool
	MinLot             float64
	PriorityMultiplier float64
	TargetPriceEUR     float64
}

// Position represents a position in the portfolio (placeholder - actual definition elsewhere).
type Position struct {
	Symbol   string
	Quantity float64
	ValueEUR float64
}

// Settings

// Settings contains optimizer configuration.
type Settings struct {
	Blend              float64 // 0.0 = pure MV, 1.0 = pure HRP
	TargetReturn       float64
	MinCashReserve     float64
	MinTradeAmount     float64
	TransactionCostPct float64
	MaxConcentration   float64
}

// Constraints

// Constraints contains all constraints for optimization.
type Constraints struct {
	WeightBounds      [][2]float64       // Per-security bounds [min, max]
	SectorConstraints []SectorConstraint // Country/industry constraints
	Symbols           []string           // Ordered symbol list
}
