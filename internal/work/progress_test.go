package work

import (
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// mockEmitter captures emitted events for testing
type mockEmitter struct {
	mu     sync.Mutex
	events []emittedEvent
}

type emittedEvent struct {
	event string
	data  any
}

func (m *mockEmitter) Emit(event string, data any) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.events = append(m.events, emittedEvent{event: event, data: data})
}

func (m *mockEmitter) getEvents() []emittedEvent {
	m.mu.Lock()
	defer m.mu.Unlock()
	result := make([]emittedEvent, len(m.events))
	copy(result, m.events)
	return result
}

func TestNewProgressReporter(t *testing.T) {
	emitter := &mockEmitter{}
	reporter := NewProgressReporter(emitter, "planner:weights", "planner:weights", "")

	assert.NotNil(t, reporter)
	assert.Equal(t, "planner:weights", reporter.workID)
	assert.Equal(t, "planner:weights", reporter.workType)
	assert.Equal(t, "", reporter.subject)
}

func TestProgressReporter_Report(t *testing.T) {
	emitter := &mockEmitter{}
	reporter := NewProgressReporter(emitter, "security:sync:NL123", "security:sync", "NL123")

	reporter.Report(1, 10, "Processing step 1")

	events := emitter.getEvents()
	require.Len(t, events, 1)
	assert.Equal(t, EventJobProgress, events[0].event)

	progressEvent, ok := events[0].data.(ProgressEvent)
	require.True(t, ok)
	assert.Equal(t, "security:sync:NL123", progressEvent.WorkID)
	assert.Equal(t, "security:sync", progressEvent.WorkType)
	assert.Equal(t, "NL123", progressEvent.Subject)
	assert.Equal(t, 1, progressEvent.Current)
	assert.Equal(t, 10, progressEvent.Total)
	assert.Equal(t, "Processing step 1", progressEvent.Message)
}

func TestProgressReporter_ReportPhase(t *testing.T) {
	emitter := &mockEmitter{}
	reporter := NewProgressReporter(emitter, "planner:weights", "planner:weights", "")

	reporter.ReportPhase("Calculating", "Computing optimizer weights...")

	events := emitter.getEvents()
	require.Len(t, events, 1)
	assert.Equal(t, EventJobProgress, events[0].event)

	progressEvent, ok := events[0].data.(ProgressEvent)
	require.True(t, ok)
	assert.Equal(t, "Calculating", progressEvent.Phase)
	assert.Equal(t, "Computing optimizer weights...", progressEvent.Message)
}

func TestProgressReporter_ReportWithDetails(t *testing.T) {
	emitter := &mockEmitter{}
	reporter := NewProgressReporter(emitter, "sync:portfolio", "sync:portfolio", "")

	details := map[string]any{
		"positions_synced": 25,
		"total_value":      10000.50,
	}
	reporter.ReportWithDetails(5, 5, "Sync complete", details)

	events := emitter.getEvents()
	require.Len(t, events, 1)

	progressEvent, ok := events[0].data.(ProgressEvent)
	require.True(t, ok)
	assert.Equal(t, 5, progressEvent.Current)
	assert.Equal(t, 5, progressEvent.Total)
	assert.Equal(t, "Sync complete", progressEvent.Message)
	assert.Equal(t, 25, progressEvent.Details["positions_synced"])
	assert.Equal(t, 10000.50, progressEvent.Details["total_value"])
}

func TestProgressReporter_Throttling(t *testing.T) {
	emitter := &mockEmitter{}
	reporter := NewProgressReporter(emitter, "test:work", "test:work", "")

	// Rapid-fire reports should be throttled
	for i := 0; i < 100; i++ {
		reporter.Report(i, 100, "Progress")
	}

	// Should have fewer than 100 events due to throttling
	events := emitter.getEvents()
	assert.Less(t, len(events), 10, "Throttling should limit event count")
	assert.Greater(t, len(events), 0, "At least one event should be emitted")
}

func TestProgressReporter_ThrottlingAllowsAfterInterval(t *testing.T) {
	emitter := &mockEmitter{}
	reporter := NewProgressReporter(emitter, "test:work", "test:work", "")

	reporter.Report(1, 10, "First")
	time.Sleep(progressThrottleInterval + 10*time.Millisecond)
	reporter.Report(2, 10, "Second")

	events := emitter.getEvents()
	assert.Len(t, events, 2, "Both events should be emitted after throttle interval")
}

func TestProgressReporter_NilEmitter(t *testing.T) {
	// Should not panic with nil emitter
	reporter := NewProgressReporter(nil, "test:work", "test:work", "")

	assert.NotPanics(t, func() {
		reporter.Report(1, 10, "Test")
		reporter.ReportPhase("Phase", "Message")
		reporter.ReportWithDetails(1, 10, "Test", nil)
		reporter.emitStarted()
		reporter.emitCompleted(time.Second)
		reporter.emitFailed(nil, time.Second, 1)
	})
}

func TestProgressReporter_NilReporter(t *testing.T) {
	// Should not panic with nil reporter
	var reporter *ProgressReporter

	assert.NotPanics(t, func() {
		reporter.Report(1, 10, "Test")
		reporter.ReportPhase("Phase", "Message")
		reporter.ReportWithDetails(1, 10, "Test", nil)
		reporter.emitStarted()
		reporter.emitCompleted(time.Second)
		reporter.emitFailed(nil, time.Second, 1)
	})
}

func TestProgressReporter_EmitStarted(t *testing.T) {
	emitter := &mockEmitter{}
	reporter := NewProgressReporter(emitter, "planner:weights", "planner:weights", "")

	reporter.emitStarted()

	events := emitter.getEvents()
	require.Len(t, events, 1)
	assert.Equal(t, EventJobStarted, events[0].event)

	startedEvent, ok := events[0].data.(WorkStartedEvent)
	require.True(t, ok)
	assert.Equal(t, "planner:weights", startedEvent.WorkID)
	assert.Equal(t, "planner:weights", startedEvent.WorkType)
	assert.Equal(t, "", startedEvent.Subject)
}

func TestProgressReporter_EmitCompleted(t *testing.T) {
	emitter := &mockEmitter{}
	reporter := NewProgressReporter(emitter, "security:sync:NL123", "security:sync", "NL123")

	reporter.emitCompleted(5 * time.Second)

	events := emitter.getEvents()
	require.Len(t, events, 1)
	assert.Equal(t, EventJobCompleted, events[0].event)

	completedEvent, ok := events[0].data.(WorkCompletedEvent)
	require.True(t, ok)
	assert.Equal(t, "security:sync:NL123", completedEvent.WorkID)
	assert.Equal(t, "security:sync", completedEvent.WorkType)
	assert.Equal(t, "NL123", completedEvent.Subject)
	assert.Equal(t, 5*time.Second, completedEvent.Duration)
}

func TestProgressReporter_EmitFailed(t *testing.T) {
	emitter := &mockEmitter{}
	reporter := NewProgressReporter(emitter, "sync:portfolio", "sync:portfolio", "")

	testErr := assert.AnError
	reporter.emitFailed(testErr, 3*time.Second, 2)

	events := emitter.getEvents()
	require.Len(t, events, 1)
	assert.Equal(t, EventJobFailed, events[0].event)

	failedEvent, ok := events[0].data.(WorkFailedEvent)
	require.True(t, ok)
	assert.Equal(t, "sync:portfolio", failedEvent.WorkID)
	assert.Equal(t, "sync:portfolio", failedEvent.WorkType)
	assert.Equal(t, "", failedEvent.Subject)
	assert.Equal(t, testErr.Error(), failedEvent.Error)
	assert.Equal(t, 3*time.Second, failedEvent.Duration)
	assert.Equal(t, 2, failedEvent.Retries)
}

func TestProgressReporter_EmitFailedWithNilError(t *testing.T) {
	emitter := &mockEmitter{}
	reporter := NewProgressReporter(emitter, "test:work", "test:work", "")

	reporter.emitFailed(nil, time.Second, 0)

	events := emitter.getEvents()
	require.Len(t, events, 1)

	failedEvent, ok := events[0].data.(WorkFailedEvent)
	require.True(t, ok)
	assert.Equal(t, "", failedEvent.Error)
}

func TestEventConstants(t *testing.T) {
	assert.Equal(t, "JobStarted", EventJobStarted)
	assert.Equal(t, "JobProgress", EventJobProgress)
	assert.Equal(t, "JobCompleted", EventJobCompleted)
	assert.Equal(t, "JobFailed", EventJobFailed)
}
