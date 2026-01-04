package satellites

import "fmt"

// Strategy preset definitions
// Faithful translation from Python: app/modules/satellites/domain/strategy_presets.py

var (
	// MomentumHunter - Aggressive breakout trading with trailing stops
	MomentumHunter = map[string]interface{}{
		"risk_appetite":         0.7,
		"hold_duration":         0.3,
		"entry_style":           0.8,
		"position_spread":       0.4,
		"profit_taking":         0.6,
		"trailing_stops":        true,
		"follow_regime":         true,
		"auto_harvest":          false,
		"pause_high_volatility": false,
		"dividend_handling":     "reinvest_same",
	}

	// SteadyEddy - Conservative buy-and-hold approach
	SteadyEddy = map[string]interface{}{
		"risk_appetite":         0.3,
		"hold_duration":         0.8,
		"entry_style":           0.3,
		"position_spread":       0.7,
		"profit_taking":         0.3,
		"trailing_stops":        false,
		"follow_regime":         false,
		"auto_harvest":          false,
		"pause_high_volatility": false,
		"dividend_handling":     "reinvest_same",
	}

	// DipBuyer - Opportunistic value investing
	DipBuyer = map[string]interface{}{
		"risk_appetite":         0.5,
		"hold_duration":         0.7,
		"entry_style":           0.2,
		"position_spread":       0.6,
		"profit_taking":         0.4,
		"trailing_stops":        false,
		"follow_regime":         false,
		"auto_harvest":          false,
		"pause_high_volatility": false,
		"dividend_handling":     "reinvest_same",
	}

	// DividendCatcher - Income-focused with cash accumulation
	DividendCatcher = map[string]interface{}{
		"risk_appetite":         0.4,
		"hold_duration":         0.2,
		"entry_style":           0.5,
		"position_spread":       0.8,
		"profit_taking":         0.8,
		"trailing_stops":        false,
		"follow_regime":         false,
		"auto_harvest":          false,
		"pause_high_volatility": false,
		"dividend_handling":     "accumulate_cash",
	}

	// StrategyPresets is the registry of all available presets
	StrategyPresets = map[string]map[string]interface{}{
		"momentum_hunter":  MomentumHunter,
		"steady_eddy":      SteadyEddy,
		"dip_buyer":        DipBuyer,
		"dividend_catcher": DividendCatcher,
	}
)

// GetPreset returns a strategy preset by name
//
// Args:
//
//	presetName: Name of the preset (momentum_hunter, steady_eddy, dip_buyer, dividend_catcher)
//
// Returns:
//
//	Dictionary of satellite settings
//
// Errors:
//
//	Returns error if preset_name is not recognized
func GetPreset(presetName string) (map[string]interface{}, error) {
	preset, exists := StrategyPresets[presetName]
	if !exists {
		return nil, fmt.Errorf(
			"unknown preset '%s'. Available: momentum_hunter, steady_eddy, dip_buyer, dividend_catcher",
			presetName,
		)
	}

	// Return a copy to prevent modifications
	result := make(map[string]interface{})
	for k, v := range preset {
		result[k] = v
	}
	return result, nil
}

// ListPresets returns all available strategy preset names
func ListPresets() []string {
	return []string{"momentum_hunter", "steady_eddy", "dip_buyer", "dividend_catcher"}
}

// GetPresetDescription returns a human-readable description of a preset
func GetPresetDescription(presetName string) (string, error) {
	descriptions := map[string]string{
		"momentum_hunter": "Aggressive breakout trading with trailing stops. " +
			"Targets high-momentum stocks, follows market regime, " +
			"moderate hold duration (30% = ~54 days average). " +
			"Best for bull markets and growth stocks.",
		"steady_eddy": "Conservative buy-and-hold approach. " +
			"Low risk (30%), long hold duration (80% = ~144 days), " +
			"wide diversification. No trailing stops. " +
			"Best for stable dividend payers and blue chips.",
		"dip_buyer": "Opportunistic value investing. " +
			"Buys pullbacks and dips (entry_style=0.2), " +
			"holds for recovery (70% = ~126 days), " +
			"moderate profit taking. " +
			"Best for oversold quality stocks.",
		"dividend_catcher": "Income-focused with cash accumulation. " +
			"Accumulates dividends as cash instead of reinvesting. " +
			"Short hold duration (20% = ~36 days) for ex-div plays, " +
			"wide diversification, aggressive profit taking. " +
			"Best for high-yield dividend strategies.",
	}

	desc, exists := descriptions[presetName]
	if !exists {
		return "", fmt.Errorf(
			"unknown preset '%s'. Available: momentum_hunter, steady_eddy, dip_buyer, dividend_catcher",
			presetName,
		)
	}

	return desc, nil
}

// ApplyPresetToSettings applies a preset to satellite settings
//
// Args:
//
//	settings: Satellite settings to modify
//	presetName: Name of the preset to apply
//
// Returns:
//
//	Modified settings with preset applied
//
// Errors:
//
//	Returns error if preset name is not recognized
func ApplyPresetToSettings(settings *SatelliteSettings, presetName string) error {
	preset, err := GetPreset(presetName)
	if err != nil {
		return err
	}

	// Apply preset values
	settings.RiskAppetite = preset["risk_appetite"].(float64)
	settings.HoldDuration = preset["hold_duration"].(float64)
	settings.EntryStyle = preset["entry_style"].(float64)
	settings.PositionSpread = preset["position_spread"].(float64)
	settings.ProfitTaking = preset["profit_taking"].(float64)
	settings.TrailingStops = preset["trailing_stops"].(bool)
	settings.FollowRegime = preset["follow_regime"].(bool)
	settings.AutoHarvest = preset["auto_harvest"].(bool)
	settings.PauseHighVolatility = preset["pause_high_volatility"].(bool)
	settings.DividendHandling = preset["dividend_handling"].(string)

	presetNameCopy := presetName
	settings.Preset = &presetNameCopy

	return nil
}
