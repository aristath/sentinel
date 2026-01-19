// Package config provides configuration management functionality.
//
// This package handles loading configuration from environment variables (.env file)
// and updating configuration from the settings database. Settings database values
// take precedence over environment variables.
//
// Configuration Loading Order:
// 1. Load from .env file (if exists)
// 2. Load from environment variables
// 3. Update from settings database (takes precedence)
//
// Data Directory Priority (highest to lowest):
// 1. --data-dir CLI flag (if provided)
// 2. TRADER_DATA_DIR environment variable
// 3. /home/arduino/data (default)
//
// This allows credentials and other sensitive settings to be managed via the
// Settings UI instead of requiring .env file changes.
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

// Config holds application configuration.
//
// Configuration is loaded from environment variables and can be updated
// from the settings database. Settings database values take precedence.
type Config struct {
	DataDir             string            // Base directory for all databases (defaults to "/home/arduino/data", always absolute)
	EvaluatorServiceURL string            // Evaluator service URL (legacy - not used in current architecture)
	TradernetAPIKey     string            // Tradernet API key (can be overridden by settings DB)
	TradernetAPISecret  string            // Tradernet API secret (can be overridden by settings DB)
	GitHubToken         string            // GitHub personal access token for artifact downloads (can be overridden by settings DB)
	LogLevel            string            // Log level (debug, info, warn, error)
	Port                int               // HTTP server port (default: 8001)
	DevMode             bool              // Development mode flag
	Deployment          *DeploymentConfig // Deployment automation configuration (optional)
}

// DeploymentConfig holds deployment automation configuration (config package version).
//
// This configuration is used for automated deployment from GitHub Actions artifacts.
// The deployment system monitors GitHub Actions for new builds and automatically
// deploys them to the Arduino Uno Q device.
type DeploymentConfig struct {
	Enabled                bool   // Enable deployment automation
	DeployDir              string // Directory for deployment files
	APIPort                int    // API port for deployment endpoints
	APIHost                string // API host for deployment endpoints
	LockTimeout            int    // Lock timeout in seconds (prevents concurrent deployments)
	HealthCheckTimeout     int    // Health check timeout in seconds
	HealthCheckMaxAttempts int    // Maximum health check attempts before rollback
	GitBranch              string // Git branch to deploy from
	TraderBinaryName       string // Binary name for the Sentinel service
	TraderServiceName      string // Systemd service name
	DockerComposePath      string // Docker Compose file path (if using Docker)
	// GitHub artifact deployment settings
	UseGitHubArtifacts bool   // Use GitHub Actions artifacts instead of building on-device (always true)
	GitHubWorkflowName string // GitHub Actions workflow name (e.g., "build-go.yml")
	GitHubArtifactName string // GitHub Actions artifact name (e.g., "sentinel-arm64")
	GitHubBranch       string // Branch to check for builds (defaults to GitBranch if empty)
	GitHubRepo         string // GitHub repository in format "owner/repo" (e.g., "aristath/sentinel")
}

// ToDeploymentConfig converts config.DeploymentConfig to deployment.DeploymentConfig.
//
// This adapter function converts the config package's DeploymentConfig to the
// deployment package's DeploymentConfig format. The githubToken is passed separately
// since it comes from Config.GitHubToken (not DeploymentConfig).
//
// githubToken - GitHub personal access token for artifact downloads
// Returns *deployment.DeploymentConfig - Deployment configuration for deployment package
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

// Load reads configuration from environment variables.
//
// This function:
// 1. Loads .env file if it exists (via godotenv)
// 2. Reads environment variables with defaults
// 3. Resolves data directory to absolute path
// 4. Creates data directory if it doesn't exist
// 5. Validates configuration
//
// Note: Configuration can be updated later from settings database via UpdateFromSettings().
// Settings database values take precedence over environment variables.
//
// dataDirOverride - Optional CLI flag override for data directory (takes highest priority)
// Returns *Config - Loaded configuration
// Returns error - Error if configuration loading fails
func Load(dataDirOverride ...string) (*Config, error) {
	// Load .env file if it exists
	// godotenv.Load() returns an error if .env doesn't exist, which is fine
	_ = godotenv.Load()

	// Determine data directory with fallback logic (priority order):
	// 1. CLI flag override (if provided) - highest priority
	// 2. TRADER_DATA_DIR environment variable
	// 3. Default to /home/arduino/data - lowest priority
	// 4. Always resolve to absolute path
	// 5. Ensure directory exists
	var dataDir string
	if len(dataDirOverride) > 0 && dataDirOverride[0] != "" {
		// CLI flag takes highest priority
		dataDir = dataDirOverride[0]
	} else {
		// Fall back to environment variable or default
		dataDir = getEnv("TRADER_DATA_DIR", "")
		if dataDir == "" {
			// Default fallback to absolute path (Arduino Uno Q default)
			dataDir = "/home/arduino/data"
		}
	}

	// Always resolve to absolute path
	// This ensures consistent path handling across different working directories
	absDataDir, err := filepath.Abs(dataDir)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve data directory path: %w", err)
	}

	// Ensure directory exists
	// Creates directory with 0755 permissions (rwxr-xr-x)
	if err := os.MkdirAll(absDataDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create data directory: %w", err)
	}

	cfg := &Config{
		DataDir:             absDataDir,
		Port:                getEnvAsInt("GO_PORT", 8001), // Default 8001 (Python uses 8000)
		DevMode:             getEnvAsBool("DEV_MODE", false),
		EvaluatorServiceURL: getEnv("EVALUATOR_SERVICE_URL", "http://localhost:9000"), // Evaluator-go microservice on 9000 (legacy)
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

// UpdateFromSettings updates configuration from settings database.
//
// This should be called after the config database is initialized (in di.Wire()).
// Settings database values take precedence over environment variables.
//
// This allows credentials and other sensitive settings to be managed via the
// Settings UI instead of requiring .env file changes or environment variable updates.
//
// If a settings database value is empty, the environment variable value is kept
// as a fallback.
//
// settingsRepo - Settings repository (must be initialized)
// Returns error - Error if settings retrieval fails
func (c *Config) UpdateFromSettings(settingsRepo *settings.Repository) error {
	// Try to get credentials from settings DB
	// Tradernet API key
	apiKey, err := settingsRepo.Get("tradernet_api_key")
	if err != nil {
		return fmt.Errorf("failed to get tradernet_api_key from settings: %w", err)
	}
	// Only use settings DB value if it's not empty (settings DB takes precedence)
	if apiKey != nil && *apiKey != "" {
		c.TradernetAPIKey = *apiKey
	}
	// If settings DB value is empty, keep the env var value (if any) as fallback

	// Tradernet API secret
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
	// GitHub token is used for downloading artifacts from GitHub Actions
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

// Validate checks if required configuration is present.
//
// Currently, all configuration is optional (Tradernet credentials can be set
// via Settings UI, and research mode doesn't require broker connection).
//
// Returns error - Error if validation fails (currently always returns nil)
func (c *Config) Validate() error {
	// Note: Tradernet credentials optional for research mode
	// Credentials can be set via Settings UI, so validation is not strict
	// if c.TradernetAPIKey == "" || c.TradernetAPISecret == "" {
	//     return fmt.Errorf("Tradernet API credentials required")
	// }

	return nil
}

// ==========================================
// Helper Functions
// ==========================================

// getEnv retrieves an environment variable with a default value.
//
// key - Environment variable name
// defaultValue - Default value if environment variable is not set
// Returns string - Environment variable value or default
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// getEnvAsInt retrieves an environment variable as an integer with a default value.
//
// key - Environment variable name
// defaultValue - Default value if environment variable is not set or invalid
// Returns int - Environment variable value as integer or default
func getEnvAsInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intVal, err := strconv.Atoi(value); err == nil {
			return intVal
		}
	}
	return defaultValue
}

// getEnvAsBool retrieves an environment variable as a boolean with a default value.
//
// key - Environment variable name
// defaultValue - Default value if environment variable is not set or invalid
// Returns bool - Environment variable value as boolean or default
func getEnvAsBool(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		if boolVal, err := strconv.ParseBool(value); err == nil {
			return boolVal
		}
	}
	return defaultValue
}

// loadDeploymentConfig loads deployment configuration with hardcoded defaults.
//
// Deployment is enabled by default and uses GitHub Actions artifacts for deployment.
// This saves 1GB+ disk space by not requiring Go toolchain on the device.
//
// Returns *DeploymentConfig - Deployment configuration with defaults
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
