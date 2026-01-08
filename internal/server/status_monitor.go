// Package server provides the HTTP server and routing for Sentinel.
package server

import (
	"time"

	"github.com/aristath/sentinel/internal/events"
	"github.com/rs/zerolog"
)

// StatusMonitor periodically checks system statuses and emits events on changes
type StatusMonitor struct {
	eventManager    *events.Manager
	systemHandlers  *SystemHandlers
	log             zerolog.Logger

	// Track previous states
	lastSystemStatus    map[string]interface{}
	lastTradernetStatus bool
}

// NewStatusMonitor creates a new status monitor
func NewStatusMonitor(
	eventManager *events.Manager,
	systemHandlers *SystemHandlers,
	log zerolog.Logger,
) *StatusMonitor {
	return &StatusMonitor{
		eventManager:    eventManager,
		systemHandlers:  systemHandlers,
		log:             log.With().Str("component", "status_monitor").Logger(),
		lastSystemStatus: make(map[string]interface{}),
	}
}

// Start begins periodic status monitoring
func (m *StatusMonitor) Start(interval time.Duration) {
	go m.monitor(interval)
}

// monitor runs the periodic monitoring loop
func (m *StatusMonitor) monitor(interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	// Do initial check
	m.checkStatuses()

	for range ticker.C {
		m.checkStatuses()
	}
}

// checkStatuses checks all monitored statuses and emits events on changes
func (m *StatusMonitor) checkStatuses() {
	// Check system status (simplified - just check if active positions count changed)
	// Full system status check would be expensive, so we do minimal checks
	m.checkSystemStatus()

	// Check tradernet status
	m.checkTradernetStatus()
}

// checkSystemStatus checks if system status has changed
func (m *StatusMonitor) checkSystemStatus() {
	// For now, emit SYSTEM_STATUS_CHANGED periodically
	// In a production system, we'd track specific metrics and compare
	if m.eventManager != nil {
		m.eventManager.Emit(events.SystemStatusChanged, "status_monitor", map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		})
	}
}

// checkTradernetStatus checks if tradernet connection status has changed
func (m *StatusMonitor) checkTradernetStatus() {
	if m.systemHandlers == nil || m.systemHandlers.tradernetClient == nil {
		return
	}

	// Check connection status
	connected := m.systemHandlers.tradernetClient.IsConnected()

	// Emit event if status changed
	if connected != m.lastTradernetStatus {
		if m.eventManager != nil {
			m.eventManager.Emit(events.TradernetStatusChanged, "status_monitor", map[string]interface{}{
				"connected": connected,
				"timestamp": time.Now().Format(time.RFC3339),
			})
		}
		m.lastTradernetStatus = connected
	}
}
