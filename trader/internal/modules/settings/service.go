package settings

import (
	"fmt"
	"strconv"

	"github.com/rs/zerolog"
)

// Service provides settings business logic
type Service struct {
	repo *Repository
	log  zerolog.Logger
}

// NewService creates a new settings service
func NewService(repo *Repository, log zerolog.Logger) *Service {
	return &Service{
		repo: repo,
		log:  log.With().Str("service", "settings").Logger(),
	}
}

// GetAll retrieves all settings with defaults
func (s *Service) GetAll() (map[string]interface{}, error) {
	dbValues, err := s.repo.GetAll()
	if err != nil {
		return nil, err
	}

	result := make(map[string]interface{})
	for key, defaultValue := range SettingDefaults {
		if dbValue, exists := dbValues[key]; exists {
			// Check if this is a string setting
			if StringSettings[key] {
				result[key] = dbValue
			} else {
				// Parse as float
				if floatVal, err := strconv.ParseFloat(dbValue, 64); err == nil {
					result[key] = floatVal
				} else {
					result[key] = defaultValue
				}
			}
		} else {
			result[key] = defaultValue
		}
	}

	return result, nil
}

// Get retrieves a setting value with fallback to default
func (s *Service) Get(key string) (interface{}, error) {
	dbValue, err := s.repo.Get(key)
	if err != nil {
		return nil, err
	}

	if dbValue != nil {
		// Check if this is a string setting
		if StringSettings[key] {
			return *dbValue, nil
		}
		// Parse as float
		if floatVal, err := strconv.ParseFloat(*dbValue, 64); err == nil {
			return floatVal, nil
		}
	}

	// Return default
	defaultValue, exists := SettingDefaults[key]
	if !exists {
		return nil, fmt.Errorf("unknown setting: %s", key)
	}
	return defaultValue, nil
}

// Set updates a setting value with validation
// Returns true if this is a first-time credential setup (both key and secret were previously empty)
func (s *Service) Set(key string, value interface{}) (bool, error) {
	// Check if setting exists in defaults
	if _, exists := SettingDefaults[key]; !exists {
		return false, fmt.Errorf("unknown setting: %s", key)
	}

	// Special handling for trading_mode
	if key == "trading_mode" {
		mode, ok := value.(string)
		if !ok {
			return false, fmt.Errorf("trading_mode must be a string")
		}
		err := s.SetTradingMode(mode)
		return false, err
	}

	// Special validation for market regime cash reserves
	if key == "market_regime_bull_cash_reserve" ||
		key == "market_regime_bear_cash_reserve" ||
		key == "market_regime_sideways_cash_reserve" {
		floatVal, ok := value.(float64)
		if !ok {
			return false, fmt.Errorf("%s must be a float", key)
		}
		if floatVal < 0.01 || floatVal > 0.40 {
			return false, fmt.Errorf("%s must be between 1%% (0.01) and 40%% (0.40)", key)
		}
	}

	// Special validation for virtual_test_cash
	if key == "virtual_test_cash" {
		floatVal, ok := value.(float64)
		if !ok {
			return false, fmt.Errorf("virtual_test_cash must be a float")
		}
		if floatVal < 0 {
			return false, fmt.Errorf("virtual_test_cash must be non-negative")
		}
	}

	// Check if this is a first-time credential setup
	// We'll determine this after saving, by checking if both credentials are now set
	// and at least one was previously empty
	isFirstTimeSetup := false
	if key == "tradernet_api_key" || key == "tradernet_api_secret" {
		// Get previous values before saving
		prevKey, _ := s.repo.Get("tradernet_api_key")
		prevSecret, _ := s.repo.Get("tradernet_api_secret")

		wasKeyEmpty := prevKey == nil || *prevKey == ""
		wasSecretEmpty := prevSecret == nil || *prevSecret == ""

		// Get the new value as string
		var newValueStr string
		switch v := value.(type) {
		case string:
			newValueStr = v
		default:
			// For non-string values, convert to string
			newValueStr = fmt.Sprintf("%v", v)
		}

		// Only proceed with first-time check if we're setting a non-empty value
		if newValueStr != "" {
			// This could be first-time setup if at least one credential was empty
			// We'll verify after saving that both are now set
			isFirstTimeSetup = wasKeyEmpty || wasSecretEmpty
		}
	}

	// Convert to string for storage
	var strValue string
	switch v := value.(type) {
	case string:
		strValue = v
	case float64:
		strValue = fmt.Sprintf("%f", v)
	case int:
		strValue = fmt.Sprintf("%d", v)
	default:
		return false, fmt.Errorf("unsupported value type for setting %s", key)
	}

	err := s.repo.Set(key, strValue, nil)
	if err != nil {
		return false, err
	}

	// Final check: if this was a credential update, verify both are now set
	// Onboarding should only trigger when BOTH credentials are set for the first time
	if (key == "tradernet_api_key" || key == "tradernet_api_secret") && isFirstTimeSetup {
		// Verify both credentials are now set
		currentKey, _ := s.repo.Get("tradernet_api_key")
		currentSecret, _ := s.repo.Get("tradernet_api_secret")

		keySet := currentKey != nil && *currentKey != ""
		secretSet := currentSecret != nil && *currentSecret != ""

		// Only return true if both are now set (this means the second credential was just set)
		// This ensures onboarding triggers only once, when the second credential is saved
		isFirstTimeSetup = keySet && secretSet
	}

	return isFirstTimeSetup, nil
}

// GetTradingMode retrieves the current trading mode
func (s *Service) GetTradingMode() (string, error) {
	value, err := s.repo.Get("trading_mode")
	if err != nil {
		return "", err
	}

	if value != nil {
		mode := *value
		if mode == "live" || mode == "research" {
			return mode, nil
		}
	}

	// Return default
	defaultMode, _ := SettingDefaults["trading_mode"].(string)
	return defaultMode, nil
}

// SetWithOnboarding updates a setting and returns whether onboarding should be triggered
// This is a convenience method that wraps Set() for handlers that need onboarding detection
func (s *Service) SetWithOnboarding(key string, value interface{}) (bool, error) {
	return s.Set(key, value)
}

// SetTradingMode sets the trading mode with validation
func (s *Service) SetTradingMode(mode string) error {
	if mode != "live" && mode != "research" {
		return fmt.Errorf("invalid trading mode: %s. Must be 'live' or 'research'", mode)
	}

	// Validate credentials when switching to live mode
	if mode == "live" {
		apiKey, err := s.repo.Get("tradernet_api_key")
		if err != nil {
			return fmt.Errorf("failed to check tradernet_api_key: %w", err)
		}
		apiSecret, err := s.repo.Get("tradernet_api_secret")
		if err != nil {
			return fmt.Errorf("failed to check tradernet_api_secret: %w", err)
		}

		if apiKey == nil || *apiKey == "" || apiSecret == nil || *apiSecret == "" {
			return fmt.Errorf("tradernet API credentials must be configured before switching to live mode")
		}
	}

	desc := "Trading mode: 'live' or 'research'"
	return s.repo.Set("trading_mode", mode, &desc)
}

// ToggleTradingMode toggles between live and research modes
func (s *Service) ToggleTradingMode() (string, string, error) {
	currentMode, err := s.GetTradingMode()
	if err != nil {
		return "", "", err
	}

	newMode := "research"
	if currentMode == "research" {
		newMode = "live"
	}

	// Clear TEST currency when switching to live mode (safety)
	if newMode == "live" {
		if err := s.repo.SetFloat("virtual_test_cash", 0.0); err != nil {
			s.log.Warn().Err(err).Msg("Failed to clear virtual_test_cash when switching to live mode")
		} else {
			s.log.Info().Msg("Cleared virtual_test_cash when switching to live mode")
		}
	}

	if err := s.SetTradingMode(newMode); err != nil {
		return "", "", err
	}

	return newMode, currentMode, nil
}
