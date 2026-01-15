package queue

import (
	"time"

	"github.com/aristath/sentinel/internal/events"
)

// ProgressReporter allows jobs to report progress during execution.
// Supports hierarchical progress with Phase, SubPhase, and Details for rich reporting.
type ProgressReporter struct {
	eventManager *events.Manager
	jobID        string
	jobType      JobType
	lastReport   time.Time
	minInterval  time.Duration // Minimum interval between progress reports
}

// NewProgressReporter creates a new progress reporter with throttling.
// Default throttle is 100ms (10 updates/sec max) for real-time feel.
func NewProgressReporter(em *events.Manager, jobID string, jobType JobType) *ProgressReporter {
	return &ProgressReporter{
		eventManager: em,
		jobID:        jobID,
		jobType:      jobType,
		minInterval:  100 * time.Millisecond, // Throttle to max 10 reports/second for real-time feel
	}
}

// Report emits a progress event (throttled to prevent flooding).
// 100% completion always bypasses the throttle.
func (pr *ProgressReporter) Report(current, total int, message string) {
	if pr.eventManager == nil {
		return
	}

	// Throttle: only report if enough time has passed OR if we're at 100%
	now := time.Now()
	if now.Sub(pr.lastReport) < pr.minInterval && current != total {
		return
	}
	pr.lastReport = now

	pr.eventManager.EmitTyped(events.JobProgress, "queue", &events.JobStatusData{
		JobID:       pr.jobID,
		JobType:     string(pr.jobType),
		Status:      "progress",
		Description: GetJobDescription(pr.jobType),
		Progress: &events.JobProgressInfo{
			Current: current,
			Total:   total,
			Message: message,
		},
		Timestamp: now,
	})
}

// ReportWithDetails emits a progress event with hierarchical phase information (throttled).
// Use this for rich progress reporting with phase, subphase, and arbitrary metrics.
func (pr *ProgressReporter) ReportWithDetails(current, total int, message, phase, subPhase string, details map[string]interface{}) {
	if pr.eventManager == nil {
		return
	}

	// Throttle: only report if enough time has passed OR if we're at 100%
	now := time.Now()
	if now.Sub(pr.lastReport) < pr.minInterval && current != total {
		return
	}
	pr.lastReport = now

	pr.eventManager.EmitTyped(events.JobProgress, "queue", &events.JobStatusData{
		JobID:       pr.jobID,
		JobType:     string(pr.jobType),
		Status:      "progress",
		Description: GetJobDescription(pr.jobType),
		Progress: &events.JobProgressInfo{
			Current:  current,
			Total:    total,
			Message:  message,
			Phase:    phase,
			SubPhase: subPhase,
			Details:  details,
		},
		Timestamp: now,
	})
}

// ReportUnthrottled emits a progress event that always bypasses the throttle.
// Use this for critical milestones (25%, 50%, 75%, 100%) or important state changes.
func (pr *ProgressReporter) ReportUnthrottled(current, total int, message string) {
	if pr.eventManager == nil {
		return
	}

	now := time.Now()
	pr.lastReport = now // Update lastReport to maintain throttle state

	pr.eventManager.EmitTyped(events.JobProgress, "queue", &events.JobStatusData{
		JobID:       pr.jobID,
		JobType:     string(pr.jobType),
		Status:      "progress",
		Description: GetJobDescription(pr.jobType),
		Progress: &events.JobProgressInfo{
			Current: current,
			Total:   total,
			Message: message,
		},
		Timestamp: now,
	})
}

// ReportUnthrottledWithDetails emits a progress event with full details that bypasses throttle.
// Use this for critical milestones or phase transitions that should always be reported.
func (pr *ProgressReporter) ReportUnthrottledWithDetails(current, total int, message, phase, subPhase string, details map[string]interface{}) {
	if pr.eventManager == nil {
		return
	}

	now := time.Now()
	pr.lastReport = now // Update lastReport to maintain throttle state

	pr.eventManager.EmitTyped(events.JobProgress, "queue", &events.JobStatusData{
		JobID:       pr.jobID,
		JobType:     string(pr.jobType),
		Status:      "progress",
		Description: GetJobDescription(pr.jobType),
		Progress: &events.JobProgressInfo{
			Current:  current,
			Total:    total,
			Message:  message,
			Phase:    phase,
			SubPhase: subPhase,
			Details:  details,
		},
		Timestamp: now,
	})
}

// ReportMessage emits a progress message without count (for indeterminate progress)
func (pr *ProgressReporter) ReportMessage(message string) {
	if pr.eventManager == nil {
		return
	}

	now := time.Now()
	if now.Sub(pr.lastReport) < pr.minInterval {
		return
	}
	pr.lastReport = now

	pr.eventManager.EmitTyped(events.JobProgress, "queue", &events.JobStatusData{
		JobID:       pr.jobID,
		JobType:     string(pr.jobType),
		Status:      "progress",
		Description: GetJobDescription(pr.jobType),
		Progress: &events.JobProgressInfo{
			Message: message,
		},
		Timestamp: now,
	})
}
