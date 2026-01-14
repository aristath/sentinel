package display

import (
	"fmt"
	"sync"

	"github.com/aristath/sentinel/internal/ticker"
	"github.com/rs/zerolog"
)

// DisplayMode represents the current display mode
type DisplayMode string

const (
	// ModeText displays scrolling ticker text
	ModeText DisplayMode = "TEXT"
	// ModeHealth displays organic portfolio health visualization
	ModeHealth DisplayMode = "HEALTH"
	// ModeStats displays system statistics
	ModeStats DisplayMode = "STATS"
)

// ModeManager manages display mode switching
type ModeManager struct {
	stateManager  *StateManager
	healthUpdater *HealthUpdater
	tickerService *ticker.TickerContentService
	currentMode   DisplayMode
	log           zerolog.Logger
	mu            sync.RWMutex
}

// NewModeManager creates a new display mode manager
func NewModeManager(
	stateManager *StateManager,
	healthUpdater *HealthUpdater,
	tickerService *ticker.TickerContentService,
	log zerolog.Logger,
) *ModeManager {
	return &ModeManager{
		stateManager:  stateManager,
		healthUpdater: healthUpdater,
		tickerService: tickerService,
		currentMode:   ModeText, // Default to text mode
		log:           log.With().Str("component", "mode_manager").Logger(),
	}
}

// SetMode switches the display to the specified mode
func (m *ModeManager) SetMode(mode DisplayMode) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if mode == m.currentMode {
		m.log.Debug().Str("mode", string(mode)).Msg("Already in requested mode")
		return nil
	}

	m.log.Info().
		Str("from", string(m.currentMode)).
		Str("to", string(mode)).
		Msg("Switching display mode")

	// Stop any active modes
	m.stopCurrentMode()

	// Start new mode
	switch mode {
	case ModeText:
		if err := m.startTextMode(); err != nil {
			return fmt.Errorf("failed to start text mode: %w", err)
		}

	case ModeHealth:
		if err := m.startHealthMode(); err != nil {
			return fmt.Errorf("failed to start health mode: %w", err)
		}

	case ModeStats:
		if err := m.startStatsMode(); err != nil {
			return fmt.Errorf("failed to start stats mode: %w", err)
		}

	default:
		return fmt.Errorf("unknown display mode: %s", mode)
	}

	m.currentMode = mode
	m.log.Info().Str("mode", string(mode)).Msg("Display mode switched successfully")
	return nil
}

// GetMode returns the current display mode
func (m *ModeManager) GetMode() DisplayMode {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.currentMode
}

// SetModeString switches the display to the specified mode (string version for interface compatibility)
func (m *ModeManager) SetModeString(mode string) error {
	return m.SetMode(DisplayMode(mode))
}

// stopCurrentMode stops the currently active mode
func (m *ModeManager) stopCurrentMode() {
	switch m.currentMode {
	case ModeText:
		// Stop ticker updates (if any background service exists)
		m.stateManager.SetText("")

	case ModeHealth:
		// Stop health updater
		m.healthUpdater.Stop()

	case ModeStats:
		// Clear stats display
		m.stateManager.ClearMatrix()
	}
}

// startTextMode starts text/ticker mode
func (m *ModeManager) startTextMode() error {
	// Generate ticker text
	text, err := m.tickerService.GenerateTickerText()
	if err != nil {
		m.log.Warn().Err(err).Msg("Failed to generate ticker text, using fallback")
		text = "SENTINEL ONLINE"
	}

	// Set text on display
	m.stateManager.SetText(text)

	m.log.Debug().Str("text", text).Msg("Started text mode")
	return nil
}

// startHealthMode starts portfolio health visualization mode
func (m *ModeManager) startHealthMode() error {
	// Clear any existing text
	m.stateManager.SetText("")

	// Start health updater (will send initial update immediately)
	m.healthUpdater.Start()

	m.log.Debug().Msg("Started health mode")
	return nil
}

// startStatsMode starts system statistics mode
func (m *ModeManager) startStatsMode() error {
	// Clear text
	m.stateManager.SetText("")

	// Set initial pixel count (could be based on system metrics)
	// For now, just clear the matrix - actual stats logic can be added later
	m.stateManager.ClearMatrix()

	m.log.Debug().Msg("Started stats mode")
	return nil
}

// RefreshCurrentMode refreshes the current mode (useful after settings changes)
func (m *ModeManager) RefreshCurrentMode() error {
	m.mu.RLock()
	mode := m.currentMode
	m.mu.RUnlock()

	m.log.Info().Str("mode", string(mode)).Msg("Refreshing current mode")

	// Re-set the same mode (will restart it)
	return m.SetMode(mode)
}
