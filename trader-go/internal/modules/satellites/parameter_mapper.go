package satellites

import "fmt"

// TradingParameters represents concrete trading parameters derived from satellite settings
// Faithful translation from Python: app/modules/satellites/domain/parameter_mapper.py
//
// These parameters are used by the planner and execution systems.
type TradingParameters struct {
	// Position sizing
	PositionSizeMax float64 `json:"position_size_max"` // Maximum position size as % of bucket (0.15-0.40)
	StopLossPct     float64 `json:"stop_loss_pct"`     // Stop loss percentage (0.05-0.20)

	// Hold duration
	TargetHoldDays  int     `json:"target_hold_days"`  // Target holding period in days (1-180)
	PatienceFactor  float64 `json:"patience_factor"`   // Patience factor for entry timing (0.0-1.0)

	// Entry style
	BuyDipThreshold     float64 `json:"buy_dip_threshold"`     // Buy dip threshold: RSI < this (0.0-1.0)
	BreakoutThreshold   float64 `json:"breakout_threshold"`    // Breakout threshold: momentum > this (0.0-1.0)

	// Diversification
	MaxPositions         int     `json:"max_positions"`          // Maximum number of positions (3-23)
	DiversificationFactor float64 `json:"diversification_factor"` // Diversification preference (0.0-1.0)

	// Profit taking
	TakeProfitThreshold   float64 `json:"take_profit_threshold"`    // Take profit at gain % (0.05-0.30)
	TrailingStopDistance  float64 `json:"trailing_stop_distance"`   // Trailing stop distance % (0.0-0.10)

	// Toggles
	TrailingStops       bool   `json:"trailing_stops"`        // Enable trailing stops
	FollowRegime        bool   `json:"follow_regime"`         // Follow market regime signals
	AutoHarvest         bool   `json:"auto_harvest"`          // Auto-harvest gains above threshold
	PauseHighVolatility bool   `json:"pause_high_volatility"` // Pause trading during high volatility

	// Dividend handling
	DividendHandling string `json:"dividend_handling"` // reinvest_same | send_to_core | accumulate_cash
}

// ParameterMapper maps satellite settings to concrete trading parameters
type ParameterMapper struct{}

// NewParameterMapper creates a new parameter mapper
func NewParameterMapper() *ParameterMapper {
	return &ParameterMapper{}
}

// MapSettingsToParameters maps satellite settings to concrete trading parameters
//
// Implements the formulas from the planning document:
// - risk_appetite → position_size_max, stop_loss_pct
// - hold_duration → target_hold_days, patience_factor
// - entry_style → buy_dip_threshold, breakout_threshold (0.0=dip buyer, 1.0=breakout)
// - position_spread → max_positions, diversification_factor
// - profit_taking → take_profit_threshold, trailing_stop_distance
//
// Args:
//   settings: Satellite settings with slider values (0.0-1.0)
//
// Returns:
//   TradingParameters with concrete values for trading logic
func (m *ParameterMapper) MapSettingsToParameters(settings SatelliteSettings) TradingParameters {
	// Position sizing from risk_appetite
	positionSizeMax := 0.15 + (0.25 * settings.RiskAppetite) // 15-40%
	stopLossPct := 0.05 + (0.15 * settings.RiskAppetite)     // 5-20%

	// Hold duration mapping
	targetHoldDays := int(1 + (180 * settings.HoldDuration)) // 1-180 days
	patienceFactor := settings.HoldDuration                  // 0.0-1.0

	// Entry style mapping (0.0 = pure dip buyer, 1.0 = pure breakout)
	buyDipThreshold := 1.0 - settings.EntryStyle
	breakoutThreshold := settings.EntryStyle

	// Diversification from position_spread
	maxPositions := int(3 + (20 * settings.PositionSpread))  // 3-23 positions
	diversificationFactor := settings.PositionSpread          // 0.0-1.0

	// Profit taking parameters
	takeProfitThreshold := 0.05 + (0.25 * settings.ProfitTaking)   // 5-30%
	trailingStopDistance := 0.10 * (1.0 - settings.ProfitTaking)   // 10-0%

	return TradingParameters{
		PositionSizeMax:       positionSizeMax,
		StopLossPct:           stopLossPct,
		TargetHoldDays:        targetHoldDays,
		PatienceFactor:        patienceFactor,
		BuyDipThreshold:       buyDipThreshold,
		BreakoutThreshold:     breakoutThreshold,
		MaxPositions:          maxPositions,
		DiversificationFactor: diversificationFactor,
		TakeProfitThreshold:   takeProfitThreshold,
		TrailingStopDistance:  trailingStopDistance,
		TrailingStops:         settings.TrailingStops,
		FollowRegime:          settings.FollowRegime,
		AutoHarvest:           settings.AutoHarvest,
		PauseHighVolatility:   settings.PauseHighVolatility,
		DividendHandling:      settings.DividendHandling,
	}
}

// GetPositionSizePct returns maximum position size percentage from settings
func (m *ParameterMapper) GetPositionSizePct(settings SatelliteSettings) float64 {
	return 0.15 + (0.25 * settings.RiskAppetite)
}

// GetStopLossPct returns stop loss percentage from settings
func (m *ParameterMapper) GetStopLossPct(settings SatelliteSettings) float64 {
	return 0.05 + (0.15 * settings.RiskAppetite)
}

// GetTargetHoldDays returns target holding period in days from settings
func (m *ParameterMapper) GetTargetHoldDays(settings SatelliteSettings) int {
	return int(1 + (180 * settings.HoldDuration))
}

// GetMaxPositions returns maximum number of positions from settings
func (m *ParameterMapper) GetMaxPositions(settings SatelliteSettings) int {
	return int(3 + (20 * settings.PositionSpread))
}

// GetTakeProfitThreshold returns take profit threshold from settings
func (m *ParameterMapper) GetTakeProfitThreshold(settings SatelliteSettings) float64 {
	return 0.05 + (0.25 * settings.ProfitTaking)
}

// IsDipBuyer checks if strategy is dip buyer oriented
func (m *ParameterMapper) IsDipBuyer(settings SatelliteSettings) bool {
	return settings.EntryStyle < 0.5
}

// IsBreakoutBuyer checks if strategy is breakout buyer oriented
func (m *ParameterMapper) IsBreakoutBuyer(settings SatelliteSettings) bool {
	return settings.EntryStyle >= 0.5
}

// DescribeParameters generates human-readable description of trading parameters
func (m *ParameterMapper) DescribeParameters(params TradingParameters) string {
	entryBias := "dip buyer"
	if params.BreakoutThreshold >= params.BuyDipThreshold {
		entryBias = "breakout buyer"
	}

	trailingStops := "disabled"
	if params.TrailingStops {
		trailingStops = "enabled"
	}

	followRegime := "disabled"
	if params.FollowRegime {
		followRegime = "enabled"
	}

	autoHarvest := "disabled"
	if params.AutoHarvest {
		autoHarvest = "enabled"
	}

	pauseOnVolatility := "disabled"
	if params.PauseHighVolatility {
		pauseOnVolatility = "enabled"
	}

	return fmt.Sprintf(`Trading Parameters:
  Position Sizing:
    - Max position size: %.1f%% of bucket
    - Stop loss: %.1f%%
    - Max positions: %d

  Hold Duration:
    - Target: %d days
    - Patience factor: %.2f

  Entry Style: %s
    - Buy dip threshold: %.2f
    - Breakout threshold: %.2f

  Profit Taking:
    - Take profit at: +%.1f%%
    - Trailing stop distance: %.1f%%

  Features:
    - Trailing stops: %s
    - Follow regime: %s
    - Auto harvest: %s
    - Pause on volatility: %s
    - Dividend handling: %s
`,
		params.PositionSizeMax*100,
		params.StopLossPct*100,
		params.MaxPositions,
		params.TargetHoldDays,
		params.PatienceFactor,
		entryBias,
		params.BuyDipThreshold,
		params.BreakoutThreshold,
		params.TakeProfitThreshold*100,
		params.TrailingStopDistance*100,
		trailingStops,
		followRegime,
		autoHarvest,
		pauseOnVolatility,
		params.DividendHandling,
	)
}
