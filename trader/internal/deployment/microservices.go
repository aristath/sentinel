package deployment

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

// MicroserviceDeployer orchestrates Python microservice deployments
type MicroserviceDeployer struct {
	dockerMgr  *DockerManager
	serviceMgr *ServiceManager
	log        Logger
}

// NewMicroserviceDeployer creates a new microservice deployer
func NewMicroserviceDeployer(dockerMgr *DockerManager, serviceMgr *ServiceManager, log Logger) *MicroserviceDeployer {
	return &MicroserviceDeployer{
		dockerMgr:  dockerMgr,
		serviceMgr: serviceMgr,
		log:        log,
	}
}

// IsNativeService returns true if the service runs natively (not in Docker)
func (d *MicroserviceDeployer) IsNativeService(serviceName string) bool {
	return serviceName == "tradernet"
}

// DeployMicroservice deploys a single microservice
func (d *MicroserviceDeployer) DeployMicroservice(serviceName string, repoDir string, rebuildImage bool) error {
	// Route to native or Docker deployment
	if d.IsNativeService(serviceName) {
		return d.DeployNativeService(serviceName, repoDir, rebuildImage)
	}

	// Docker deployment (pypfopt)
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

// DeployNativeService deploys a native systemd service (tradernet)
func (d *MicroserviceDeployer) DeployNativeService(serviceName string, repoDir string, recreateVenv bool) error {
	serviceDir := filepath.Join(repoDir, fmt.Sprintf("microservices/%s", serviceName))

	// Check if service directory exists
	if _, err := os.Stat(serviceDir); os.IsNotExist(err) {
		return fmt.Errorf("microservice directory does not exist: %s", serviceDir)
	}

	// Recreate venv if dependencies changed
	if recreateVenv {
		d.log.Info().
			Str("service", serviceName).
			Msg("Recreating virtual environment due to dependency changes")
		if err := d.RecreateVenv(serviceName, repoDir); err != nil {
			return fmt.Errorf("failed to recreate venv for %s: %w", serviceName, err)
		}
	}

	// Restart systemd service to pick up code changes
	// systemctl accepts service name with or without .service suffix
	if err := d.serviceMgr.RestartService(serviceName); err != nil {
		return fmt.Errorf("failed to restart systemd service for %s: %w", serviceName, err)
	}

	d.log.Info().
		Str("service", serviceName).
		Bool("recreated_venv", recreateVenv).
		Msg("Successfully deployed native microservice")

	return nil
}

// RecreateVenv recreates the virtual environment for a native service
func (d *MicroserviceDeployer) RecreateVenv(serviceName string, repoDir string) error {
	serviceDir := filepath.Join(repoDir, fmt.Sprintf("microservices/%s", serviceName))
	venvPath := filepath.Join(serviceDir, "venv")
	requirementsPath := filepath.Join(serviceDir, "requirements.txt")

	// Check requirements.txt exists
	if _, err := os.Stat(requirementsPath); os.IsNotExist(err) {
		return fmt.Errorf("requirements.txt not found: %s", requirementsPath)
	}

	d.log.Info().
		Str("service", serviceName).
		Str("venv_path", venvPath).
		Msg("Recreating virtual environment")

	// Remove old venv
	if _, err := os.Stat(venvPath); err == nil {
		if err := os.RemoveAll(venvPath); err != nil {
			return fmt.Errorf("failed to remove old venv: %w", err)
		}
	}

	// Create new venv
	cmd := exec.Command("python3", "-m", "venv", venvPath)
	cmd.Dir = serviceDir
	if output, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("failed to create venv: %w (output: %s)", err, string(output))
	}

	// Install dependencies
	pipPath := filepath.Join(venvPath, "bin", "pip")
	cmd = exec.Command(pipPath, "install", "--upgrade", "pip")
	cmd.Dir = serviceDir
	if output, err := cmd.CombinedOutput(); err != nil {
		d.log.Warn().Err(err).Str("output", string(output)).Msg("Failed to upgrade pip, continuing")
	}

	cmd = exec.Command(pipPath, "install", "--no-cache-dir", "-r", requirementsPath)
	cmd.Dir = serviceDir
	if output, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("failed to install dependencies: %w (output: %s)", err, string(output))
	}

	d.log.Info().
		Str("service", serviceName).
		Msg("Virtual environment recreated successfully")

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
	// Native services use HTTP health check
	if d.IsNativeService(serviceName) {
		if err := d.serviceMgr.CheckHealth(healthURL, 3, 5*time.Second); err != nil {
			return fmt.Errorf("health check failed for %s: %w", serviceName, err)
		}
		return nil
	}

	// Docker services use container health check
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
		"pypfopt":   "http://localhost:9001/health",
		"tradernet": "http://localhost:9002/health",
	}

	if url, ok := ports[serviceName]; ok {
		return url
	}

	return "http://localhost:9001/health" // Default
}
