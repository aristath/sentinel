package satellites

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestParameterMapper_MapSettings_MomentumHunter(t *testing.T) {
	mapper := NewParameterMapper()
	settings := NewSatelliteSettings("sat1")
	ApplyPresetToSettings(settings, "momentum_hunter")

	params := mapper.MapSettingsToParameters(*settings)

	// Position sizing (risk_appetite = 0.7)
	assert.InDelta(t, 0.325, params.PositionSizeMax, 0.001) // 0.15 + (0.25 * 0.7)
	assert.InDelta(t, 0.155, params.StopLossPct, 0.001)     // 0.05 + (0.15 * 0.7)

	// Hold duration (hold_duration = 0.3)
	assert.Equal(t, 55, params.TargetHoldDays) // 1 + (180 * 0.3)
	assert.Equal(t, 0.3, params.PatienceFactor)

	// Entry style (entry_style = 0.8, breakout buyer)
	assert.InDelta(t, 0.2, params.BuyDipThreshold, 0.0001) // 1.0 - 0.8
	assert.InDelta(t, 0.8, params.BreakoutThreshold, 0.0001)

	// Diversification (position_spread = 0.4)
	assert.Equal(t, 11, params.MaxPositions) // 3 + (20 * 0.4)
	assert.Equal(t, 0.4, params.DiversificationFactor)

	// Profit taking (profit_taking = 0.6)
	assert.InDelta(t, 0.20, params.TakeProfitThreshold, 0.01)  // 0.05 + (0.25 * 0.6)
	assert.InDelta(t, 0.04, params.TrailingStopDistance, 0.01) // 0.10 * (1.0 - 0.6)

	// Toggles
	assert.True(t, params.TrailingStops)
	assert.True(t, params.FollowRegime)
	assert.False(t, params.AutoHarvest)
	assert.False(t, params.PauseHighVolatility)
	assert.Equal(t, "reinvest_same", params.DividendHandling)
}

func TestParameterMapper_MapSettings_SteadyEddy(t *testing.T) {
	mapper := NewParameterMapper()
	settings := NewSatelliteSettings("sat1")
	ApplyPresetToSettings(settings, "steady_eddy")

	params := mapper.MapSettingsToParameters(*settings)

	// Position sizing (risk_appetite = 0.3, conservative)
	assert.InDelta(t, 0.225, params.PositionSizeMax, 0.001) // 0.15 + (0.25 * 0.3)
	assert.InDelta(t, 0.095, params.StopLossPct, 0.001)     // 0.05 + (0.15 * 0.3)

	// Hold duration (hold_duration = 0.8, long term)
	assert.Equal(t, 145, params.TargetHoldDays) // 1 + (180 * 0.8)

	// Entry style (entry_style = 0.3, dip buyer)
	assert.Equal(t, 0.7, params.BuyDipThreshold)
	assert.Equal(t, 0.3, params.BreakoutThreshold)

	// Diversification (position_spread = 0.7, wide)
	assert.Equal(t, 17, params.MaxPositions)

	// Profit taking (profit_taking = 0.3, let winners run)
	assert.InDelta(t, 0.125, params.TakeProfitThreshold, 0.001)
	assert.InDelta(t, 0.07, params.TrailingStopDistance, 0.001)
}

func TestParameterMapper_MapSettings_DipBuyer(t *testing.T) {
	mapper := NewParameterMapper()
	settings := NewSatelliteSettings("sat1")
	ApplyPresetToSettings(settings, "dip_buyer")

	params := mapper.MapSettingsToParameters(*settings)

	// Entry style (entry_style = 0.2, pure dip buyer)
	assert.Equal(t, 0.8, params.BuyDipThreshold) // 1.0 - 0.2
	assert.Equal(t, 0.2, params.BreakoutThreshold)
}

func TestParameterMapper_MapSettings_DividendCatcher(t *testing.T) {
	mapper := NewParameterMapper()
	settings := NewSatelliteSettings("sat1")
	ApplyPresetToSettings(settings, "dividend_catcher")

	params := mapper.MapSettingsToParameters(*settings)

	// Hold duration (hold_duration = 0.2, short term)
	assert.Equal(t, 37, params.TargetHoldDays) // 1 + (180 * 0.2)

	// Diversification (position_spread = 0.8, very wide)
	assert.Equal(t, 19, params.MaxPositions) // 3 + (20 * 0.8)

	// Profit taking (profit_taking = 0.8, aggressive)
	assert.InDelta(t, 0.25, params.TakeProfitThreshold, 0.001)  // 0.05 + (0.25 * 0.8)
	assert.InDelta(t, 0.02, params.TrailingStopDistance, 0.001) // 0.10 * (1.0 - 0.8)

	assert.Equal(t, "accumulate_cash", params.DividendHandling)
}

func TestParameterMapper_GetPositionSizePct(t *testing.T) {
	mapper := NewParameterMapper()

	tests := []struct {
		riskAppetite float64
		expected     float64
	}{
		{0.0, 0.15},  // Minimum: 15%
		{0.5, 0.275}, // Mid: 27.5%
		{1.0, 0.40},  // Maximum: 40%
	}

	for _, tt := range tests {
		settings := SatelliteSettings{RiskAppetite: tt.riskAppetite}
		result := mapper.GetPositionSizePct(settings)
		assert.InDelta(t, tt.expected, result, 0.001)
	}
}

func TestParameterMapper_GetStopLossPct(t *testing.T) {
	mapper := NewParameterMapper()

	tests := []struct {
		riskAppetite float64
		expected     float64
	}{
		{0.0, 0.05},  // Minimum: 5%
		{0.5, 0.125}, // Mid: 12.5%
		{1.0, 0.20},  // Maximum: 20%
	}

	for _, tt := range tests {
		settings := SatelliteSettings{RiskAppetite: tt.riskAppetite}
		result := mapper.GetStopLossPct(settings)
		assert.InDelta(t, tt.expected, result, 0.001)
	}
}

func TestParameterMapper_GetTargetHoldDays(t *testing.T) {
	mapper := NewParameterMapper()

	tests := []struct {
		holdDuration float64
		expected     int
	}{
		{0.0, 1},   // Minimum: 1 day
		{0.5, 91},  // Mid: 91 days
		{1.0, 181}, // Maximum: 181 days
	}

	for _, tt := range tests {
		settings := SatelliteSettings{HoldDuration: tt.holdDuration}
		result := mapper.GetTargetHoldDays(settings)
		assert.Equal(t, tt.expected, result)
	}
}

func TestParameterMapper_GetMaxPositions(t *testing.T) {
	mapper := NewParameterMapper()

	tests := []struct {
		positionSpread float64
		expected       int
	}{
		{0.0, 3},  // Minimum: 3 positions (concentrated)
		{0.5, 13}, // Mid: 13 positions
		{1.0, 23}, // Maximum: 23 positions (diversified)
	}

	for _, tt := range tests {
		settings := SatelliteSettings{PositionSpread: tt.positionSpread}
		result := mapper.GetMaxPositions(settings)
		assert.Equal(t, tt.expected, result)
	}
}

func TestParameterMapper_GetTakeProfitThreshold(t *testing.T) {
	mapper := NewParameterMapper()

	tests := []struct {
		profitTaking float64
		expected     float64
	}{
		{0.0, 0.05},  // Minimum: 5%
		{0.5, 0.175}, // Mid: 17.5%
		{1.0, 0.30},  // Maximum: 30%
	}

	for _, tt := range tests {
		settings := SatelliteSettings{ProfitTaking: tt.profitTaking}
		result := mapper.GetTakeProfitThreshold(settings)
		assert.InDelta(t, tt.expected, result, 0.001)
	}
}

func TestParameterMapper_IsDipBuyer(t *testing.T) {
	mapper := NewParameterMapper()

	dipBuyer := SatelliteSettings{EntryStyle: 0.3}
	assert.True(t, mapper.IsDipBuyer(dipBuyer))

	neutral := SatelliteSettings{EntryStyle: 0.5}
	assert.False(t, mapper.IsDipBuyer(neutral))

	breakoutBuyer := SatelliteSettings{EntryStyle: 0.8}
	assert.False(t, mapper.IsDipBuyer(breakoutBuyer))
}

func TestParameterMapper_IsBreakoutBuyer(t *testing.T) {
	mapper := NewParameterMapper()

	dipBuyer := SatelliteSettings{EntryStyle: 0.3}
	assert.False(t, mapper.IsBreakoutBuyer(dipBuyer))

	neutral := SatelliteSettings{EntryStyle: 0.5}
	assert.True(t, mapper.IsBreakoutBuyer(neutral))

	breakoutBuyer := SatelliteSettings{EntryStyle: 0.8}
	assert.True(t, mapper.IsBreakoutBuyer(breakoutBuyer))
}

func TestParameterMapper_DescribeParameters(t *testing.T) {
	mapper := NewParameterMapper()

	// Momentum hunter
	settings := NewSatelliteSettings("sat1")
	ApplyPresetToSettings(settings, "momentum_hunter")
	params := mapper.MapSettingsToParameters(*settings)

	desc := mapper.DescribeParameters(params)
	assert.Contains(t, desc, "Trading Parameters:")
	assert.Contains(t, desc, "Max position size:")
	assert.Contains(t, desc, "Stop loss:")
	assert.Contains(t, desc, "Target:")
	assert.Contains(t, desc, "days")
	assert.Contains(t, desc, "breakout buyer")
	assert.Contains(t, desc, "Trailing stops: enabled")
	assert.Contains(t, desc, "Follow regime: enabled")
	assert.Contains(t, desc, "reinvest_same")
}

func TestParameterMapper_EntryStyleMapping(t *testing.T) {
	mapper := NewParameterMapper()

	tests := []struct {
		entryStyle        float64
		expectedDipThresh float64
		expectedBreakout  float64
		expectedBias      string
	}{
		{0.0, 1.0, 0.0, "dip buyer"},      // Pure dip buyer
		{0.2, 0.8, 0.2, "dip buyer"},      // Dip buyer oriented
		{0.5, 0.5, 0.5, "breakout buyer"}, // Neutral (equal=breakout)
		{0.8, 0.2, 0.8, "breakout buyer"}, // Breakout buyer oriented
		{1.0, 0.0, 1.0, "breakout buyer"}, // Pure breakout buyer
	}

	for _, tt := range tests {
		settings := SatelliteSettings{EntryStyle: tt.entryStyle}
		params := mapper.MapSettingsToParameters(settings)

		assert.InDelta(t, tt.expectedDipThresh, params.BuyDipThreshold, 0.0001)
		assert.InDelta(t, tt.expectedBreakout, params.BreakoutThreshold, 0.0001)

		desc := mapper.DescribeParameters(params)
		assert.Contains(t, desc, tt.expectedBias)
	}
}

func TestParameterMapper_BoundaryValues(t *testing.T) {
	mapper := NewParameterMapper()

	// All sliders at 0.0
	minSettings := SatelliteSettings{
		RiskAppetite:   0.0,
		HoldDuration:   0.0,
		EntryStyle:     0.0,
		PositionSpread: 0.0,
		ProfitTaking:   0.0,
	}
	minParams := mapper.MapSettingsToParameters(minSettings)

	assert.Equal(t, 0.15, minParams.PositionSizeMax)
	assert.Equal(t, 0.05, minParams.StopLossPct)
	assert.Equal(t, 1, minParams.TargetHoldDays)
	assert.Equal(t, 3, minParams.MaxPositions)
	assert.Equal(t, 0.05, minParams.TakeProfitThreshold)
	assert.Equal(t, 0.10, minParams.TrailingStopDistance)

	// All sliders at 1.0
	maxSettings := SatelliteSettings{
		RiskAppetite:   1.0,
		HoldDuration:   1.0,
		EntryStyle:     1.0,
		PositionSpread: 1.0,
		ProfitTaking:   1.0,
	}
	maxParams := mapper.MapSettingsToParameters(maxSettings)

	assert.Equal(t, 0.40, maxParams.PositionSizeMax)
	assert.Equal(t, 0.20, maxParams.StopLossPct)
	assert.Equal(t, 181, maxParams.TargetHoldDays)
	assert.Equal(t, 23, maxParams.MaxPositions)
	assert.Equal(t, 0.30, maxParams.TakeProfitThreshold)
	assert.Equal(t, 0.0, maxParams.TrailingStopDistance)
}
