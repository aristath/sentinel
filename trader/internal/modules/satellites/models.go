package satellites

import (
	"fmt"
	"time"
)

// BucketType represents the type of portfolio bucket
type BucketType string

const (
	BucketTypeCore      BucketType = "core"
	BucketTypeSatellite BucketType = "satellite"
)

// BucketStatus represents the lifecycle status of a bucket
type BucketStatus string

const (
	BucketStatusResearch     BucketStatus = "research"     // Paper trading, no real money
	BucketStatusAccumulating BucketStatus = "accumulating" // Building up to minimum threshold
	BucketStatusActive       BucketStatus = "active"       // Normal trading
	BucketStatusHibernating  BucketStatus = "hibernating"  // Below minimum, hold only
	BucketStatusPaused       BucketStatus = "paused"       // Manual pause by user
	BucketStatusRetired      BucketStatus = "retired"      // Closed, historical data only
)

// TransactionType represents the type of bucket transaction for audit trail
type TransactionType string

const (
	TransactionTypeDeposit      TransactionType = "deposit"
	TransactionTypeReallocation TransactionType = "reallocation"
	TransactionTypeTradeBuy     TransactionType = "trade_buy"
	TransactionTypeTradeSell    TransactionType = "trade_sell"
	TransactionTypeDividend     TransactionType = "dividend"
	TransactionTypeTransferIn   TransactionType = "transfer_in"
	TransactionTypeTransferOut  TransactionType = "transfer_out"
)

// Bucket represents a portfolio bucket (core or satellite)
// Faithful translation from Python: app/modules/satellites/domain/models.py -> Bucket
type Bucket struct {
	ID                   string       `json:"id"`
	Name                 string       `json:"name"`
	Type                 BucketType   `json:"type"`
	Status               BucketStatus `json:"status"`
	Notes                *string      `json:"notes,omitempty"`
	TargetPct            *float64     `json:"target_pct,omitempty"`            // Target allocation percentage (0.0-1.0)
	MinPct               *float64     `json:"min_pct,omitempty"`               // Minimum percentage before hibernation
	MaxPct               *float64     `json:"max_pct,omitempty"`               // Maximum allowed percentage
	ConsecutiveLosses    int          `json:"consecutive_losses"`              // Count of consecutive losing trades
	MaxConsecutiveLosses int          `json:"max_consecutive_losses"`          // Circuit breaker threshold
	HighWaterMark        float64      `json:"high_water_mark"`                 // Peak bucket value
	HighWaterMarkDate    *string      `json:"high_water_mark_date,omitempty"`  // When high water mark was set
	LossStreakPausedAt   *string      `json:"loss_streak_paused_at,omitempty"` // When circuit breaker triggered
	CreatedAt            string       `json:"created_at"`
	UpdatedAt            string       `json:"updated_at"`
}

// IsActive checks if bucket is in an active trading state
func (b *Bucket) IsActive() bool {
	return b.Status == BucketStatusActive
}

// IsTradingAllowed checks if new trades are allowed
func (b *Bucket) IsTradingAllowed() bool {
	return b.Status == BucketStatusActive || b.Status == BucketStatusAccumulating
}

// IsCore checks if this is the core bucket
func (b *Bucket) IsCore() bool {
	return b.Type == BucketTypeCore
}

// IsSatellite checks if this is a satellite bucket
func (b *Bucket) IsSatellite() bool {
	return b.Type == BucketTypeSatellite
}

// CalculateDrawdown calculates current drawdown from high water mark
// Returns drawdown as a percentage (0.0-1.0)
func (b *Bucket) CalculateDrawdown(currentValue float64) float64 {
	if b.HighWaterMark <= 0 {
		return 0.0
	}
	drawdown := (b.HighWaterMark - currentValue) / b.HighWaterMark
	if drawdown < 0 {
		return 0.0
	}
	return drawdown
}

// BucketBalance represents virtual cash balance for a bucket in a specific currency
// Faithful translation from Python: app/modules/satellites/domain/models.py -> BucketBalance
type BucketBalance struct {
	BucketID    string  `json:"bucket_id"`
	Currency    string  `json:"currency"`
	Balance     float64 `json:"balance"`
	LastUpdated string  `json:"last_updated"`
}

// BucketTransaction represents an audit trail entry for bucket cash flow
// Faithful translation from Python: app/modules/satellites/domain/models.py -> BucketTransaction
type BucketTransaction struct {
	ID          *int64          `json:"id,omitempty"` // Database ID (set after insert)
	BucketID    string          `json:"bucket_id"`
	Type        TransactionType `json:"type"`
	Amount      float64         `json:"amount"` // Positive for inflow, negative for outflow
	Currency    string          `json:"currency"`
	Description *string         `json:"description,omitempty"`
	CreatedAt   string          `json:"created_at"`
}

// NewBucketTransaction creates a new bucket transaction with current timestamp
func NewBucketTransaction(bucketID string, txType TransactionType, amount float64, currency string, description *string) *BucketTransaction {
	now := time.Now().Format(time.RFC3339)
	return &BucketTransaction{
		BucketID:    bucketID,
		Type:        txType,
		Amount:      amount,
		Currency:    currency,
		Description: description,
		CreatedAt:   now,
	}
}

// SatelliteSettings represents strategy configuration settings for a satellite
// Faithful translation from Python: app/modules/satellites/domain/models.py -> SatelliteSettings
//
// Slider values are in range 0.0-1.0 where:
// - 0.0 = Conservative/Left option
// - 1.0 = Aggressive/Right option
type SatelliteSettings struct {
	SatelliteID         string  `json:"satellite_id"`
	Preset              *string `json:"preset,omitempty"`      // Strategy preset name
	RiskAppetite        float64 `json:"risk_appetite"`         // 0=Conservative, 1=Aggressive
	HoldDuration        float64 `json:"hold_duration"`         // 0=Quick flips, 1=Patient holds
	EntryStyle          float64 `json:"entry_style"`           // 0=Buy dips, 1=Buy breakouts
	PositionSpread      float64 `json:"position_spread"`       // 0=Concentrated, 1=Diversified
	ProfitTaking        float64 `json:"profit_taking"`         // 0=Let winners run, 1=Take profits early
	TrailingStops       bool    `json:"trailing_stops"`        // Enable trailing stops
	FollowRegime        bool    `json:"follow_regime"`         // Follow market regime signals
	AutoHarvest         bool    `json:"auto_harvest"`          // Auto-harvest gains to core
	PauseHighVolatility bool    `json:"pause_high_volatility"` // Pause during high volatility
	DividendHandling    string  `json:"dividend_handling"`     // reinvest_same, send_to_core, accumulate_cash

	// Risk Metric Parameters - Parameterize risk calculations per agent
	RiskFreeRate         float64 `json:"risk_free_rate"`         // Annual risk-free rate (default: 0.035)
	SortinoMAR           float64 `json:"sortino_mar"`            // Minimum Acceptable Return for Sortino (default: 0.05)
	EvaluationPeriodDays int     `json:"evaluation_period_days"` // Days for performance evaluation (default: 90)
	VolatilityWindow     int     `json:"volatility_window"`      // Days for volatility calculation (default: 60)
}

// NewSatelliteSettings creates a new SatelliteSettings with default values
func NewSatelliteSettings(satelliteID string) *SatelliteSettings {
	return &SatelliteSettings{
		SatelliteID:         satelliteID,
		RiskAppetite:        0.5,
		HoldDuration:        0.5,
		EntryStyle:          0.5,
		PositionSpread:      0.5,
		ProfitTaking:        0.5,
		TrailingStops:       false,
		FollowRegime:        false,
		AutoHarvest:         false,
		PauseHighVolatility: false,
		DividendHandling:    "reinvest_same",
		// Risk metric defaults (moderate/balanced)
		RiskFreeRate:         0.035, // 3.5% annual risk-free rate
		SortinoMAR:           0.05,  // 5% minimum acceptable return for retirement
		EvaluationPeriodDays: 90,    // Quarterly evaluation
		VolatilityWindow:     60,    // 60-day volatility window
	}
}

// Validate validates slider values are in range
func (s *SatelliteSettings) Validate() error {
	sliders := map[string]float64{
		"risk_appetite":   s.RiskAppetite,
		"hold_duration":   s.HoldDuration,
		"entry_style":     s.EntryStyle,
		"position_spread": s.PositionSpread,
		"profit_taking":   s.ProfitTaking,
	}

	for name, value := range sliders {
		if value < 0.0 || value > 1.0 {
			return fmt.Errorf("%s must be between 0.0 and 1.0, got %f", name, value)
		}
	}

	validDividendOptions := []string{"reinvest_same", "send_to_core", "accumulate_cash"}
	valid := false
	for _, option := range validDividendOptions {
		if s.DividendHandling == option {
			valid = true
			break
		}
	}
	if !valid {
		return fmt.Errorf("dividend_handling must be one of %v, got %s", validDividendOptions, s.DividendHandling)
	}

	return nil
}
