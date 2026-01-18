/**
 * Package domain provides comprehensive Security model with all data.
 *
 * This file defines the Security struct that contains ALL security data from ALL sources:
 * - Basic security data (from universe.db)
 * - Scores (from portfolio.db)
 * - Position data (from portfolio.db, if held)
 * - Tags (from universe.db security_tags)
 * - Current price (runtime, from broker API or cache)
 *
 * This is the single unified Security type used throughout the system.
 * By having everything in one struct, we can pass it throughout the entire flow
 * from database reads to planning to trade execution without conversions or lookups.
 */
package domain

import (
	"encoding/json"
	"time"
)

/**
 * Security represents a complete security with ALL data from ALL sources.
 *
 * This struct contains everything we might need: basic data, scores, positions,
 * tags, and runtime data. All fields use pointers for optional data (nil = not set).
 *
 * Usage:
 *   security := securityService.Get("FR0014004L86")
 *   name := security.Name
 *   cagr := security.CAGRScore
 */
type Security struct {
	// ===== PRIMARY IDENTIFIERS (required) =====
	ISIN   string `json:"isin"`   // PRIMARY KEY - International Securities Identification Number
	Symbol string `json:"symbol"` // Broker/display symbol (boundary identifier for APIs)

	// ===== BASIC SECURITY DATA (from universe.db securities table) =====
	Name               string   `json:"name"`                // Company/security name
	ProductType        string   `json:"product_type"`        // EQUITY, ETF, MUTUALFUND, ETC, CASH, UNKNOWN
	Currency           string   `json:"currency,omitempty"`  // Trading currency
	Geography          string   `json:"geography,omitempty"` // Comma-separated for multiple (e.g., "EU, US")
	Industry           string   `json:"industry,omitempty"`  // Comma-separated for multiple (e.g., "Technology, Finance")
	FullExchangeName   string   `json:"fullExchangeName,omitempty"`
	MarketCode         string   `json:"market_code,omitempty"` // Tradernet market code (e.g., "FIX", "EU", "HKEX")
	MinLot             float64  `json:"min_lot"`               // Minimum lot size (float64 for fractional lots)
	MinPortfolioTarget float64  `json:"min_portfolio_target,omitempty"`
	MaxPortfolioTarget float64  `json:"max_portfolio_target,omitempty"`
	AllowBuy           bool     `json:"allow_buy"`           // Can buy this security?
	AllowSell          bool     `json:"allow_sell"`          // Can sell this security?
	PriorityMultiplier float64  `json:"priority_multiplier"` // Priority adjustment multiplier
	Tags               []string `json:"tags,omitempty"`      // Classification tags (e.g., ["value-opportunity", "stable"])
	LastSynced         *int64   `json:"-"`                   // Unix timestamp, converted to string in MarshalJSON

	// ===== SCORES (from portfolio.db scores table) =====
	// All scoring data for ranking and selection
	CalculatedAt       *time.Time `json:"calculated_at,omitempty"` // When scores were calculated
	TotalScore         *float64   `json:"total_score,omitempty"`   // Overall ranking score
	QualityScore       *float64   `json:"quality_score,omitempty"`
	OpportunityScore   *float64   `json:"opportunity_score,omitempty"`
	ConsistencyScore   *float64   `json:"consistency_score,omitempty"`
	CAGRScore          *float64   `json:"cagr_score,omitempty"`
	TechnicalScore     *float64   `json:"technical_score,omitempty"`
	StabilityScore     *float64   `json:"stability_score,omitempty"`
	AllocationFitScore *float64   `json:"allocation_fit_score,omitempty"`
	AnalystScore       *float64   `json:"analyst_score,omitempty"`
	SellScore          *float64   `json:"sell_score,omitempty"`

	// Technical indicators (from scores table)
	RSI             *float64 `json:"rsi,omitempty"`                // Relative Strength Index
	EMA200          *float64 `json:"ema_200,omitempty"`            // 200-day Exponential Moving Average
	Below52wHighPct *float64 `json:"below_52w_high_pct,omitempty"` // Percentage below 52-week high

	// Risk metrics (from scores table)
	Volatility             *float64 `json:"volatility,omitempty"`     // Annual volatility
	SharpeScore            *float64 `json:"sharpe_score,omitempty"`   // Sharpe ratio score
	DrawdownScore          *float64 `json:"drawdown_score,omitempty"` // Drawdown score
	FinancialStrengthScore *float64 `json:"financial_strength_score,omitempty"`
	DividendBonus          *float64 `json:"dividend_bonus,omitempty"` // Dividend yield bonus

	// Historical data quality
	HistoryYears *int `json:"history_years,omitempty"` // Years of historical data available

	// ===== POSITION DATA (from portfolio.db positions table, if held) =====
	// Current position data (nil if not held)
	PositionQuantity         *float64   `json:"position_quantity,omitempty"`           // Current shares held
	PositionAvgPrice         *float64   `json:"position_avg_price,omitempty"`          // Average cost per share (EUR)
	PositionCurrency         *string    `json:"position_currency,omitempty"`           // Position currency
	PositionCurrencyRate     *float64   `json:"position_currency_rate,omitempty"`      // Exchange rate to EUR
	PositionMarketValueEUR   *float64   `json:"position_market_value_eur,omitempty"`   // Current market value (EUR)
	PositionCostBasisEUR     *float64   `json:"position_cost_basis_eur,omitempty"`     // Total cost basis (EUR)
	PositionUnrealizedPnL    *float64   `json:"position_unrealized_pnl,omitempty"`     // Unrealized P&L (EUR)
	PositionUnrealizedPnLPct *float64   `json:"position_unrealized_pnl_pct,omitempty"` // Unrealized P&L %
	PositionLastUpdated      *time.Time `json:"position_last_updated,omitempty"`       // Last position update
	PositionFirstBoughtAt    *time.Time `json:"position_first_bought_at,omitempty"`    // First purchase date
	PositionLastSoldAt       *time.Time `json:"position_last_sold_at,omitempty"`       // Last sale date

	// ===== CURRENT MARKET DATA (runtime, from broker API or cache) =====
	CurrentPrice *float64 `json:"current_price,omitempty"` // Current market price (EUR)

	// ===== RAW DATA (from securities.data JSON column) =====
	// Complete Tradernet API response stored as-is for reference/fallback
	TradernetRaw json.RawMessage `json:"tradernet_raw,omitempty"` // Raw JSON from Tradernet API
}

/**
 * MarshalJSON customizes JSON serialization to convert Unix timestamp to string
 */
func (s Security) MarshalJSON() ([]byte, error) {
	type Alias Security
	aux := &struct {
		LastSynced string `json:"last_synced,omitempty"`
		*Alias
	}{
		Alias: (*Alias)(&s),
	}

	// Convert Unix timestamp to RFC3339 string for API
	if s.LastSynced != nil {
		t := time.Unix(*s.LastSynced, 0).UTC()
		aux.LastSynced = t.Format(time.RFC3339)
	}

	return json.Marshal(aux)
}

/**
 * HasPosition returns true if this security is currently held in the portfolio
 */
func (s *Security) HasPosition() bool {
	return s.PositionQuantity != nil && *s.PositionQuantity > 0
}

/**
 * IsTradable returns true if this security can be bought or sold
 */
func (s *Security) IsTradable() bool {
	return s.AllowBuy || s.AllowSell
}

/**
 * DailyPrice represents a daily OHLCV price point for historical data
 */
type DailyPrice struct {
	Date          string   `json:"date"` // YYYY-MM-DD format
	Open          float64  `json:"open"`
	High          float64  `json:"high"`
	Low           float64  `json:"low"`
	Close         float64  `json:"close"`
	AdjustedClose *float64 `json:"adjusted_close,omitempty"`
	Volume        *int64   `json:"volume,omitempty"`
}

/**
 * HistoricalDataOptions configures historical data queries
 */
type HistoricalDataOptions struct {
	StartDate string // YYYY-MM-DD format
	EndDate   string // YYYY-MM-DD format
	Limit     int    // Max number of records (0 = no limit)
}
