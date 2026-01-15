package events

import (
	"encoding/json"
	"time"
)

// EventData is the interface that all event data types must implement
// This allows for type-safe event data while maintaining flexibility
type EventData interface {
	// EventType returns the event type this data is associated with
	EventType() EventType
}

// PlanGeneratedData contains data for PlanGenerated events
type PlanGeneratedData struct {
	PortfolioHash string  `json:"portfolio_hash"`
	Steps         int     `json:"steps"`
	EndScore      float64 `json:"end_score"`
	Improvement   float64 `json:"improvement"`
	Feasible      bool    `json:"feasible"`
}

// EventType returns the event type for PlanGeneratedData
func (d *PlanGeneratedData) EventType() EventType {
	return PlanGenerated
}

// RecommendationsReadyData contains data for RecommendationsReady events
type RecommendationsReadyData struct {
	PortfolioHash string `json:"portfolio_hash"`
	Count         int    `json:"count"`
}

// EventType returns the event type for RecommendationsReadyData
func (d *RecommendationsReadyData) EventType() EventType {
	return RecommendationsReady
}

// PortfolioChangedData contains data for PortfolioChanged events
type PortfolioChangedData struct {
	SyncCompleted bool `json:"sync_completed"`
}

// EventType returns the event type for PortfolioChangedData
func (d *PortfolioChangedData) EventType() EventType {
	return PortfolioChanged
}

// PriceUpdatedData contains data for PriceUpdated events
type PriceUpdatedData struct {
	PricesSynced bool `json:"prices_synced"`
}

// EventType returns the event type for PriceUpdatedData
func (d *PriceUpdatedData) EventType() EventType {
	return PriceUpdated
}

// TradeExecutedData contains data for TradeExecuted events
type TradeExecutedData struct {
	Symbol   string  `json:"symbol"`
	Side     string  `json:"side"`
	Quantity float64 `json:"quantity"`
	Price    float64 `json:"price"`
	OrderID  string  `json:"order_id,omitempty"`
	Source   string  `json:"source,omitempty"`
}

// EventType returns the event type for TradeExecutedData
func (d *TradeExecutedData) EventType() EventType {
	return TradeExecuted
}

// SecurityAddedData contains data for SecurityAdded events
type SecurityAddedData struct {
	Symbol string `json:"symbol"`
	ISIN   string `json:"isin"`
	Name   string `json:"name"`
}

// EventType returns the event type for SecurityAddedData
func (d *SecurityAddedData) EventType() EventType {
	return SecurityAdded
}

// SecuritySyncedData contains data for SecuritySynced events
// This event has two variants - single security sync or batch sync
type SecuritySyncedData struct {
	// Single security sync fields
	ISIN   string   `json:"isin,omitempty"`
	Symbol string   `json:"symbol,omitempty"`
	Reason string   `json:"reason,omitempty"`
	Price  *float64 `json:"price,omitempty"`

	// Batch sync fields
	Processed *int `json:"processed,omitempty"`
	Errors    *int `json:"errors,omitempty"`
}

// EventType returns the event type for SecuritySyncedData
func (d *SecuritySyncedData) EventType() EventType {
	return SecuritySynced
}

// ScoreUpdatedData contains data for ScoreUpdated events
type ScoreUpdatedData struct {
	ISIN       string  `json:"isin"`
	Symbol     string  `json:"symbol"`
	TotalScore float64 `json:"total_score"`
}

// EventType returns the event type for ScoreUpdatedData
func (d *ScoreUpdatedData) EventType() EventType {
	return ScoreUpdated
}

// StateChangedData contains data for StateChanged events
type StateChangedData struct {
	OldHash string `json:"old_hash"`
	NewHash string `json:"new_hash"`
}

// EventType returns the event type for StateChangedData
func (d *StateChangedData) EventType() EventType {
	return StateChanged
}

// SettingsChangedData contains data for SettingsChanged events
type SettingsChangedData struct {
	Key   string      `json:"key"`
	Value interface{} `json:"value"`
}

// EventType returns the event type for SettingsChangedData
func (d *SettingsChangedData) EventType() EventType {
	return SettingsChanged
}

// SystemStatusChangedData contains data for SystemStatusChanged events
type SystemStatusChangedData struct {
	Status    string `json:"status,omitempty"`
	Timestamp string `json:"timestamp"`
}

// EventType returns the event type for SystemStatusChangedData
func (d *SystemStatusChangedData) EventType() EventType {
	return SystemStatusChanged
}

// TradernetStatusChangedData contains data for TradernetStatusChanged events
type TradernetStatusChangedData struct {
	Connected bool   `json:"connected"`
	Timestamp string `json:"timestamp"`
}

// EventType returns the event type for TradernetStatusChangedData
func (d *TradernetStatusChangedData) EventType() EventType {
	return TradernetStatusChanged
}

// MarketStatusData represents individual market status (matches tradernet.MarketStatusData)
type MarketStatusData struct {
	Name      string `json:"name"`
	Code      string `json:"code"`
	Status    string `json:"status"`     // "open", "closed", "pre_open", "post_close"
	OpenTime  string `json:"open_time"`  // "09:30"
	CloseTime string `json:"close_time"` // "16:00"
	Date      string `json:"date"`       // "2024-01-09"
	UpdatedAt string `json:"updated_at"` // ISO 8601 timestamp
}

// MarketsStatusChangedData contains data for MarketsStatusChanged events
type MarketsStatusChangedData struct {
	Markets     map[string]MarketStatusData `json:"markets"` // Keyed by exchange code (XNAS, XNYS, etc.)
	OpenCount   int                         `json:"open_count"`
	ClosedCount int                         `json:"closed_count"`
	LastUpdated string                      `json:"last_updated"` // ISO 8601 timestamp
}

// EventType returns the event type for MarketsStatusChangedData
func (d *MarketsStatusChangedData) EventType() EventType {
	return MarketsStatusChanged
}

// AllocationTargetsChangedData contains data for AllocationTargetsChanged events
type AllocationTargetsChangedData struct {
	Type  string `json:"type"`
	Count int    `json:"count,omitempty"`
}

// EventType returns the event type for AllocationTargetsChangedData
func (d *AllocationTargetsChangedData) EventType() EventType {
	return AllocationTargetsChanged
}

// PlannerConfigChangedData contains data for PlannerConfigChanged events
type PlannerConfigChangedData struct {
	ConfigID int64  `json:"config_id"`
	Action   string `json:"action"`
	Name     string `json:"name,omitempty"`
}

// EventType returns the event type for PlannerConfigChangedData
func (d *PlannerConfigChangedData) EventType() EventType {
	return PlannerConfigChanged
}

// ErrorEventData contains data for ErrorOccurred events
type ErrorEventData struct {
	Error   string                 `json:"error"`
	Context map[string]interface{} `json:"context,omitempty"`
}

// EventType returns the event type for ErrorEventData
func (d *ErrorEventData) EventType() EventType {
	return ErrorOccurred
}

// JobProgressInfo contains progress information for a job.
// Supports hierarchical progress with Phase, SubPhase, and Details for rich progress reporting.
type JobProgressInfo struct {
	Current int    `json:"current"`
	Total   int    `json:"total"`
	Message string `json:"message,omitempty"`

	// Phase identifies the current high-level operation (e.g., "opportunity_identification",
	// "sequence_generation", "sequence_evaluation")
	Phase string `json:"phase,omitempty"`

	// SubPhase identifies the specific sub-operation within a phase (e.g., "profit_taking",
	// "depth_3", "batch_1")
	SubPhase string `json:"sub_phase,omitempty"`

	// Details contains arbitrary key-value metrics for the current phase.
	// Common keys include:
	// - For opportunity_identification: calculators_total, calculators_done, candidates_so_far, filtered_so_far
	// - For sequence_generation: candidates_count, current_depth, combinations_at_depth, sequences_generated
	// - For sequence_evaluation: workers_active, feasible_count, infeasible_count, best_score, sequences_per_second
	Details map[string]interface{} `json:"details,omitempty"`
}

// JobStatusData contains data for job lifecycle events
type JobStatusData struct {
	JobID       string                 `json:"job_id"`
	JobType     string                 `json:"job_type"`
	Status      string                 `json:"status"` // "started", "progress", "completed", "failed"
	Description string                 `json:"description"`
	Progress    *JobProgressInfo       `json:"progress,omitempty"`
	Error       string                 `json:"error,omitempty"`
	Duration    float64                `json:"duration,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
	Timestamp   time.Time              `json:"timestamp"`
}

// EventType returns the event type for JobStatusData
// Note: The actual event type is determined by the Status field
func (d *JobStatusData) EventType() EventType {
	switch d.Status {
	case "started":
		return JobStarted
	case "progress":
		return JobProgress
	case "completed":
		return JobCompleted
	case "failed":
		return JobFailed
	default:
		return JobStarted
	}
}

// EventWithData represents an event with typed data
type EventWithData struct {
	Type      EventType `json:"type"`
	Timestamp time.Time `json:"timestamp"`
	Module    string    `json:"module"`
	Data      EventData `json:"data"`
}

// MarshalJSON customizes JSON serialization for EventWithData
func (e *EventWithData) MarshalJSON() ([]byte, error) {
	type Alias EventWithData
	aux := &struct {
		Data json.RawMessage `json:"data"`
		*Alias
	}{
		Alias: (*Alias)(e),
	}

	// Marshal the data separately
	if e.Data != nil {
		dataBytes, err := json.Marshal(e.Data)
		if err != nil {
			return nil, err
		}
		aux.Data = dataBytes
	}

	return json.Marshal(aux)
}

// UnmarshalJSON customizes JSON deserialization for EventWithData
func (e *EventWithData) UnmarshalJSON(data []byte) error {
	type Alias EventWithData
	aux := &struct {
		Data json.RawMessage `json:"data"`
		*Alias
	}{
		Alias: (*Alias)(e),
	}

	if err := json.Unmarshal(data, aux); err != nil {
		return err
	}

	// Unmarshal data based on event type
	if len(aux.Data) > 0 {
		var eventData EventData
		switch aux.Type {
		case PlanGenerated:
			eventData = &PlanGeneratedData{}
		case RecommendationsReady:
			eventData = &RecommendationsReadyData{}
		case PortfolioChanged:
			eventData = &PortfolioChangedData{}
		case PriceUpdated:
			eventData = &PriceUpdatedData{}
		case TradeExecuted:
			eventData = &TradeExecutedData{}
		case SecurityAdded:
			eventData = &SecurityAddedData{}
		case SecuritySynced:
			eventData = &SecuritySyncedData{}
		case ScoreUpdated:
			eventData = &ScoreUpdatedData{}
		case SettingsChanged:
			eventData = &SettingsChangedData{}
		case SystemStatusChanged:
			eventData = &SystemStatusChangedData{}
		case TradernetStatusChanged:
			eventData = &TradernetStatusChangedData{}
		case MarketsStatusChanged:
			eventData = &MarketsStatusChangedData{}
		case AllocationTargetsChanged:
			eventData = &AllocationTargetsChangedData{}
		case PlannerConfigChanged:
			eventData = &PlannerConfigChangedData{}
		case ErrorOccurred:
			eventData = &ErrorEventData{}
		case JobStarted, JobProgress, JobCompleted, JobFailed:
			eventData = &JobStatusData{}
		default:
			// For unknown types, use raw map
			var rawData map[string]interface{}
			if err := json.Unmarshal(aux.Data, &rawData); err != nil {
				return err
			}
			// Convert to generic data type
			eventData = &GenericEventData{Data: rawData}
		}

		if eventData != nil {
			if err := json.Unmarshal(aux.Data, eventData); err != nil {
				return err
			}
			e.Data = eventData
		}
	}

	return nil
}

// GenericEventData is a fallback for events that don't have a specific type
type GenericEventData struct {
	Type EventType              `json:"-"`
	Data map[string]interface{} `json:"-"`
}

// EventType returns the event type for GenericEventData
func (d *GenericEventData) EventType() EventType {
	return d.Type
}

// MarshalJSON customizes JSON serialization for GenericEventData
func (d *GenericEventData) MarshalJSON() ([]byte, error) {
	return json.Marshal(d.Data)
}

// UnmarshalJSON customizes JSON deserialization for GenericEventData
func (d *GenericEventData) UnmarshalJSON(data []byte) error {
	return json.Unmarshal(data, &d.Data)
}
