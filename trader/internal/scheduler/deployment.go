package scheduler

import (
	"time"

	"github.com/aristath/arduino-trader/internal/deployment"
	"github.com/rs/zerolog"
)

// DeploymentJob handles scheduled deployment checks
type DeploymentJob struct {
	deploymentManager *deployment.Manager
	log               zerolog.Logger
	interval          time.Duration
	enabled           bool
}

// NewDeploymentJob creates a new deployment job
func NewDeploymentJob(deploymentManager *deployment.Manager, interval time.Duration, enabled bool, log zerolog.Logger) *DeploymentJob {
	return &DeploymentJob{
		deploymentManager: deploymentManager,
		log:               log.With().Str("component", "deployment_job").Logger(),
		interval:          interval,
		enabled:           enabled,
	}
}

// Name returns the job name
func (j *DeploymentJob) Name() string {
	return "deployment"
}

// Run executes the deployment check
func (j *DeploymentJob) Run() error {
	if !j.enabled {
		j.log.Debug().Msg("Deployment job is disabled, skipping")
		return nil
	}

	j.log.Info().Msg("Running deployment check")

	result, err := j.deploymentManager.Deploy()
	if err != nil {
		j.log.Error().Err(err).Msg("Deployment failed")
		return err
	}

	if result.Deployed {
		j.log.Info().
			Bool("success", result.Success).
			Int("services", len(result.ServicesDeployed)).
			Dur("duration", result.Duration).
			Msg("Deployment completed successfully")
	} else {
		j.log.Debug().Msg("No deployment needed (no changes)")
	}

	return nil
}
