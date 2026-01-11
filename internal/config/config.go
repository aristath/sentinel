// Package config provides configuration management functionality.
package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"github.com/aristath/sentinel/internal/deployment"
	"github.com/aristath/sentinel/internal/modules/settings"
	"github.com/joho/godotenv"
)

// Config holds application configuration
type Config struct {
	DataDir             string // Base directory for all databases (defaults to "/home/arduino/data", always absolute)
	EvaluatorServiceURL string
	TradernetAPIKey     string
	TradernetAPISecret  string
	GitHubToken         string // GitHub personal access token for artifact downloads
	LogLevel            string
	Port                int
	DevMode             bool
	Deployment          *DeploymentConfig
}

// DeploymentConfig holds deployment automation configuration (config package version)
type DeploymentConfig struct {
	Enabled                bool
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
	// GitHub artifact deployment settings
	UseGitHubArtifacts bool   // Use GitHub Actions artifacts instead of building on-device
	GitHubWorkflowName string // e.g., "build-go.yml"
	GitHubArtifactName string // e.g., "sentinel-arm64"
	GitHubBranch       string // Branch to check for builds (defaults to GitBranch if empty)
	GitHubRepo         string // GitHub repository in format "owner/repo" (e.g., "aristath/sentinel")
}

// ToDeploymentConfig converts config.DeploymentConfig to deployment.DeploymentConfig
// githubToken is passed separately since it comes from Config.GitHubToken (not DeploymentConfig)
func (c *DeploymentConfig) ToDeploymentConfig(githubToken string) *deployment.DeploymentConfig {
	// Determine GitHub branch (use GitHubBranch if set, otherwise GitBranch)
	githubBranch := c.GitHubBranch
	if githubBranch == "" {
		githubBranch = c.GitBranch
	}

	return &deployment.DeploymentConfig{
		Enabled:                c.Enabled,
		DeployDir:              c.DeployDir,
		APIPort:                c.APIPort,
		APIHost:                c.APIHost,
		LockTimeout:            time.Duration(c.LockTimeout) * time.Second,
		HealthCheckTimeout:     time.Duration(c.HealthCheckTimeout) * time.Second,
		HealthCheckMaxAttempts: c.HealthCheckMaxAttempts,
		GitBranch:              c.GitBranch,
		TraderConfig: deployment.GoServiceConfig{
			Name:        "sentinel",
			BuildPath:   "cmd/server",
			BinaryName:  c.TraderBinaryName,
			ServiceName: c.TraderServiceName,
		},
		DockerComposePath:  c.DockerComposePath,
		UseGitHubArtifacts: c.UseGitHubArtifacts,
		GitHubWorkflowName: c.GitHubWorkflowName,
		GitHubArtifactName: c.GitHubArtifactName,
		GitHubBranch:       githubBranch,
		GitHubRepo:         c.GitHubRepo,
		GitHubToken:        githubToken,
	}
}

// Load reads configuration from environment variables
func Load() (*Config, error) {
	// Load .env file if it exists
	_ = godotenv.Load()

	// Determine data directory with fallback logic
	// 1. Check TRADER_DATA_DIR environment variable
	// 2. If not set, default to /home/arduino/data
	// 3. Always resolve to absolute path
	// 4. Ensure directory exists
	dataDir := getEnv("TRADER_DATA_DIR", "")
	if dataDir == "" {
		// Default fallback to absolute path
		dataDir = "/home/arduino/data"
	}

	// Always resolve to absolute path
	absDataDir, err := filepath.Abs(dataDir)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve data directory path: %w", err)
	}

	// Ensure directory exists
	if err := os.MkdirAll(absDataDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create data directory: %w", err)
	}

	cfg := &Config{
		DataDir:             absDataDir,
		Port:                getEnvAsInt("GO_PORT", 8001), // Default 8001 (Python uses 8000)
		DevMode:             getEnvAsBool("DEV_MODE", false),
		EvaluatorServiceURL: getEnv("EVALUATOR_SERVICE_URL", "http://localhost:9000"), // Evaluator-go microservice on 9000
		TradernetAPIKey:     getEnv("TRADERNET_API_KEY", ""),
		TradernetAPISecret:  getEnv("TRADERNET_API_SECRET", ""),
		GitHubToken:         getEnv("GITHUB_TOKEN", ""), // GitHub token for deployment
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

	// Get GitHub token from settings DB
	githubToken, err := settingsRepo.Get("github_token")
	if err != nil {
		return fmt.Errorf("failed to get github_token from settings: %w", err)
	}
	// Only use settings DB value if it's not empty (settings DB takes precedence)
	if githubToken != nil && *githubToken != "" {
		c.GitHubToken = *githubToken
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
		Enabled:                true, // Enabled by default
		DeployDir:              ".",  // Current directory (resolved to WorkingDirectory)
		APIPort:                8001,
		APIHost:                "localhost",
		LockTimeout:            120, // 2 minutes
		HealthCheckTimeout:     10,
		HealthCheckMaxAttempts: 3,
		GitBranch:              "", // Empty = auto-detect at runtime (deployment manager has fallback logic)
		TraderBinaryName:       "sentinel",
		TraderServiceName:      "sentinel",
		DockerComposePath:      "",
		// GitHub artifact deployment (REQUIRED - no on-device building)
		// This saves 1GB+ disk space by not requiring Go toolchain on device
		UseGitHubArtifacts: true, // Always true - artifact deployment is required
		GitHubWorkflowName: getEnv("GITHUB_WORKFLOW_NAME", "build-go.yml"),
		GitHubArtifactName: getEnv("GITHUB_ARTIFACT_NAME", "sentinel-arm64"),
		GitHubBranch:       getEnv("GITHUB_BRANCH", ""),                // Defaults to GitBranch if empty
		GitHubRepo:         getEnv("GITHUB_REPO", "aristath/sentinel"), // GitHub repository
	}
}
