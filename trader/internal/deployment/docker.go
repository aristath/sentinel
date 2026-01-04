package deployment

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// DockerManager manages Docker containers and images
type DockerManager struct {
	composePath string
	log         Logger
}

// NewDockerManager creates a new Docker manager
func NewDockerManager(composePath string, log Logger) *DockerManager {
	return &DockerManager{
		composePath: composePath,
		log:         log,
	}
}

// RebuildImage rebuilds a Docker image for a service
func (d *DockerManager) RebuildImage(serviceName string, composeDir string) error {
	d.log.Info().
		Str("service", serviceName).
		Str("compose_dir", composeDir).
		Msg("Rebuilding Docker image")

	cmd := exec.Command("docker", "compose", "build", serviceName)
	cmd.Dir = composeDir

	var stdout, stderr strings.Builder
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		output := stdout.String() + stderr.String()
		return fmt.Errorf("failed to rebuild Docker image for %s: %w\nOutput: %s", serviceName, err, output)
	}

	d.log.Info().
		Str("service", serviceName).
		Msg("Successfully rebuilt Docker image")

	return nil
}

// RestartContainer restarts a Docker container
func (d *DockerManager) RestartContainer(serviceName string, composeDir string) error {
	d.log.Info().
		Str("service", serviceName).
		Str("compose_dir", composeDir).
		Msg("Restarting Docker container")

	cmd := exec.Command("docker", "compose", "restart", serviceName)
	cmd.Dir = composeDir

	var stdout, stderr strings.Builder
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		output := stdout.String() + stderr.String()
		return fmt.Errorf("failed to restart Docker container for %s: %w\nOutput: %s", serviceName, err, output)
	}

	d.log.Info().
		Str("service", serviceName).
		Msg("Successfully restarted Docker container")

	return nil
}

// RestartContainers restarts multiple containers in parallel
func (d *DockerManager) RestartContainers(serviceNames []string, composeDir string) map[string]error {
	var wg sync.WaitGroup
	errors := make(map[string]error)
	var mu sync.Mutex

	for _, serviceName := range serviceNames {
		wg.Add(1)
		go func(name string) {
			defer wg.Done()
			err := d.RestartContainer(name, composeDir)
			if err != nil {
				mu.Lock()
				errors[name] = err
				mu.Unlock()
			}
		}(serviceName)
	}

	wg.Wait()
	return errors
}

// CheckContainerHealth performs a health check on a container
func (d *DockerManager) CheckContainerHealth(serviceName string, composeDir string, healthURL string, maxAttempts int, timeout time.Duration) error {
	// First, check if container is running
	if err := d.waitForContainerRunning(serviceName, composeDir, 10*time.Second); err != nil {
		return fmt.Errorf("container not running: %w", err)
	}

	// Then perform HTTP health check if URL provided
	if healthURL != "" {
		sm := NewServiceManager(d.log)
		if err := sm.CheckHealth(healthURL, maxAttempts, timeout); err != nil {
			return fmt.Errorf("health check failed: %w", err)
		}
	}

	return nil
}

// waitForContainerRunning waits for a container to be in running state
func (d *DockerManager) waitForContainerRunning(serviceName string, composeDir string, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	interval := 1 * time.Second

	for time.Now().Before(deadline) {
		status, err := d.getContainerStatus(serviceName, composeDir)
		if err != nil {
			return err
		}

		if status == "running" {
			return nil
		}

		time.Sleep(interval)
	}

	return fmt.Errorf("container %s did not reach running state within %v", serviceName, timeout)
}

// getContainerStatus gets the status of a container
func (d *DockerManager) getContainerStatus(serviceName string, composeDir string) (string, error) {
	// Get container name from compose
	cmd := exec.Command("docker", "compose", "ps", "-q", serviceName)
	cmd.Dir = composeDir

	output, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("failed to get container ID: %w", err)
	}

	containerID := strings.TrimSpace(string(output))
	if containerID == "" {
		return "not_found", nil
	}

	// Get container status
	cmd = exec.Command("docker", "inspect", "-f", "{{.State.Status}}", containerID)
	output, err = cmd.Output()
	if err != nil {
		return "", fmt.Errorf("failed to inspect container: %w", err)
	}

	status := strings.TrimSpace(string(output))
	return status, nil
}

// GenerateComposeFile generates a docker-compose.yml file with volume mounts
func (d *DockerManager) GenerateComposeFile(serviceName string, repoDir string, outputPath string, ports map[string]int, env map[string]string) error {
	compose := ComposeConfig{
		Version: "3.8",
		Services: map[string]ServiceConfig{
			serviceName: {
				Build: BuildConfig{
					Context:    ".",
					Dockerfile: "Dockerfile",
				},
				ContainerName: fmt.Sprintf("%s-service", serviceName),
				Ports:         []string{},
				Environment:   []string{},
				Restart:       "unless-stopped",
				Volumes: []string{
					fmt.Sprintf("%s:/app", filepath.Join(repoDir, fmt.Sprintf("microservices/%s", serviceName))),
				},
				WorkingDir: "/app",
			},
		},
	}

	// Add ports
	service := compose.Services[serviceName]
	for hostPort, containerPort := range ports {
		service.Ports = append(service.Ports, fmt.Sprintf("%s:%d", hostPort, containerPort))
	}

	// Add environment variables
	for key, value := range env {
		service.Environment = append(service.Environment, fmt.Sprintf("%s=%s", key, value))
	}

	compose.Services[serviceName] = service

	// Write compose file
	data, err := json.MarshalIndent(compose, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal compose config: %w", err)
	}

	if err := os.WriteFile(outputPath, data, 0644); err != nil {
		return fmt.Errorf("failed to write compose file: %w", err)
	}

	d.log.Info().
		Str("service", serviceName).
		Str("output", outputPath).
		Msg("Generated docker-compose.yml")

	return nil
}

// ComposeConfig represents a docker-compose.yml structure
type ComposeConfig struct {
	Version  string                   `json:"version"`
	Services map[string]ServiceConfig `json:"services"`
}

// ServiceConfig represents a service in docker-compose
type ServiceConfig struct {
	Build         BuildConfig `json:"build"`
	ContainerName string      `json:"container_name"`
	Ports         []string    `json:"ports"`
	Environment   []string    `json:"environment"`
	Restart       string      `json:"restart"`
	Volumes       []string    `json:"volumes"`
	WorkingDir    string      `json:"working_dir,omitempty"`
}

// BuildConfig represents build configuration
type BuildConfig struct {
	Context    string `json:"context"`
	Dockerfile string `json:"dockerfile"`
}
