package satellites

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestStrategyPresets_GetPreset_MomentumHunter(t *testing.T) {
	preset, err := GetPreset("momentum_hunter")
	require.NoError(t, err)
	require.NotNil(t, preset)

	assert.Equal(t, 0.7, preset["risk_appetite"])
	assert.Equal(t, 0.3, preset["hold_duration"])
	assert.Equal(t, 0.8, preset["entry_style"])
	assert.Equal(t, 0.4, preset["position_spread"])
	assert.Equal(t, 0.6, preset["profit_taking"])
	assert.Equal(t, true, preset["trailing_stops"])
	assert.Equal(t, true, preset["follow_regime"])
	assert.Equal(t, false, preset["auto_harvest"])
	assert.Equal(t, false, preset["pause_high_volatility"])
	assert.Equal(t, "reinvest_same", preset["dividend_handling"])
}

func TestStrategyPresets_GetPreset_SteadyEddy(t *testing.T) {
	preset, err := GetPreset("steady_eddy")
	require.NoError(t, err)
	require.NotNil(t, preset)

	assert.Equal(t, 0.3, preset["risk_appetite"])
	assert.Equal(t, 0.8, preset["hold_duration"])
	assert.Equal(t, 0.3, preset["entry_style"])
	assert.Equal(t, 0.7, preset["position_spread"])
	assert.Equal(t, 0.3, preset["profit_taking"])
	assert.Equal(t, false, preset["trailing_stops"])
	assert.Equal(t, false, preset["follow_regime"])
}

func TestStrategyPresets_GetPreset_DipBuyer(t *testing.T) {
	preset, err := GetPreset("dip_buyer")
	require.NoError(t, err)
	require.NotNil(t, preset)

	assert.Equal(t, 0.5, preset["risk_appetite"])
	assert.Equal(t, 0.7, preset["hold_duration"])
	assert.Equal(t, 0.2, preset["entry_style"]) // Dip buyer → low entry style
	assert.Equal(t, 0.6, preset["position_spread"])
	assert.Equal(t, 0.4, preset["profit_taking"])
}

func TestStrategyPresets_GetPreset_DividendCatcher(t *testing.T) {
	preset, err := GetPreset("dividend_catcher")
	require.NoError(t, err)
	require.NotNil(t, preset)

	assert.Equal(t, 0.4, preset["risk_appetite"])
	assert.Equal(t, 0.2, preset["hold_duration"]) // Short duration
	assert.Equal(t, 0.5, preset["entry_style"])
	assert.Equal(t, 0.8, preset["position_spread"]) // Wide diversification
	assert.Equal(t, 0.8, preset["profit_taking"])   // Aggressive profit taking
	assert.Equal(t, "accumulate_cash", preset["dividend_handling"])
}

func TestStrategyPresets_GetPreset_InvalidName(t *testing.T) {
	preset, err := GetPreset("invalid_preset")
	assert.Error(t, err)
	assert.Nil(t, preset)
	assert.Contains(t, err.Error(), "unknown preset")
}

func TestStrategyPresets_ListPresets(t *testing.T) {
	presets := ListPresets()
	assert.Len(t, presets, 4)
	assert.Contains(t, presets, "momentum_hunter")
	assert.Contains(t, presets, "steady_eddy")
	assert.Contains(t, presets, "dip_buyer")
	assert.Contains(t, presets, "dividend_catcher")
}

func TestStrategyPresets_GetPresetDescription(t *testing.T) {
	desc, err := GetPresetDescription("momentum_hunter")
	require.NoError(t, err)
	assert.Contains(t, desc, "Aggressive breakout trading")
	assert.Contains(t, desc, "trailing stops")

	desc, err = GetPresetDescription("steady_eddy")
	require.NoError(t, err)
	assert.Contains(t, desc, "Conservative buy-and-hold")
	assert.Contains(t, desc, "30%")

	desc, err = GetPresetDescription("dip_buyer")
	require.NoError(t, err)
	assert.Contains(t, desc, "Opportunistic value")
	assert.Contains(t, desc, "pullbacks and dips")

	desc, err = GetPresetDescription("dividend_catcher")
	require.NoError(t, err)
	assert.Contains(t, desc, "Income-focused")
	assert.Contains(t, desc, "cash accumulation")
}

func TestStrategyPresets_GetPresetDescription_InvalidName(t *testing.T) {
	desc, err := GetPresetDescription("invalid_preset")
	assert.Error(t, err)
	assert.Empty(t, desc)
	assert.Contains(t, err.Error(), "unknown preset")
}

func TestStrategyPresets_ApplyPresetToSettings(t *testing.T) {
	settings := NewSatelliteSettings("sat1")

	// Apply momentum hunter preset
	err := ApplyPresetToSettings(settings, "momentum_hunter")
	require.NoError(t, err)

	assert.Equal(t, 0.7, settings.RiskAppetite)
	assert.Equal(t, 0.3, settings.HoldDuration)
	assert.Equal(t, 0.8, settings.EntryStyle)
	assert.Equal(t, 0.4, settings.PositionSpread)
	assert.Equal(t, 0.6, settings.ProfitTaking)
	assert.True(t, settings.TrailingStops)
	assert.True(t, settings.FollowRegime)
	assert.False(t, settings.AutoHarvest)
	assert.False(t, settings.PauseHighVolatility)
	assert.Equal(t, "reinvest_same", settings.DividendHandling)
	require.NotNil(t, settings.Preset)
	assert.Equal(t, "momentum_hunter", *settings.Preset)
}

func TestStrategyPresets_ApplyPresetToSettings_InvalidPreset(t *testing.T) {
	settings := NewSatelliteSettings("sat1")

	err := ApplyPresetToSettings(settings, "invalid_preset")
	assert.Error(t, err)
}

func TestStrategyPresets_GetPresetReturnsCopy(t *testing.T) {
	// Get preset
	preset1, err := GetPreset("momentum_hunter")
	require.NoError(t, err)

	// Modify the returned map
	preset1["risk_appetite"] = 0.99

	// Get preset again
	preset2, err := GetPreset("momentum_hunter")
	require.NoError(t, err)

	// Should be unchanged (copy was returned)
	assert.Equal(t, 0.7, preset2["risk_appetite"])
}

func TestStrategyPresets_AllPresetsAvailable(t *testing.T) {
	// Verify all 4 presets are in registry
	assert.Len(t, StrategyPresets, 4)
	assert.Contains(t, StrategyPresets, "momentum_hunter")
	assert.Contains(t, StrategyPresets, "steady_eddy")
	assert.Contains(t, StrategyPresets, "dip_buyer")
	assert.Contains(t, StrategyPresets, "dividend_catcher")

	// Verify each preset has all required fields
	for name, preset := range StrategyPresets {
		t.Run(name, func(t *testing.T) {
			assert.Contains(t, preset, "risk_appetite")
			assert.Contains(t, preset, "hold_duration")
			assert.Contains(t, preset, "entry_style")
			assert.Contains(t, preset, "position_spread")
			assert.Contains(t, preset, "profit_taking")
			assert.Contains(t, preset, "trailing_stops")
			assert.Contains(t, preset, "follow_regime")
			assert.Contains(t, preset, "auto_harvest")
			assert.Contains(t, preset, "pause_high_volatility")
			assert.Contains(t, preset, "dividend_handling")
		})
	}
}
