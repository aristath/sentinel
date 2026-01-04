package trading

import (
	"fmt"
	"strings"
	"time"
)

// TradeSide represents the trade direction (BUY or SELL)
// Faithful translation from Python: app/domain/value_objects/trade_side.py
type TradeSide string

const (
	TradeSideBuy  TradeSide = "BUY"
	TradeSideSell TradeSide = "SELL"
)

// IsValid checks if the trade side is valid
func (ts TradeSide) IsValid() bool {
	return ts == TradeSideBuy || ts == TradeSideSell
}

// IsBuy returns true if this is a BUY trade
func (ts TradeSide) IsBuy() bool {
	return ts == TradeSideBuy
}

// IsSell returns true if this is a SELL trade
func (ts TradeSide) IsSell() bool {
	return ts == TradeSideSell
}

// FromString creates TradeSide from string (case-insensitive)
// Faithful translation from Python: @classmethod def from_string(cls, value: str) -> "TradeSide"
func TradeSideFromString(value string) (TradeSide, error) {
	if value == "" {
		return "", fmt.Errorf("invalid trade side: empty string")
	}

	valueUpper := strings.ToUpper(value)
	switch valueUpper {
	case "BUY":
		return TradeSideBuy, nil
	case "SELL":
		return TradeSideSell, nil
	default:
		return "", fmt.Errorf("invalid trade side: %s", value)
	}
}

// Trade represents an executed trade record
// Faithful translation from Python: app/domain/models.py -> Trade
type Trade struct {
	ExecutedAt   time.Time  `json:"executed_at"`
	CurrencyRate *float64   `json:"currency_rate,omitempty"`
	ValueEUR     *float64   `json:"value_eur,omitempty"`
	CreatedAt    *time.Time `json:"created_at,omitempty"`
	Source       string     `json:"source"`
	Symbol       string     `json:"symbol"`
	OrderID      string     `json:"order_id,omitempty"`
	Currency     string     `json:"currency,omitempty"`
	ISIN         string     `json:"isin,omitempty"`
	Mode         string     `json:"mode"`
	Side         TradeSide  `json:"side"`
	Price        float64    `json:"price"`
	ID           int        `json:"id"`
	Quantity     float64    `json:"quantity"`
}

// Validate validates trade data and normalizes symbol
// Faithful translation from Python: def __post_init__(self)
func (t *Trade) Validate() error {
	if t.Symbol == "" || strings.TrimSpace(t.Symbol) == "" {
		return fmt.Errorf("symbol cannot be empty")
	}

	if t.Quantity <= 0 {
		return fmt.Errorf("quantity must be positive")
	}

	if t.Price <= 0 {
		return fmt.Errorf("price must be positive")
	}

	// Normalize symbol
	t.Symbol = strings.ToUpper(strings.TrimSpace(t.Symbol))

	return nil
}
