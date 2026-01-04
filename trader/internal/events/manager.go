package events

import (
	"encoding/json"
	"time"

	"github.com/rs/zerolog"
)

// EventType represents different event types
type EventType string

const (
	CashFlowSyncStart    EventType = "CASH_FLOW_SYNC_START"
	CashFlowSyncComplete EventType = "CASH_FLOW_SYNC_COMPLETE"
	ErrorOccurred        EventType = "ERROR_OCCURRED"
	DepositProcessed     EventType = "DEPOSIT_PROCESSED"
	DividendCreated      EventType = "DIVIDEND_CREATED"
	SecurityAdded        EventType = "SECURITY_ADDED"

	// Satellite bucket events
	SatelliteCreated    EventType = "SATELLITE_CREATED"
	SatelliteActivated  EventType = "SATELLITE_ACTIVATED"
	SatellitePaused     EventType = "SATELLITE_PAUSED"
	SatelliteResumed    EventType = "SATELLITE_RESUMED"
	SatelliteRetired    EventType = "SATELLITE_RETIRED"
	SatelliteHibernated EventType = "SATELLITE_HIBERNATED"
	SatelliteReawakened EventType = "SATELLITE_REAWAKENED"
	BucketUpdated       EventType = "BUCKET_UPDATED"

	// Satellite balance events
	BalanceTransferred EventType = "BALANCE_TRANSFERRED"
	DepositAllocated   EventType = "DEPOSIT_ALLOCATED"
	BalancesReconciled EventType = "BALANCES_RECONCILED"

	// Satellite settings events
	SettingsUpdated EventType = "SETTINGS_UPDATED"
	PresetApplied   EventType = "PRESET_APPLIED"
)

// Event represents a system event
type Event struct {
	Type      EventType              `json:"type"`
	Timestamp time.Time              `json:"timestamp"`
	Data      map[string]interface{} `json:"data"`
	Module    string                 `json:"module"`
}

// Manager handles event emission and logging
type Manager struct {
	log zerolog.Logger
}

// NewManager creates a new event manager
func NewManager(log zerolog.Logger) *Manager {
	return &Manager{
		log: log.With().Str("service", "events").Logger(),
	}
}

// Emit emits an event
func (m *Manager) Emit(eventType EventType, module string, data map[string]interface{}) {
	event := Event{
		Type:      eventType,
		Timestamp: time.Now(),
		Data:      data,
		Module:    module,
	}

	// Log event
	eventJSON, _ := json.Marshal(event)
	m.log.Info().
		Str("event_type", string(eventType)).
		Str("module", module).
		RawJSON("event", eventJSON).
		Msg("Event emitted")
}

// EmitError emits an error event
func (m *Manager) EmitError(module string, err error, context map[string]interface{}) {
	data := map[string]interface{}{
		"error":   err.Error(),
		"context": context,
	}
	m.Emit(ErrorOccurred, module, data)
}
