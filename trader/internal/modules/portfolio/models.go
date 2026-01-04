package portfolio

// Position represents current position in a security
// Faithful translation from Python: app/modules/portfolio/domain/models.py
type Position struct {
	LastUpdated      string  `json:"last_updated,omitempty"`
	LastSoldAt       string  `json:"last_sold_at,omitempty"`
	ISIN             string  `json:"isin,omitempty"`
	Currency         string  `json:"currency"`
	FirstBoughtAt    string  `json:"first_bought_at,omitempty"`
	Symbol           string  `json:"symbol"`
	CurrentPrice     float64 `json:"current_price,omitempty"`
	CostBasisEUR     float64 `json:"cost_basis_eur,omitempty"`
	UnrealizedPnL    float64 `json:"unrealized_pnl,omitempty"`
	UnrealizedPnLPct float64 `json:"unrealized_pnl_pct,omitempty"`
	MarketValueEUR   float64 `json:"market_value_eur,omitempty"`
	CurrencyRate     float64 `json:"currency_rate"`
	AvgPrice         float64 `json:"avg_price"`
	Quantity         float64 `json:"quantity"`
}

// PortfolioSnapshot represents daily portfolio summary
// Faithful translation from Python: app/modules/portfolio/domain/models.py
type PortfolioSnapshot struct {
	Date           string  `json:"date"` // YYYY-MM-DD format
	TotalValue     float64 `json:"total_value"`
	CashBalance    float64 `json:"cash_balance"`
	InvestedValue  float64 `json:"invested_value,omitempty"`
	UnrealizedPnL  float64 `json:"unrealized_pnl,omitempty"`
	GeoEUPct       float64 `json:"geo_eu_pct,omitempty"`
	GeoAsiaPct     float64 `json:"geo_asia_pct,omitempty"`
	GeoUSPct       float64 `json:"geo_us_pct,omitempty"`
	PositionCount  int     `json:"position_count,omitempty"`
	AnnualTurnover float64 `json:"annual_turnover,omitempty"`
}

// AllocationStatus represents current allocation vs target
// Faithful translation from Python: app/domain/models.py
type AllocationStatus struct {
	Category     string  `json:"category"`      // "country" or "industry"
	Name         string  `json:"name"`          // Country name or Industry name
	TargetPct    float64 `json:"target_pct"`    // Target allocation percentage
	CurrentPct   float64 `json:"current_pct"`   // Current allocation percentage
	CurrentValue float64 `json:"current_value"` // Current value in EUR
	Deviation    float64 `json:"deviation"`     // current - target (negative = underweight)
}

// PortfolioSummary represents complete portfolio allocation summary
// Faithful translation from Python: app/domain/models.py
type PortfolioSummary struct {
	CountryAllocations  []AllocationStatus `json:"country_allocations"`
	IndustryAllocations []AllocationStatus `json:"industry_allocations"`
	TotalValue          float64            `json:"total_value"`
	CashBalance         float64            `json:"cash_balance"`
}

// PositionWithSecurity represents position with security information
// Used by get_with_security_info() - combines Position + Security data
type PositionWithSecurity struct {
	Country          string  `db:"country"`
	StockName        string  `db:"name"`
	Symbol           string  `db:"symbol"`
	Currency         string  `db:"currency"`
	FullExchangeName string  `db:"fullExchangeName"`
	Industry         string  `db:"industry"`
	LastUpdated      string  `db:"last_updated"`
	CurrentPrice     float64 `db:"current_price"`
	MarketValueEUR   float64 `db:"market_value_eur"`
	CurrencyRate     float64 `db:"currency_rate"`
	AvgPrice         float64 `db:"avg_price"`
	Quantity         float64 `db:"quantity"`
	AllowSell        bool    `db:"allow_sell"`
}

// Analytics Response Models
// Faithful translation from Python: app/api/models.py

// DailyReturn represents a daily return data point
type DailyReturn struct {
	Date   string  `json:"date"`
	Return float64 `json:"return"`
}

// MonthlyReturn represents a monthly return data point
type MonthlyReturn struct {
	Month  string  `json:"month"` // YYYY-MM format
	Return float64 `json:"return"`
}

// ReturnsData holds all return metrics
type ReturnsData struct {
	Daily   []DailyReturn   `json:"daily"`
	Monthly []MonthlyReturn `json:"monthly"`
	Annual  float64         `json:"annual"`
}

// RiskMetrics holds portfolio risk measurements
type RiskMetrics struct {
	SharpeRatio  float64 `json:"sharpe_ratio"`
	SortinoRatio float64 `json:"sortino_ratio"`
	CalmarRatio  float64 `json:"calmar_ratio"`
	Volatility   float64 `json:"volatility"`
	MaxDrawdown  float64 `json:"max_drawdown"`
}

// RiskParameters holds configurable parameters for risk metric calculations
// Allows each agent (main, satellites) to have different risk assessment criteria
type RiskParameters struct {
	RiskFreeRate float64 `json:"risk_free_rate"` // Annual risk-free rate (e.g., 0.035 for 3.5%)
	SortinoMAR   float64 `json:"sortino_mar"`    // Minimum Acceptable Return for Sortino (e.g., 0.05 for 5%)
}

// NewDefaultRiskParameters returns sensible defaults for portfolio risk calculations
// Suitable for main/core portfolio (retirement-focused)
func NewDefaultRiskParameters() RiskParameters {
	return RiskParameters{
		RiskFreeRate: 0.035, // 3.5% annual risk-free rate
		SortinoMAR:   0.05,  // 5% minimum acceptable return (inflation + modest real return)
	}
}

// AttributionData holds performance attribution by category
type AttributionData struct {
	Country  map[string]float64 `json:"country"`
	Industry map[string]float64 `json:"industry"`
}

// PeriodInfo describes the analytics time period
type PeriodInfo struct {
	StartDate string `json:"start_date"` // YYYY-MM-DD
	EndDate   string `json:"end_date"`   // YYYY-MM-DD
	Days      int    `json:"days"`
}

// TurnoverInfo describes portfolio turnover metrics
type TurnoverInfo struct {
	AnnualTurnover  *float64 `json:"annual_turnover"`
	TurnoverDisplay string   `json:"turnover_display"`
	Status          string   `json:"status"`
	Alert           *string  `json:"alert"`
	Reason          string   `json:"reason"`
}

// PortfolioAnalyticsResponse is the main analytics response
type PortfolioAnalyticsResponse struct {
	Returns     ReturnsData     `json:"returns"`
	RiskMetrics RiskMetrics     `json:"risk_metrics"`
	Attribution AttributionData `json:"attribution"`
	Period      PeriodInfo      `json:"period"`
	Turnover    *TurnoverInfo   `json:"turnover,omitempty"`
}
