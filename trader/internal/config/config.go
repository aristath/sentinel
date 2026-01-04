package config

import (
	"fmt"
	"os"
	"strconv"
	"time"

	"github.com/aristath/arduino-trader/internal/deployment"
	"github.com/aristath/arduino-trader/internal/modules/settings"
	"github.com/joho/godotenv"
)

// Config holds application configuration
type Config struct {
	DataDir             string // Base directory for all databases (defaults to "../data" or "./data")
	DatabasePath        string // Path to config.db (deprecated, use DataDir + "/config.db")
	HistoryPath         string // Path to per-symbol history databases
	PythonServiceURL    string
	TradernetServiceURL string
	PyPFOptServiceURL   string
	EvaluatorServiceURL string
	TradernetAPIKey     string
	TradernetAPISecret  string
	LogLevel            string
	Port                int
	DevMode             bool
	Deployment          *DeploymentConfig
}

// DeploymentConfig holds deployment automation configuration (config package version)
type DeploymentConfig struct {
	Enabled                bool
	RepoDir                string
	DeployDir              string
	StaticDir              string // Path for static assets (app/static)
	APIPort                int
	APIHost                string
	LockTimeout            int // in seconds
	HealthCheckTimeout     int // in seconds
	HealthCheckMaxAttempts int
	GitBranch              string
	TraderBinaryName       string
	TraderServiceName      string
	BridgeBinaryName       string
	BridgeServiceName      string
	DockerComposePath      string
	MicroservicesEnabled   bool
}

// ToDeploymentConfig converts config.DeploymentConfig to deployment.DeploymentConfig
func (c *DeploymentConfig) ToDeploymentConfig() *deployment.DeploymentConfig {
	return &deployment.DeploymentConfig{
		Enabled:                c.Enabled,
		RepoDir:                c.RepoDir,
		DeployDir:              c.DeployDir,
		StaticDir:              c.StaticDir,
		APIPort:                c.APIPort,
		APIHost:                c.APIHost,
		LockTimeout:            time.Duration(c.LockTimeout) * time.Second,
		HealthCheckTimeout:     time.Duration(c.HealthCheckTimeout) * time.Second,
		HealthCheckMaxAttempts: c.HealthCheckMaxAttempts,
		GitBranch:              c.GitBranch,
		TraderConfig: deployment.GoServiceConfig{
			Name:        "trader",
			BuildPath:   "trader/cmd/server",
			BinaryName:  c.TraderBinaryName,
			ServiceName: c.TraderServiceName,
		},
		DisplayBridgeConfig: deployment.GoServiceConfig{
			Name:        "display-bridge",
			BuildPath:   "display/bridge",
			BinaryName:  c.BridgeBinaryName,
			ServiceName: c.BridgeServiceName,
		},
		DockerComposePath:    c.DockerComposePath,
		MicroservicesEnabled: c.MicroservicesEnabled,
	}
}

// Load reads configuration from environment variables
func Load() (*Config, error) {
	// Load .env file if it exists
	_ = godotenv.Load()

	// Determine data directory with fallback logic
	dataDir := getEnv("DATA_DIR", "")
	if dataDir == "" {
		// Try to find data directory - check ../data first (when running from trader/), then ./data
		if _, err := os.Stat("../data"); err == nil {
			dataDir = "../data"
		} else if _, err := os.Stat("./data"); err == nil {
			dataDir = "./data"
		} else {
			// Default fallback
			dataDir = "../data"
		}
	}

	// Legacy DatabasePath support (for config.db)
	databasePath := getEnv("DATABASE_PATH", "")
	if databasePath == "" {
		databasePath = dataDir + "/config.db"
	}

	cfg := &Config{
		DataDir:             dataDir,
		Port:                getEnvAsInt("GO_PORT", 8001), // Default 8001 (Python uses 8000)
		DevMode:             getEnvAsBool("DEV_MODE", false),
		DatabasePath:        databasePath,
		HistoryPath:         getEnv("HISTORY_PATH", dataDir+"/history"),               // Per-symbol price databases
		PythonServiceURL:    getEnv("PYTHON_SERVICE_URL", "http://localhost:8000"),    // Python on 8000
		TradernetServiceURL: getEnv("TRADERNET_SERVICE_URL", "http://localhost:9002"), // Tradernet microservice on 9002
		PyPFOptServiceURL:   getEnv("PYPFOPT_SERVICE_URL", "http://localhost:9001"),   // PyPFOpt microservice on 9001
		EvaluatorServiceURL: getEnv("EVALUATOR_SERVICE_URL", "http://localhost:9000"), // Evaluator-go microservice on 9000
		TradernetAPIKey:     getEnv("TRADERNET_API_KEY", ""),
		TradernetAPISecret:  getEnv("TRADERNET_API_SECRET", ""),
		LogLevel:            getEnv("LOG_LEVEL", "info"),
		Deployment:          loadDeploymentConfig(),
	}

	// Validate required fields
	if err := cfg.Validate(); err != nil {
		return nil, err
	}

	return cfg, nil
}

// UpdateFromSettings updates configuration from settings database
// This should be called after the config database is initialized
func (c *Config) UpdateFromSettings(settingsRepo *settings.Repository) error {
	// Try to get credentials from settings DB
	apiKey, err := settingsRepo.Get("tradernet_api_key")
	if err != nil {
		return fmt.Errorf("failed to get tradernet_api_key from settings: %w", err)
	}
	if apiKey != nil && *apiKey != "" {
		c.TradernetAPIKey = *apiKey
	}

	apiSecret, err := settingsRepo.Get("tradernet_api_secret")
	if err != nil {
		return fmt.Errorf("failed to get tradernet_api_secret from settings: %w", err)
	}
	if apiSecret != nil && *apiSecret != "" {
		c.TradernetAPISecret = *apiSecret
	}

	return nil
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

// loadDeploymentConfig loads deployment configuration with hardcoded defaults
func loadDeploymentConfig() *DeploymentConfig {
	return &DeploymentConfig{
		Enabled:                true,      // Enabled by default
		RepoDir:                "../repo", // Relative to WorkingDirectory (/home/arduino/app/bin)
		DeployDir:              ".",       // Current directory (app/bin)
		StaticDir:              "../static",
		APIPort:                8001,
		APIHost:                "localhost",
		LockTimeout:            300, // 5 minutes
		HealthCheckTimeout:     10,
		HealthCheckMaxAttempts: 3,
		GitBranch:              "main",
		TraderBinaryName:       "trader",
		TraderServiceName:      "trader",
		BridgeBinaryName:       "display-bridge",
		BridgeServiceName:      "display-bridge",
		DockerComposePath:      "",
		MicroservicesEnabled:   true,
	}
}
