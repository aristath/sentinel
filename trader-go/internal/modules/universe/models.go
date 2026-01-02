package universe

import "time"

// Security represents a security in the investment universe
// Faithful translation from Python: app/domain/models.py -> class Security
type Security struct {
	Symbol             string  `json:"symbol"`
	Name               string  `json:"name"`
	ProductType        string  `json:"product_type"` // EQUITY, ETF, ETC, MUTUALFUND, UNKNOWN
	Country            string  `json:"country,omitempty"`
	FullExchangeName   string  `json:"fullExchangeName,omitempty"`
	YahooSymbol        string  `json:"yahoo_symbol,omitempty"`
	ISIN               string  `json:"isin,omitempty"`
	Industry           string  `json:"industry,omitempty"`
	PriorityMultiplier float64 `json:"priority_multiplier"`
	MinLot             int     `json:"min_lot"`
	Active             bool    `json:"active"`
	AllowBuy           bool    `json:"allow_buy"`
	AllowSell          bool    `json:"allow_sell"`
	Currency           string  `json:"currency,omitempty"`
	LastSynced         string  `json:"last_synced,omitempty"`          // ISO datetime
	MinPortfolioTarget float64 `json:"min_portfolio_target,omitempty"` // 0-20%
	MaxPortfolioTarget float64 `json:"max_portfolio_target,omitempty"` // 0-30%
	BucketID           string  `json:"bucket_id"`                      // core or satellite
}

// SecurityScore represents calculated scores for a security
// Faithful translation from Python: app/domain/models.py -> class SecurityScore
type SecurityScore struct {
	Symbol string `json:"symbol"`
	ISIN   string `json:"isin,omitempty"`

	// Primary component scores (0-1 range)
	QualityScore       float64 `json:"quality_score,omitempty"`
	OpportunityScore   float64 `json:"opportunity_score,omitempty"`
	AnalystScore       float64 `json:"analyst_score,omitempty"`
	AllocationFitScore float64 `json:"allocation_fit_score,omitempty"`

	// Quality breakdown
	CAGRScore              float64 `json:"cagr_score,omitempty"`
	ConsistencyScore       float64 `json:"consistency_score,omitempty"`
	FinancialStrengthScore float64 `json:"financial_strength_score,omitempty"`
	SharpeScore            float64 `json:"sharpe_score,omitempty"`
	DrawdownScore          float64 `json:"drawdown_score,omitempty"`
	DividendBonus          float64 `json:"dividend_bonus,omitempty"`

	// Technical indicators
	RSI             float64 `json:"rsi,omitempty"`
	EMA200          float64 `json:"ema_200,omitempty"`
	Below52wHighPct float64 `json:"below_52w_high_pct,omitempty"`

	// Combined scores
	TotalScore       float64 `json:"total_score,omitempty"`
	SellScore        float64 `json:"sell_score,omitempty"`
	TechnicalScore   float64 `json:"technical_score,omitempty"`
	FundamentalScore float64 `json:"fundamental_score,omitempty"`

	// Metadata
	HistoryYears float64    `json:"history_years,omitempty"`
	Volatility   float64    `json:"volatility,omitempty"`
	CalculatedAt *time.Time `json:"calculated_at,omitempty"`
}

// SecurityWithScore combines security and score data
// Used for GET /api/securities endpoint response
type SecurityWithScore struct {
	// Security fields
	Symbol             string  `json:"symbol"`
	Name               string  `json:"name"`
	ISIN               string  `json:"isin,omitempty"`
	YahooSymbol        string  `json:"yahoo_symbol,omitempty"`
	ProductType        string  `json:"product_type,omitempty"`
	Country            string  `json:"country,omitempty"`
	FullExchangeName   string  `json:"fullExchangeName,omitempty"`
	Industry           string  `json:"industry,omitempty"`
	PriorityMultiplier float64 `json:"priority_multiplier"`
	MinLot             int     `json:"min_lot"`
	Active             bool    `json:"active"`
	AllowBuy           bool    `json:"allow_buy"`
	AllowSell          bool    `json:"allow_sell"`
	Currency           string  `json:"currency,omitempty"`
	LastSynced         string  `json:"last_synced,omitempty"`
	MinPortfolioTarget float64 `json:"min_portfolio_target,omitempty"`
	MaxPortfolioTarget float64 `json:"max_portfolio_target,omitempty"`
	BucketID           string  `json:"bucket_id"`

	// Score fields (can be nil if no score calculated)
	QualityScore       *float64 `json:"quality_score,omitempty"`
	OpportunityScore   *float64 `json:"opportunity_score,omitempty"`
	AnalystScore       *float64 `json:"analyst_score,omitempty"`
	AllocationFitScore *float64 `json:"allocation_fit_score,omitempty"`
	TotalScore         *float64 `json:"total_score,omitempty"`
	CAGRScore          *float64 `json:"cagr_score,omitempty"`
	ConsistencyScore   *float64 `json:"consistency_score,omitempty"`
	HistoryYears       *float64 `json:"history_years,omitempty"`
	Volatility         *float64 `json:"volatility,omitempty"`
	TechnicalScore     *float64 `json:"technical_score,omitempty"`
	FundamentalScore   *float64 `json:"fundamental_score,omitempty"`

	// Position data (if security is currently held)
	PositionValue    *float64 `json:"position_value,omitempty"`
	PositionQuantity *float64 `json:"position_quantity,omitempty"`

	// Priority score (calculated by PriorityCalculator)
	PriorityScore *float64 `json:"priority_score,omitempty"`
}
