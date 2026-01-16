package domain

import "time"

// EnrichedPosition combines ALL position data in one place.
// This eliminates 600+ redundant map lookups per planning run by embedding:
// - All 14 database fields from portfolio.Position
// - Security metadata (from StocksByISIN lookup)
// - Current market price (from CurrentPrices map)
// - Calculated fields (DaysHeld, WeightInPortfolio)
//
// REPLACES the minimal domain.Position type used in OpportunityContext.
type EnrichedPosition struct {
	// Core position data (14 fields from portfolio.Position database table)
	ISIN             string     // Primary key for all lookups
	Symbol           string     // Display/logging identifier
	Quantity         float64    // Current shares held
	AverageCost      float64    // Cost basis per share (EUR)
	Currency         string     // Position currency
	CurrencyRate     float64    // Exchange rate to EUR (1 EUR = CurrencyRate units)
	MarketValueEUR   float64    // Current market value in EUR
	CostBasisEUR     float64    // Total cost basis in EUR
	UnrealizedPnL    float64    // Unrealized P&L (EUR)
	UnrealizedPnLPct float64    // Unrealized P&L percentage
	LastUpdated      *time.Time // Last position update timestamp
	FirstBoughtAt    *time.Time // First purchase date (midnight UTC)
	LastSoldAt       *time.Time // Last sale date if any (midnight UTC)

	// Security metadata (from StocksByISIN map - eliminates lookup)
	SecurityName string // Company name
	Geography    string // Geography (comma-separated for multiple)
	Exchange     string // Exchange identifier
	Active       bool   // Is security active for trading?
	AllowBuy     bool   // Can buy this security?
	AllowSell    bool   // Can sell this security?
	MinLot       int    // Minimum lot size

	// Market data (from CurrentPrices map - eliminates lookup)
	CurrentPrice float64 // Current market price (EUR)

	// Calculated fields (computed during enrichment)
	DaysHeld          *int    // Days since first purchase (nil if unknown)
	WeightInPortfolio float64 // Percentage of total portfolio value
}

// CanBuy returns true if buying is allowed for this security.
// After migration 038: All securities in database are active (no soft delete), so we only check AllowBuy.
func (e *EnrichedPosition) CanBuy() bool {
	return e.AllowBuy
}

// CanSell returns true if selling is allowed for this security.
// After migration 038: All securities in database are active (no soft delete), so we only check AllowSell.
func (e *EnrichedPosition) CanSell() bool {
	return e.AllowSell
}

// GainPercent calculates the gain/loss percentage from cost basis.
// Returns 0.0 if AverageCost is zero or negative (edge case).
// Formula: (CurrentPrice - AverageCost) / AverageCost
func (e *EnrichedPosition) GainPercent() float64 {
	if e.AverageCost <= 0 {
		return 0
	}
	return (e.CurrentPrice - e.AverageCost) / e.AverageCost
}
