package dividends

import (
	"fmt"
	"strings"
	"time"
)

// DividendRecord represents a dividend payment with DRIP tracking
// Faithful translation from Python: app/domain/models.py -> DividendRecord
type DividendRecord struct {
	ID                 int        `json:"id"`
	Symbol             string     `json:"symbol"`
	ISIN               string     `json:"isin,omitempty"`
	CashFlowID         *int       `json:"cash_flow_id,omitempty"` // Link to cash_flows table
	Amount             float64    `json:"amount"`                 // Original dividend amount
	Currency           string     `json:"currency"`
	AmountEUR          float64    `json:"amount_eur"`   // Converted to EUR
	PaymentDate        string     `json:"payment_date"` // ISO date string
	Reinvested         bool       `json:"reinvested"`
	ReinvestedAt       *time.Time `json:"reinvested_at,omitempty"`
	ReinvestedQuantity *int       `json:"reinvested_quantity,omitempty"`
	PendingBonus       float64    `json:"pending_bonus"` // Expected return bonus (0.0 to 1.0)
	BonusCleared       bool       `json:"bonus_cleared"`
	ClearedAt          *time.Time `json:"cleared_at,omitempty"`
	CreatedAt          *time.Time `json:"created_at,omitempty"`
}

// Validate validates dividend record data
// Faithful translation from Python: def __post_init__(self)
func (d *DividendRecord) Validate() error {
	if d.Symbol == "" || strings.TrimSpace(d.Symbol) == "" {
		return fmt.Errorf("symbol cannot be empty")
	}

	if d.Amount <= 0 {
		return fmt.Errorf("dividend amount must be positive")
	}

	if d.AmountEUR <= 0 {
		return fmt.Errorf("amount_eur must be positive")
	}

	if d.Currency == "" {
		return fmt.Errorf("currency cannot be empty")
	}

	if d.PaymentDate == "" {
		return fmt.Errorf("payment_date cannot be empty")
	}

	// Normalize symbol
	d.Symbol = strings.ToUpper(strings.TrimSpace(d.Symbol))

	return nil
}
