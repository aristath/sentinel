package domain

import "time"

// Currency represents a currency code
type Currency string

const (
	CurrencyEUR Currency = "EUR"
	CurrencyUSD Currency = "USD"
	CurrencyGBP Currency = "GBP"
	CurrencyTEST Currency = "TEST" // For research mode
)

// Security represents a tradable security
type Security struct {
	ID          int64     `json:"id"`
	Symbol      string    `json:"symbol"`
	Name        string    `json:"name"`
	Exchange    string    `json:"exchange"`
	Currency    Currency  `json:"currency"`
	ISIN        string    `json:"isin"`
	Active      bool      `json:"active"`
	LastUpdated time.Time `json:"last_updated"`
}

// Position represents a portfolio position
type Position struct {
	ID           int64     `json:"id"`
	SecurityID   int64     `json:"security_id"`
	Symbol       string    `json:"symbol"`
	Quantity     float64   `json:"quantity"`
	AverageCost  float64   `json:"average_cost"`
	CurrentPrice float64   `json:"current_price"`
	MarketValue  float64   `json:"market_value"`
	UnrealizedPL float64   `json:"unrealized_pl"`
	Currency     Currency  `json:"currency"`
	LastUpdated  time.Time `json:"last_updated"`
}

// Trade represents an executed trade
type Trade struct {
	ID         int64     `json:"id"`
	SecurityID int64     `json:"security_id"`
	Symbol     string    `json:"symbol"`
	Side       string    `json:"side"` // BUY or SELL
	Quantity   float64   `json:"quantity"`
	Price      float64   `json:"price"`
	Fees       float64   `json:"fees"`
	Total      float64   `json:"total"`
	Currency   Currency  `json:"currency"`
	ExecutedAt time.Time `json:"executed_at"`
	CreatedAt  time.Time `json:"created_at"`
}

// Money represents a monetary value with currency
type Money struct {
	Amount   float64  `json:"amount"`
	Currency Currency `json:"currency"`
}

// NewMoney creates a new Money value
func NewMoney(amount float64, currency Currency) Money {
	return Money{
		Amount:   amount,
		Currency: currency,
	}
}
