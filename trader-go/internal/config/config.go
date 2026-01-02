package config

import (
	"fmt"
	"os"
	"strconv"

	"github.com/joho/godotenv"
)

// Config holds application configuration
type Config struct {
	// Server
	Port    int
	DevMode bool

	// Database
	DatabasePath string

	// Python Services (temporary during migration)
	PythonServiceURL string

	// Tradernet API
	TradernetAPIKey    string
	TradernetAPISecret string

	// Logging
	LogLevel string
}

// Load reads configuration from environment variables
func Load() (*Config, error) {
	// Load .env file if it exists
	_ = godotenv.Load()

	cfg := &Config{
		Port:               getEnvAsInt("GO_PORT", 8001),        // Default 8001 (Python uses 8000)
		DevMode:            getEnvAsBool("DEV_MODE", false),
		DatabasePath:       getEnv("DATABASE_PATH", "./data/portfolio.db"),
		PythonServiceURL:   getEnv("PYTHON_SERVICE_URL", "http://localhost:8000"), // Python on 8000
		TradernetAPIKey:    getEnv("TRADERNET_API_KEY", ""),
		TradernetAPISecret: getEnv("TRADERNET_API_SECRET", ""),
		LogLevel:           getEnv("LOG_LEVEL", "info"),
	}

	// Validate required fields
	if err := cfg.Validate(); err != nil {
		return nil, err
	}

	return cfg, nil
}

// Validate checks if required configuration is present
func (c *Config) Validate() error {
	if c.DatabasePath == "" {
		return fmt.Errorf("DATABASE_PATH is required")
	}

	// Note: Tradernet credentials optional for research mode
	// if c.TradernetAPIKey == "" || c.TradernetAPISecret == "" {
	//     return fmt.Errorf("Tradernet API credentials required")
	// }

	return nil
}

// Helper functions
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvAsInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intVal, err := strconv.Atoi(value); err == nil {
			return intVal
		}
	}
	return defaultValue
}

func getEnvAsBool(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		if boolVal, err := strconv.ParseBool(value); err == nil {
			return boolVal
		}
	}
	return defaultValue
}
