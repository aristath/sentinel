package portfolio

// Position represents current position in a security
// Faithful translation from Python: app/modules/portfolio/domain/models.py
type Position struct {
	LastUpdated      string  `json:"last_updated,omitempty"`
	BucketID         string  `json:"bucket_id"`
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
	BucketID         string  `db:"bucket_id"`
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
}
