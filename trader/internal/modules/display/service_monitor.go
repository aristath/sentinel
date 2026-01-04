package display

import (
	"context"
	"os/exec"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// ServiceMonitor monitors systemd service status and updates LED3 accordingly
type ServiceMonitor struct {
	serviceName  string
	stateManager *StateManager
	log          zerolog.Logger
	interval     time.Duration
}

// NewServiceMonitor creates a new service monitor
func NewServiceMonitor(serviceName string, stateManager *StateManager, log zerolog.Logger) *ServiceMonitor {
	return &ServiceMonitor{
		serviceName:  serviceName,
		stateManager: stateManager,
		log:          log.With().Str("component", "service_monitor").Logger(),
		interval:     2 * time.Second,
	}
}

// GetServiceStatus queries systemd for service status
func (sm *ServiceMonitor) GetServiceStatus() (string, error) {
	cmd := exec.Command("systemctl", "is-active", sm.serviceName)
	output, err := cmd.Output()
	if err != nil {
		// Check if service is inactive
		if exitErr, ok := err.(*exec.ExitError); ok && exitErr.ExitCode() == 3 {
			return "inactive", nil
		}
		return "", err
	}

	status := strings.TrimSpace(string(output))
	return status, nil
}

// UpdateLED3ForStatus maps service status to LED3 behavior
func (sm *ServiceMonitor) UpdateLED3ForStatus(status string) {
	switch status {
	case "active":
		// Green blinking heartbeat
		sm.stateManager.SetLED3Blink(0, 255, 0, 1000)
		sm.log.Debug().Str("status", status).Msg("LED3: Green blink (active)")
	case "activating", "reloading":
		// Yellow blinking (starting)
		sm.stateManager.SetLED3Blink(255, 255, 0, 1000)
		sm.log.Debug().Str("status", status).Msg("LED3: Yellow blink (starting)")
	case "inactive", "failed", "deactivating":
		// Red solid (failed/inactive)
		sm.stateManager.SetLED3Color(255, 0, 0)
		sm.log.Debug().Str("status", status).Msg("LED3: Red solid (failed/inactive)")
	default:
		// Unknown status - turn off
		sm.stateManager.SetLED3Color(0, 0, 0)
		sm.log.Debug().Str("status", status).Msg("LED3: Off (unknown status)")
	}
}

// MonitorService runs the monitoring loop
func (sm *ServiceMonitor) MonitorService(ctx context.Context) {
	sm.log.Info().
		Str("service", sm.serviceName).
		Dur("interval", sm.interval).
		Msg("Starting service monitor")

	ticker := time.NewTicker(sm.interval)
	defer ticker.Stop()

	// Initial check
	status, err := sm.GetServiceStatus()
	if err != nil {
		sm.log.Error().Err(err).Msg("Failed to get initial service status")
		sm.UpdateLED3ForStatus("unknown")
	} else {
		sm.UpdateLED3ForStatus(status)
	}

	for {
		select {
		case <-ctx.Done():
			sm.log.Info().Msg("Service monitor stopping")
			sm.stateManager.SetLED3Color(0, 0, 0)
			return
		case <-ticker.C:
			status, err := sm.GetServiceStatus()
			if err != nil {
				sm.log.Debug().Err(err).Msg("Failed to get service status")
				sm.UpdateLED3ForStatus("unknown")
				continue
			}

			sm.UpdateLED3ForStatus(status)
		}
	}
}
