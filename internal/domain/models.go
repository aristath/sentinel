// Package domain provides core domain models and types.
package domain

import "time"

// Currency represents a currency code
type Currency string

const (
	CurrencyEUR  Currency = "EUR"
	CurrencyUSD  Currency = "USD"
	CurrencyGBP  Currency = "GBP"
	CurrencyTEST Currency = "TEST" // For research mode
)

// ProductType represents the type of financial product/instrument
type ProductType string

const (
	// ProductTypeEquity represents individual stocks/shares
	ProductTypeEquity ProductType = "EQUITY"
	// ProductTypeETF represents Exchange Traded Funds
	ProductTypeETF ProductType = "ETF"
	// ProductTypeETC represents Exchange Traded Commodities
	ProductTypeETC ProductType = "ETC"
	// ProductTypeMutualFund represents mutual funds (some UCITS products)
	ProductTypeMutualFund ProductType = "MUTUALFUND"
	// ProductTypeIndex represents market indices (non-tradeable)
	ProductTypeIndex ProductType = "INDEX"
	// ProductTypeUnknown represents unknown type
	ProductTypeUnknown ProductType = "UNKNOWN"
)

// Security type removed - use universe.Security directly (single source of truth).
// After migration 038: All security data is in universe.Security with JSON storage.

// Position represents a portfolio position
type Position struct {
	LastUpdated  time.Time `json:"last_updated"`
	Symbol       string    `json:"symbol"`
	ISIN         string    `json:"isin"` // Primary identifier (after migration)
	Currency     Currency  `json:"currency"`
	ID           int64     `json:"id"`
	SecurityID   int64     `json:"security_id"`
	Quantity     float64   `json:"quantity"`
	AverageCost  float64   `json:"average_cost"`
	CurrentPrice float64   `json:"current_price"`
	MarketValue  float64   `json:"market_value"`
	UnrealizedPL float64   `json:"unrealized_pl"`
}

// Trade represents an executed trade
type Trade struct {
	ExecutedAt time.Time `json:"executed_at"`
	CreatedAt  time.Time `json:"created_at"`
	Symbol     string    `json:"symbol"`
	Side       string    `json:"side"`
	Currency   Currency  `json:"currency"`
	ID         int64     `json:"id"`
	SecurityID int64     `json:"security_id"`
	Quantity   float64   `json:"quantity"`
	Price      float64   `json:"price"`
	Fees       float64   `json:"fees"`
	Total      float64   `json:"total"`
}

// Money represents a monetary value with currency
type Money struct {
	Currency Currency `json:"currency"`
	Amount   float64  `json:"amount"`
}

// NewMoney creates a new Money value
func NewMoney(amount float64, currency Currency) Money {
	return Money{
		Amount:   amount,
		Currency: currency,
	}
}
