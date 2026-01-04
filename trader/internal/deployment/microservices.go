package deployment

import (
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// MicroserviceDeployer orchestrates Python microservice deployments
type MicroserviceDeployer struct {
	dockerMgr *DockerManager
	log       Logger
}

// NewMicroserviceDeployer creates a new microservice deployer
func NewMicroserviceDeployer(dockerMgr *DockerManager, log Logger) *MicroserviceDeployer {
	return &MicroserviceDeployer{
		dockerMgr: dockerMgr,
		log:       log,
	}
}

// DeployMicroservice deploys a single microservice
func (d *MicroserviceDeployer) DeployMicroservice(serviceName string, repoDir string, rebuildImage bool) error {
	composeDir := filepath.Join(repoDir, fmt.Sprintf("microservices/%s", serviceName))

	// Check if compose directory exists
	if _, err := os.Stat(composeDir); os.IsNotExist(err) {
		return fmt.Errorf("microservice directory does not exist: %s", composeDir)
	}

	composeFile := filepath.Join(composeDir, "docker-compose.yml")
	if _, err := os.Stat(composeFile); os.IsNotExist(err) {
		d.log.Warn().
			Str("service", serviceName).
			Str("file", composeFile).
			Msg("docker-compose.yml not found, microservice may need manual setup")
		return nil
	}

	// Rebuild image if dependencies changed
	if rebuildImage {
		if err := d.dockerMgr.RebuildImage(serviceName, composeDir); err != nil {
			return fmt.Errorf("failed to rebuild image for %s: %w", serviceName, err)
		}
	}

	// Restart container to pick up code changes (volumes are mounted from repo)
	if err := d.dockerMgr.RestartContainer(serviceName, composeDir); err != nil {
		return fmt.Errorf("failed to restart container for %s: %w", serviceName, err)
	}

	d.log.Info().
		Str("service", serviceName).
		Bool("rebuild_image", rebuildImage).
		Msg("Successfully deployed microservice")

	return nil
}

// DeployMicroservices deploys multiple microservices
func (d *MicroserviceDeployer) DeployMicroservices(services map[string]bool, repoDir string) map[string]error {
	errors := make(map[string]error)

	for serviceName, rebuildImage := range services {
		if err := d.DeployMicroservice(serviceName, repoDir, rebuildImage); err != nil {
			errors[serviceName] = err
		}
	}

	return errors
}

// CheckMicroserviceHealth checks health of a microservice
func (d *MicroserviceDeployer) CheckMicroserviceHealth(serviceName string, repoDir string, healthURL string) error {
	composeDir := filepath.Join(repoDir, fmt.Sprintf("microservices/%s", serviceName))

	if err := d.dockerMgr.CheckContainerHealth(serviceName, composeDir, healthURL, 3, 5*time.Second); err != nil {
		return fmt.Errorf("health check failed for %s: %w", serviceName, err)
	}

	return nil
}

// GetMicroserviceHealthURL returns the health check URL for a microservice
func (d *MicroserviceDeployer) GetMicroserviceHealthURL(serviceName string) string {
	// Default ports for microservices
	ports := map[string]string{
		"pypfopt":   "http://localhost:9002/health",
		"tradernet": "http://localhost:9001/health",
	}

	if url, ok := ports[serviceName]; ok {
		return url
	}

	return "http://localhost:9001/health" // Default
}
