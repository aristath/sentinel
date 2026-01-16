package work

import (
	"sync"
	"time"
)

// ProgressReporter provides progress reporting for work items.
// It emits events that can be consumed by the Activity UI to show real-time progress.
type ProgressReporter struct {
	eventEmitter EventEmitter
	workID       string
	workType     string
	subject      string

	// Throttling to avoid spam
	lastReport time.Time
	mu         sync.Mutex
}

// EventEmitter defines the interface for emitting events
type EventEmitter interface {
	Emit(event string, data any)
}

// ProgressEvent is emitted during work execution
type ProgressEvent struct {
	WorkID   string         `json:"work_id"`
	WorkType string         `json:"work_type"`
	Subject  string         `json:"subject,omitempty"`
	Current  int            `json:"current,omitempty"`
	Total    int            `json:"total,omitempty"`
	Phase    string         `json:"phase,omitempty"`
	Message  string         `json:"message,omitempty"`
	Details  map[string]any `json:"details,omitempty"`
}

// WorkStartedEvent is emitted when a work item begins execution
type WorkStartedEvent struct {
	WorkID   string `json:"work_id"`
	WorkType string `json:"work_type"`
	Subject  string `json:"subject,omitempty"`
}

// WorkCompletedEvent is emitted when a work item completes successfully
type WorkCompletedEvent struct {
	WorkID   string        `json:"work_id"`
	WorkType string        `json:"work_type"`
	Subject  string        `json:"subject,omitempty"`
	Duration time.Duration `json:"duration_ms"`
}

// WorkFailedEvent is emitted when a work item fails
type WorkFailedEvent struct {
	WorkID   string        `json:"work_id"`
	WorkType string        `json:"work_type"`
	Subject  string        `json:"subject,omitempty"`
	Error    string        `json:"error"`
	Duration time.Duration `json:"duration_ms"`
	Retries  int           `json:"retries"`
}

// Event names for work lifecycle
const (
	EventJobStarted   = "JobStarted"
	EventJobProgress  = "JobProgress"
	EventJobCompleted = "JobCompleted"
	EventJobFailed    = "JobFailed"
)

// Throttle interval for progress events (avoid spam)
const progressThrottleInterval = 100 * time.Millisecond

// NewProgressReporter creates a new progress reporter for a work item
func NewProgressReporter(emitter EventEmitter, workID, workType, subject string) *ProgressReporter {
	return &ProgressReporter{
		eventEmitter: emitter,
		workID:       workID,
		workType:     workType,
		subject:      subject,
	}
}

// Report reports numeric progress (current/total) with a message.
// Progress events are throttled to avoid spam.
func (r *ProgressReporter) Report(current, total int, message string) {
	r.ReportWithDetails(current, total, message, nil)
}

// ReportPhase reports a named phase with a message.
// This is useful for work that has distinct phases rather than numeric progress.
func (r *ProgressReporter) ReportPhase(phase, message string) {
	if r == nil || r.eventEmitter == nil {
		return
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	// Throttle progress events
	if time.Since(r.lastReport) < progressThrottleInterval {
		return
	}
	r.lastReport = time.Now()

	r.eventEmitter.Emit(EventJobProgress, ProgressEvent{
		WorkID:   r.workID,
		WorkType: r.workType,
		Subject:  r.subject,
		Phase:    phase,
		Message:  message,
	})
}

// ReportWithDetails reports progress with additional custom details.
// Details can contain arbitrary key-value data for the UI.
func (r *ProgressReporter) ReportWithDetails(current, total int, message string, details map[string]any) {
	if r == nil || r.eventEmitter == nil {
		return
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	// Throttle progress events
	if time.Since(r.lastReport) < progressThrottleInterval {
		return
	}
	r.lastReport = time.Now()

	r.eventEmitter.Emit(EventJobProgress, ProgressEvent{
		WorkID:   r.workID,
		WorkType: r.workType,
		Subject:  r.subject,
		Current:  current,
		Total:    total,
		Message:  message,
		Details:  details,
	})
}

// emitStarted emits a JobStarted event
func (r *ProgressReporter) emitStarted() {
	if r == nil || r.eventEmitter == nil {
		return
	}

	r.eventEmitter.Emit(EventJobStarted, WorkStartedEvent{
		WorkID:   r.workID,
		WorkType: r.workType,
		Subject:  r.subject,
	})
}

// emitCompleted emits a JobCompleted event
func (r *ProgressReporter) emitCompleted(duration time.Duration) {
	if r == nil || r.eventEmitter == nil {
		return
	}

	r.eventEmitter.Emit(EventJobCompleted, WorkCompletedEvent{
		WorkID:   r.workID,
		WorkType: r.workType,
		Subject:  r.subject,
		Duration: duration,
	})
}

// emitFailed emits a JobFailed event
func (r *ProgressReporter) emitFailed(err error, duration time.Duration, retries int) {
	if r == nil || r.eventEmitter == nil {
		return
	}

	errMsg := ""
	if err != nil {
		errMsg = err.Error()
	}

	r.eventEmitter.Emit(EventJobFailed, WorkFailedEvent{
		WorkID:   r.workID,
		WorkType: r.workType,
		Subject:  r.subject,
		Error:    errMsg,
		Duration: duration,
		Retries:  retries,
	})
}
