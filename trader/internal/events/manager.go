// Package events provides event management functionality.
package events

import (
	"encoding/json"
	"time"

	"github.com/rs/zerolog"
)

// Event represents a system event with typed data
// The Data field can be either EventData (typed) or map[string]interface{} (legacy)
type Event struct {
	Type      EventType              `json:"type"`
	Timestamp time.Time              `json:"timestamp"`
	Data      map[string]interface{} `json:"data"` // Legacy: for backward compatibility, can be converted to EventData
	Module    string                 `json:"module"`
}

// GetTypedData attempts to convert the legacy Data map to typed EventData
// Returns the typed data if conversion is successful, nil otherwise
func (e *Event) GetTypedData() EventData {
	if e.Data == nil {
		return nil
	}

	// Try to unmarshal based on event type
	switch e.Type {
	case PlanGenerated:
		var data PlanGeneratedData
		if err := convertMapToStruct(e.Data, &data); err == nil {
			return &data
		}
	case RecommendationsReady:
		var data RecommendationsReadyData
		if err := convertMapToStruct(e.Data, &data); err == nil {
			return &data
		}
	case PortfolioChanged:
		var data PortfolioChangedData
		if err := convertMapToStruct(e.Data, &data); err == nil {
			return &data
		}
	case PriceUpdated:
		var data PriceUpdatedData
		if err := convertMapToStruct(e.Data, &data); err == nil {
			return &data
		}
	case TradeExecuted:
		var data TradeExecutedData
		if err := convertMapToStruct(e.Data, &data); err == nil {
			return &data
		}
	case SecurityAdded:
		var data SecurityAddedData
		if err := convertMapToStruct(e.Data, &data); err == nil {
			return &data
		}
	case SecuritySynced:
		var data SecuritySyncedData
		if err := convertMapToStruct(e.Data, &data); err == nil {
			return &data
		}
	case ScoreUpdated:
		var data ScoreUpdatedData
		if err := convertMapToStruct(e.Data, &data); err == nil {
			return &data
		}
	case SettingsChanged:
		var data SettingsChangedData
		if err := convertMapToStruct(e.Data, &data); err == nil {
			return &data
		}
	case SystemStatusChanged:
		var data SystemStatusChangedData
		if err := convertMapToStruct(e.Data, &data); err == nil {
			return &data
		}
	case TradernetStatusChanged:
		var data TradernetStatusChangedData
		if err := convertMapToStruct(e.Data, &data); err == nil {
			return &data
		}
	case MarketsStatusChanged:
		var data MarketsStatusChangedData
		if err := convertMapToStruct(e.Data, &data); err == nil {
			return &data
		}
	case AllocationTargetsChanged:
		var data AllocationTargetsChangedData
		if err := convertMapToStruct(e.Data, &data); err == nil {
			return &data
		}
	case PlannerConfigChanged:
		var data PlannerConfigChangedData
		if err := convertMapToStruct(e.Data, &data); err == nil {
			return &data
		}
	case ErrorOccurred:
		var data ErrorEventData
		if err := convertMapToStruct(e.Data, &data); err == nil {
			return &data
		}
	}

	return nil
}

// convertMapToStruct converts a map[string]interface{} to a struct
// This is a helper function for backward compatibility
func convertMapToStruct(m map[string]interface{}, v interface{}) error {
	jsonBytes, err := json.Marshal(m)
	if err != nil {
		return err
	}
	return json.Unmarshal(jsonBytes, v)
}

// Manager handles event emission and logging
type Manager struct {
	bus *Bus
	log zerolog.Logger
}

// NewManager creates a new event manager
func NewManager(bus *Bus, log zerolog.Logger) *Manager {
	return &Manager{
		bus: bus,
		log: log.With().Str("service", "events").Logger(),
	}
}

// Emit emits an event to the bus and logs it (legacy method with map[string]interface{})
func (m *Manager) Emit(eventType EventType, module string, data map[string]interface{}) {
	event := Event{
		Type:      eventType,
		Timestamp: time.Now(),
		Data:      data,
		Module:    module,
	}

	// Publish to bus
	m.bus.Emit(eventType, module, data)

	// Log event
	eventJSON, _ := json.Marshal(event)
	m.log.Info().
		Str("event_type", string(eventType)).
		Str("module", module).
		RawJSON("event", eventJSON).
		Msg("Event emitted")
}

// EmitTyped emits an event with typed data to the bus and logs it
func (m *Manager) EmitTyped(eventType EventType, module string, data EventData) {
	// Convert typed data to map for backward compatibility
	dataMap := convertEventDataToMap(data)

	event := Event{
		Type:      eventType,
		Timestamp: time.Now(),
		Data:      dataMap,
		Module:    module,
	}

	// Publish to bus
	m.bus.Emit(eventType, module, dataMap)

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
	data := &ErrorEventData{
		Error:   err.Error(),
		Context: context,
	}
	m.EmitTyped(ErrorOccurred, module, data)
}

// convertEventDataToMap converts typed EventData to map[string]interface{} for backward compatibility
func convertEventDataToMap(data EventData) map[string]interface{} {
	if data == nil {
		return nil
	}

	jsonBytes, err := json.Marshal(data)
	if err != nil {
		return nil
	}

	var result map[string]interface{}
	if err := json.Unmarshal(jsonBytes, &result); err != nil {
		return nil
	}

	return result
}
