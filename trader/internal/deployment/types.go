package deployment

import (
	"time"
)

// DeploymentResult represents the result of a deployment attempt
type DeploymentResult struct {
	Success          bool
	Deployed         bool // Whether deployment actually happened (vs no changes)
	CommitBefore     string
	CommitAfter      string
	Error            string
	ServicesDeployed []ServiceDeployment
	SketchDeployed   bool
	Duration         time.Duration
}

// ServiceDeployment represents the deployment status of a single service
type ServiceDeployment struct {
	ServiceName string // "trader", "display-bridge", "pypfopt", "tradernet"
	ServiceType string // "go", "docker"
	Success     bool
	Error       string
}

// ChangeCategories categorizes what types of changes were detected
type ChangeCategories struct {
	MainApp       bool
	DisplayBridge bool
	Static        bool
	Sketch        bool
	PyPFOpt       bool
	PyPFOptDeps   bool
	Tradernet     bool
	TradernetDeps bool
	Config        bool
}

// HasAnyChanges returns true if any category has changes
func (c *ChangeCategories) HasAnyChanges() bool {
	return c.MainApp || c.DisplayBridge || c.Static || c.Sketch ||
		c.PyPFOpt || c.PyPFOptDeps || c.Tradernet || c.TradernetDeps || c.Config
}

// GoServiceConfig holds configuration for a Go service
type GoServiceConfig struct {
	Name        string // Service identifier: "trader" or "display-bridge"
	BuildPath   string // Relative path from repo root (e.g., "trader/cmd/server")
	BinaryName  string // Output binary name (e.g., "trader")
	ServiceName string // Systemd service name (e.g., "trader")
}

// DefaultTraderConfig returns default configuration for trader service
func DefaultTraderConfig() GoServiceConfig {
	return GoServiceConfig{
		Name:        "trader",
		BuildPath:   "trader/cmd/server",
		BinaryName:  "trader",
		ServiceName: "trader",
	}
}

// DefaultBridgeConfig returns default configuration for display-bridge service
func DefaultBridgeConfig() GoServiceConfig {
	return GoServiceConfig{
		Name:        "display-bridge",
		BuildPath:   "display/bridge",
		BinaryName:  "display-bridge",
		ServiceName: "display-bridge",
	}
}
