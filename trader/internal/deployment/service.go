package deployment

import (
	"fmt"
	"net/http"
	"os/exec"
	"strings"
	"sync"
	"time"
)

// ServiceManager manages systemd services
type ServiceManager struct {
	log Logger
}

// NewServiceManager creates a new service manager
func NewServiceManager(log Logger) *ServiceManager {
	return &ServiceManager{
		log: log,
	}
}

// RestartService restarts a systemd service
func (s *ServiceManager) RestartService(serviceName string) error {
	s.log.Info().
		Str("service", serviceName).
		Msg("Restarting systemd service")

	cmd := exec.Command("sudo", "systemctl", "restart", serviceName)
	output, err := cmd.CombinedOutput()
	if err != nil {
		outputStr := strings.TrimSpace(string(output))
		return &ServiceRestartError{
			ServiceName: serviceName,
			Message:     fmt.Sprintf("systemctl restart failed: %s", outputStr),
			Err:         err,
		}
	}

	s.log.Info().
		Str("service", serviceName).
		Msg("Successfully restarted systemd service")

	return nil
}

// RestartServices restarts multiple services in parallel
func (s *ServiceManager) RestartServices(serviceNames []string) map[string]error {
	var wg sync.WaitGroup
	errors := make(map[string]error)
	var mu sync.Mutex

	for _, serviceName := range serviceNames {
		wg.Add(1)
		go func(name string) {
			defer wg.Done()
			err := s.RestartService(name)
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

// CheckHealth performs a health check on a service
func (s *ServiceManager) CheckHealth(apiURL string, maxAttempts int, timeout time.Duration) error {
	client := &http.Client{
		Timeout: timeout,
	}

	var lastError error
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		s.log.Debug().
			Str("url", apiURL).
			Int("attempt", attempt).
			Int("max_attempts", maxAttempts).
			Msg("Performing health check")

		req, err := http.NewRequest("GET", apiURL, nil)
		if err != nil {
			return &HealthCheckError{
				ServiceName: apiURL,
				Message:     "failed to create health check request",
				Err:         err,
			}
		}

		resp, err := client.Do(req)
		if err != nil {
			lastError = err
			if attempt < maxAttempts {
				time.Sleep(1 * time.Second)
				continue
			}
			return &HealthCheckError{
				ServiceName: apiURL,
				Message:     fmt.Sprintf("health check failed after %d attempts", maxAttempts),
				Err:         err,
			}
		}
		resp.Body.Close()

		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			s.log.Info().
				Str("url", apiURL).
				Int("status", resp.StatusCode).
				Msg("Health check passed")
			return nil
		}

		lastError = fmt.Errorf("unexpected status code: %d", resp.StatusCode)
		if attempt < maxAttempts {
			time.Sleep(1 * time.Second)
			continue
		}
	}

	return &HealthCheckError{
		ServiceName: apiURL,
		Message:     fmt.Sprintf("health check failed after %d attempts", maxAttempts),
		Err:         lastError,
	}
}

// GetServiceStatus returns the status of a systemd service
func (s *ServiceManager) GetServiceStatus(serviceName string) (string, error) {
	cmd := exec.Command("systemctl", "is-active", serviceName)
	output, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("failed to get service status: %w", err)
	}

	status := strings.TrimSpace(string(output))
	return status, nil
}
