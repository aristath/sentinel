package universe

import "time"

// Tag represents a tag definition with ID and human-readable name
type Tag struct {
	Id   string `json:"id"`   // Code-friendly ID (e.g., 'value-opportunity')
	Name string `json:"name"` // Human-readable name (e.g., 'Value Opportunity')
}

// Security represents a security in the investment universe
// Faithful translation from Python: app/domain/models.py -> class Security
// After migration 030: ISIN is PRIMARY KEY and is required for all database operations
type Security struct {
	Currency           string   `json:"currency,omitempty"`
	Name               string   `json:"name"`
	ProductType        string   `json:"product_type"`
	Country            string   `json:"country,omitempty"`
	FullExchangeName   string   `json:"fullExchangeName,omitempty"`
	YahooSymbol        string   `json:"yahoo_symbol,omitempty"`
	ISIN               string   `json:"isin,omitempty"` // Required: PRIMARY KEY after migration 030
	Industry           string   `json:"industry,omitempty"`
	Symbol             string   `json:"symbol"`
	LastSynced         string   `json:"last_synced,omitempty"`
	PriorityMultiplier float64  `json:"priority_multiplier"`
	MinPortfolioTarget float64  `json:"min_portfolio_target,omitempty"`
	MaxPortfolioTarget float64  `json:"max_portfolio_target,omitempty"`
	MinLot             int      `json:"min_lot"`
	AllowSell          bool     `json:"allow_sell"`
	AllowBuy           bool     `json:"allow_buy"`
	Active             bool     `json:"active"`
	Tags               []string `json:"tags,omitempty"`
}

// SecurityScore represents calculated scores for a security
// Faithful translation from Python: app/domain/models.py -> class SecurityScore
// After migration 030: ISIN is PRIMARY KEY and is required for all database operations
type SecurityScore struct {
	CalculatedAt           *time.Time `json:"calculated_at,omitempty"`
	Symbol                 string     `json:"symbol"`         // Kept for backward compatibility, not used as key
	ISIN                   string     `json:"isin,omitempty"` // Required: PRIMARY KEY after migration 030
	DrawdownScore          float64    `json:"drawdown_score,omitempty"`
	RSI                    float64    `json:"rsi,omitempty"`
	AllocationFitScore     float64    `json:"allocation_fit_score,omitempty"`
	CAGRScore              float64    `json:"cagr_score,omitempty"`
	ConsistencyScore       float64    `json:"consistency_score,omitempty"`
	FinancialStrengthScore float64    `json:"financial_strength_score,omitempty"`
	SharpeScore            float64    `json:"sharpe_score,omitempty"`
	OpportunityScore       float64    `json:"opportunity_score,omitempty"`
	DividendBonus          float64    `json:"dividend_bonus,omitempty"`
	AnalystScore           float64    `json:"analyst_score,omitempty"`
	EMA200                 float64    `json:"ema_200,omitempty"`
	Below52wHighPct        float64    `json:"below_52w_high_pct,omitempty"`
	TotalScore             float64    `json:"total_score,omitempty"`
	SellScore              float64    `json:"sell_score,omitempty"`
	TechnicalScore         float64    `json:"technical_score,omitempty"`
	FundamentalScore       float64    `json:"fundamental_score,omitempty"`
	HistoryYears           float64    `json:"history_years,omitempty"`
	Volatility             float64    `json:"volatility,omitempty"`
	QualityScore           float64    `json:"quality_score,omitempty"`
}

// SecurityWithScore combines security and score data
// Used for GET /api/securities endpoint response
type SecurityWithScore struct {
	QualityScore       *float64 `json:"quality_score,omitempty"`
	OpportunityScore   *float64 `json:"opportunity_score,omitempty"`
	ConsistencyScore   *float64 `json:"consistency_score,omitempty"`
	CAGRScore          *float64 `json:"cagr_score,omitempty"`
	TotalScore         *float64 `json:"total_score,omitempty"`
	AnalystScore       *float64 `json:"analyst_score,omitempty"`
	HistoryYears       *float64 `json:"history_years,omitempty"`
	Volatility         *float64 `json:"volatility,omitempty"`
	TechnicalScore     *float64 `json:"technical_score,omitempty"`
	PriorityScore      *float64 `json:"priority_score,omitempty"`
	PositionQuantity   *float64 `json:"position_quantity,omitempty"`
	PositionValue      *float64 `json:"position_value,omitempty"`
	CurrentPrice       *float64 `json:"current_price,omitempty"`
	FundamentalScore   *float64 `json:"fundamental_score,omitempty"`
	AllocationFitScore *float64 `json:"allocation_fit_score,omitempty"`
	Name               string   `json:"name"`
	Symbol             string   `json:"symbol"`
	Industry           string   `json:"industry,omitempty"`
	FullExchangeName   string   `json:"fullExchangeName,omitempty"`
	LastSynced         string   `json:"last_synced,omitempty"`
	Country            string   `json:"country,omitempty"`
	Currency           string   `json:"currency,omitempty"`
	ProductType        string   `json:"product_type,omitempty"`
	YahooSymbol        string   `json:"yahoo_symbol,omitempty"`
	ISIN               string   `json:"isin,omitempty"`
	PriorityMultiplier float64  `json:"priority_multiplier"`
	MaxPortfolioTarget float64  `json:"max_portfolio_target,omitempty"`
	MinPortfolioTarget float64  `json:"min_portfolio_target,omitempty"`
	MinLot             int      `json:"min_lot"`
	AllowSell          bool     `json:"allow_sell"`
	AllowBuy           bool     `json:"allow_buy"`
	Active             bool     `json:"active"`
	Tags               []string `json:"tags,omitempty"`
}
