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
	PythonServiceURL    string
	UnifiedServiceURL   string // Unified microservice (pypfopt, tradernet, yfinance) on 9000
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
	APIPort                int
	APIHost                string
	LockTimeout            int // in seconds
	HealthCheckTimeout     int // in seconds
	HealthCheckMaxAttempts int
	GitBranch              string
	TraderBinaryName       string
	TraderServiceName      string
	DockerComposePath      string
	MicroservicesEnabled   bool
	// GitHub artifact deployment settings
	UseGitHubArtifacts bool   // Use GitHub Actions artifacts instead of building on-device
	GitHubWorkflowName string // e.g., "build-go.yml"
	GitHubArtifactName string // e.g., "trader-arm64"
	GitHubBranch       string // Branch to check for builds (defaults to GitBranch if empty)
}

// ToDeploymentConfig converts config.DeploymentConfig to deployment.DeploymentConfig
func (c *DeploymentConfig) ToDeploymentConfig() *deployment.DeploymentConfig {
	// Determine GitHub branch (use GitHubBranch if set, otherwise GitBranch)
	githubBranch := c.GitHubBranch
	if githubBranch == "" {
		githubBranch = c.GitBranch
	}

	return &deployment.DeploymentConfig{
		Enabled:                c.Enabled,
		RepoDir:                c.RepoDir,
		DeployDir:              c.DeployDir,
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
		DockerComposePath:    c.DockerComposePath,
		MicroservicesEnabled: c.MicroservicesEnabled,
		UseGitHubArtifacts:   c.UseGitHubArtifacts,
		GitHubWorkflowName:   c.GitHubWorkflowName,
		GitHubArtifactName:   c.GitHubArtifactName,
		GitHubBranch:         githubBranch,
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

	cfg := &Config{
		DataDir:             dataDir,
		Port:                getEnvAsInt("GO_PORT", 8001), // Default 8001 (Python uses 8000)
		DevMode:             getEnvAsBool("DEV_MODE", false),
		PythonServiceURL:    getEnv("PYTHON_SERVICE_URL", "http://localhost:8000"),    // Python on 8000
		UnifiedServiceURL:   getEnv("UNIFIED_SERVICE_URL", "http://localhost:9000"),   // Unified microservice on 9000
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
// Settings DB values take precedence over environment variables
func (c *Config) UpdateFromSettings(settingsRepo *settings.Repository) error {
	// Try to get credentials from settings DB
	apiKey, err := settingsRepo.Get("tradernet_api_key")
	if err != nil {
		return fmt.Errorf("failed to get tradernet_api_key from settings: %w", err)
	}
	// Only use settings DB value if it's not empty (settings DB takes precedence)
	if apiKey != nil && *apiKey != "" {
		c.TradernetAPIKey = *apiKey
	}
	// If settings DB value is empty, keep the env var value (if any) as fallback

	apiSecret, err := settingsRepo.Get("tradernet_api_secret")
	if err != nil {
		return fmt.Errorf("failed to get tradernet_api_secret from settings: %w", err)
	}
	// Only use settings DB value if it's not empty (settings DB takes precedence)
	if apiSecret != nil && *apiSecret != "" {
		c.TradernetAPISecret = *apiSecret
	}
	// If settings DB value is empty, keep the env var value (if any) as fallback

	return nil
}

// Validate checks if required configuration is present
func (c *Config) Validate() error {

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
		Enabled:                true,                     // Enabled by default
		RepoDir:                "/home/arduino/app/repo", // Absolute path to repo
		DeployDir:              ".",                      // Current directory (resolved to WorkingDirectory)
		APIPort:                8001,
		APIHost:                "localhost",
		LockTimeout:            120, // 2 minutes
		HealthCheckTimeout:     10,
		HealthCheckMaxAttempts: 3,
		GitBranch:              "", // Empty = auto-detect at runtime (deployment manager has fallback logic)
		TraderBinaryName:       "trader",
		TraderServiceName:      "trader",
		DockerComposePath:      "",
		MicroservicesEnabled:   true,
		// GitHub artifact deployment (REQUIRED - no on-device building)
		// This saves 1GB+ disk space by not requiring Go toolchain on device
		UseGitHubArtifacts: true, // Always true - artifact deployment is required
		GitHubWorkflowName: getEnv("GITHUB_WORKFLOW_NAME", "build-go.yml"),
		GitHubArtifactName: getEnv("GITHUB_ARTIFACT_NAME", "trader-arm64"),
		GitHubBranch:       getEnv("GITHUB_BRANCH", ""), // Defaults to GitBranch if empty
	}
}
