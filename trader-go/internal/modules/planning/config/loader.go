package config

import (
	"fmt"
	"os"

	"github.com/BurntSushi/toml"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// Loader handles loading planner configurations from TOML files.
type Loader struct {
	log zerolog.Logger
}

// NewLoader creates a new configuration loader.
func NewLoader(log zerolog.Logger) *Loader {
	return &Loader{
		log: log.With().Str("component", "config_loader").Logger(),
	}
}

// LoadFromFile loads a planner configuration from a TOML file.
func (l *Loader) LoadFromFile(configPath string) (*domain.PlannerConfiguration, error) {
	l.log.Info().Str("path", configPath).Msg("Loading planner configuration")

	// Check if file exists
	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		return nil, fmt.Errorf("config file not found: %s", configPath)
	}

	// Read and decode TOML file
	var config domain.PlannerConfiguration
	if _, err := toml.DecodeFile(configPath, &config); err != nil {
		return nil, fmt.Errorf("failed to parse TOML config: %w", err)
	}

	// Log loaded configuration summary
	l.log.Info().
		Str("name", config.Name).
		Int("enabled_calculators", len(config.GetEnabledCalculators())).
		Int("enabled_patterns", len(config.GetEnabledPatterns())).
		Int("enabled_generators", len(config.GetEnabledGenerators())).
		Int("enabled_filters", len(config.GetEnabledFilters())).
		Msg("Configuration loaded successfully")

	return &config, nil
}

// LoadFromString loads a planner configuration from a TOML string.
// This is useful for loading configurations from the database.
func (l *Loader) LoadFromString(tomlString string) (*domain.PlannerConfiguration, error) {
	l.log.Debug().Msg("Loading planner configuration from string")

	var config domain.PlannerConfiguration
	if _, err := toml.Decode(tomlString, &config); err != nil {
		return nil, fmt.Errorf("failed to parse TOML config: %w", err)
	}

	l.log.Info().
		Str("name", config.Name).
		Msg("Configuration loaded from string")

	return &config, nil
}

// SaveToFile saves a planner configuration to a TOML file.
func (l *Loader) SaveToFile(config *domain.PlannerConfiguration, configPath string) error {
	l.log.Info().
		Str("path", configPath).
		Str("name", config.Name).
		Msg("Saving planner configuration")

	// Create file
	file, err := os.Create(configPath)
	if err != nil {
		return fmt.Errorf("failed to create config file: %w", err)
	}
	defer file.Close()

	// Encode to TOML
	encoder := toml.NewEncoder(file)
	if err := encoder.Encode(config); err != nil {
		return fmt.Errorf("failed to encode config to TOML: %w", err)
	}

	l.log.Info().Msg("Configuration saved successfully")
	return nil
}

// ToString converts a planner configuration to a TOML string.
func (l *Loader) ToString(config *domain.PlannerConfiguration) (string, error) {
	var buffer string
	encoder := toml.NewEncoder(&stringWriter{buf: &buffer})
	if err := encoder.Encode(config); err != nil {
		return "", fmt.Errorf("failed to encode config to TOML: %w", err)
	}
	return buffer, nil
}

// stringWriter is a simple writer that writes to a string.
type stringWriter struct {
	buf *string
}

func (sw *stringWriter) Write(p []byte) (n int, err error) {
	*sw.buf += string(p)
	return len(p), nil
}
