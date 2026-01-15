package work

import (
	"context"
	"fmt"
	"time"
)

// DeploymentCheckServiceInterface defines the deployment check service interface
type DeploymentCheckServiceInterface interface {
	CheckForDeployment() error
	GetCheckInterval() time.Duration
}

// DeploymentDeps contains all dependencies for deployment work types
type DeploymentDeps struct {
	DeploymentService DeploymentCheckServiceInterface
}

// RegisterDeploymentWorkTypes registers all deployment work types with the registry
func RegisterDeploymentWorkTypes(registry *Registry, deps *DeploymentDeps) {
	// deployment:check - Check for new deployments
	registry.Register(&WorkType{
		ID:           "deployment:check",
		Priority:     PriorityLow,
		MarketTiming: AnyTime,
		Interval:     deps.DeploymentService.GetCheckInterval(),
		FindSubjects: func() []string {
			// Always check for deployments on interval
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string) error {

			err := deps.DeploymentService.CheckForDeployment()
			if err != nil {
				return fmt.Errorf("failed to check for deployment: %w", err)
			}

			return nil
		},
	})
}
