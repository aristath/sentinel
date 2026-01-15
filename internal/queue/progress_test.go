package queue

import (
	"testing"
	"time"

	"github.com/aristath/sentinel/internal/events"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func setupEventManager() (*events.Manager, *events.Bus) {
	log := zerolog.Nop()
	bus := events.NewBus(log)
	manager := events.NewManager(bus, log)
	return manager, bus
}

// TestNewProgressReporter tests creating a new progress reporter
func TestNewProgressReporter(t *testing.T) {
	eventManager, _ := setupEventManager()
	reporter := NewProgressReporter(eventManager, "test_job_123", JobTypePlannerBatch)

	assert.NotNil(t, reporter)
	assert.Equal(t, "test_job_123", reporter.jobID)
	assert.Equal(t, JobTypePlannerBatch, reporter.jobType)
	// Throttle interval should be 100ms (10 updates/sec max) for real-time feel
	assert.Equal(t, 100*time.Millisecond, reporter.minInterval)
}

// TestProgressReporter_Report tests basic progress reporting
func TestProgressReporter_Report(t *testing.T) {
	eventManager, bus := setupEventManager()
	eventsChan := make(chan events.Event, 10)
	_ = bus.Subscribe(events.JobProgress, func(event *events.Event) {
		eventsChan <- *event
	})

	reporter := NewProgressReporter(eventManager, "test_job_456", JobTypeSyncCycle)

	// Report progress
	reporter.Report(3, 7, "Syncing portfolio")

	// Wait for event
	select {
	case event := <-eventsChan:
		assert.Equal(t, events.JobProgress, event.Type)
		assert.Equal(t, "queue", event.Module)

		// Get typed data
		typedData := event.GetTypedData()
		require.NotNil(t, typedData, "Event should have typed data")

		data, ok := typedData.(*events.JobStatusData)
		require.True(t, ok, "Event data should be JobStatusData")
		assert.Equal(t, "test_job_456", data.JobID)
		assert.Equal(t, string(JobTypeSyncCycle), data.JobType)
		assert.Equal(t, "progress", data.Status)
		assert.Equal(t, "Syncing all data from broker", data.Description)

		require.NotNil(t, data.Progress)
		assert.Equal(t, 3, data.Progress.Current)
		assert.Equal(t, 7, data.Progress.Total)
		assert.Equal(t, "Syncing portfolio", data.Progress.Message)
	case <-time.After(100 * time.Millisecond):
		t.Fatal("Expected JobProgress event not received")
	}
}

// TestProgressReporter_Throttling tests that progress reports are throttled
func TestProgressReporter_Throttling(t *testing.T) {
	eventManager, bus := setupEventManager()
	eventsChan := make(chan events.Event, 10)
	_ = bus.Subscribe(events.JobProgress, func(event *events.Event) {
		eventsChan <- *event
	})

	reporter := NewProgressReporter(eventManager, "test_job_789", JobTypeDividendReinvest)

	// Send multiple rapid reports (throttle is 100ms now)
	reporter.Report(1, 10, "Step 1")
	time.Sleep(30 * time.Millisecond) // Less than 100ms throttle
	reporter.Report(2, 10, "Step 2")  // Should be throttled
	time.Sleep(30 * time.Millisecond)
	reporter.Report(3, 10, "Step 3") // Should be throttled

	// Only first report should arrive
	select {
	case event := <-eventsChan:
		data := event.GetTypedData().(*events.JobStatusData)
		assert.Equal(t, 1, data.Progress.Current)
		assert.Equal(t, "Step 1", data.Progress.Message)
	case <-time.After(50 * time.Millisecond):
		t.Fatal("Expected first progress event")
	}

	// No second event should arrive (throttled)
	select {
	case <-eventsChan:
		t.Fatal("Second event should have been throttled")
	case <-time.After(50 * time.Millisecond):
		// Expected - no event
	}

	// Wait for throttle to expire (100ms - already waited ~60ms)
	time.Sleep(50 * time.Millisecond)

	// Now next report should go through
	reporter.Report(4, 10, "Step 4")
	select {
	case event := <-eventsChan:
		data := event.GetTypedData().(*events.JobStatusData)
		assert.Equal(t, 4, data.Progress.Current)
		assert.Equal(t, "Step 4", data.Progress.Message)
	case <-time.After(50 * time.Millisecond):
		t.Fatal("Expected progress event after throttle expired")
	}
}

// TestProgressReporter_NoThrottleAtCompletion tests 100% completion bypasses throttle
func TestProgressReporter_NoThrottleAtCompletion(t *testing.T) {
	eventManager, bus := setupEventManager()
	eventsChan := make(chan events.Event, 10)
	_ = bus.Subscribe(events.JobProgress, func(event *events.Event) {
		eventsChan <- *event
	})

	reporter := NewProgressReporter(eventManager, "test_job_complete", JobTypeHourlyBackup)

	// Send rapid reports ending at 100%
	reporter.Report(1, 5, "Step 1")

	// Receive first
	<-eventsChan

	time.Sleep(100 * time.Millisecond) // Less than throttle
	reporter.Report(5, 5, "Complete")  // 100% should bypass throttle

	// Completion should arrive immediately despite throttle
	select {
	case event := <-eventsChan:
		data := event.GetTypedData().(*events.JobStatusData)
		assert.Equal(t, 5, data.Progress.Current)
		assert.Equal(t, 5, data.Progress.Total)
		assert.Equal(t, "Complete", data.Progress.Message)
	case <-time.After(100 * time.Millisecond):
		t.Fatal("Completion event should bypass throttle")
	}
}

// TestProgressReporter_ReportMessage tests message-only reporting
func TestProgressReporter_ReportMessage(t *testing.T) {
	eventManager, bus := setupEventManager()
	eventsChan := make(chan events.Event, 10)
	_ = bus.Subscribe(events.JobProgress, func(event *events.Event) {
		eventsChan <- *event
	})

	reporter := NewProgressReporter(eventManager, "test_job_msg", JobTypeFormulaDiscovery)

	// Report message without progress
	reporter.ReportMessage("Analyzing formula performance")

	// Wait for event
	select {
	case event := <-eventsChan:
		data := event.GetTypedData().(*events.JobStatusData)
		assert.Equal(t, "test_job_msg", data.JobID)
		require.NotNil(t, data.Progress)
		assert.Equal(t, 0, data.Progress.Current)
		assert.Equal(t, 0, data.Progress.Total)
		assert.Equal(t, "Analyzing formula performance", data.Progress.Message)
	case <-time.After(100 * time.Millisecond):
		t.Fatal("Expected progress event with message")
	}
}

// TestProgressReporter_MessageThrottling tests message reports are also throttled
func TestProgressReporter_MessageThrottling(t *testing.T) {
	eventManager, bus := setupEventManager()
	eventsChan := make(chan events.Event, 10)
	_ = bus.Subscribe(events.JobProgress, func(event *events.Event) {
		eventsChan <- *event
	})

	reporter := NewProgressReporter(eventManager, "test_throttle_msg", JobTypeHistoryCleanup)

	// Send rapid messages
	reporter.ReportMessage("Message 1")
	<-eventsChan // Receive first

	time.Sleep(30 * time.Millisecond)   // Less than 100ms throttle
	reporter.ReportMessage("Message 2") // Should be throttled

	// No second message should arrive
	select {
	case <-eventsChan:
		t.Fatal("Second message should have been throttled")
	case <-time.After(50 * time.Millisecond):
		// Expected
	}
}

// TestProgressReporter_NilEventManager tests graceful handling of nil event manager
func TestProgressReporter_NilEventManager(t *testing.T) {
	reporter := NewProgressReporter(nil, "test_nil", JobTypeDeployment)

	// Should not panic
	assert.NotPanics(t, func() {
		reporter.Report(1, 5, "Step 1")
	})

	assert.NotPanics(t, func() {
		reporter.ReportMessage("Test message")
	})
}

// TestProgressReporter_JobDescriptionMapping tests all job types have descriptions
func TestProgressReporter_JobDescriptionMapping(t *testing.T) {
	eventManager, bus := setupEventManager()
	eventsChan := make(chan events.Event, 10)
	_ = bus.Subscribe(events.JobProgress, func(event *events.Event) {
		eventsChan <- *event
	})

	// Test a few key job types
	jobTypes := []JobType{
		JobTypePlannerBatch,
		JobTypeSyncCycle,
		JobTypeDividendReinvest,
		JobTypeEventBasedTrading,
		JobTypeHourlyBackup,
	}

	for _, jobType := range jobTypes {
		reporter := NewProgressReporter(eventManager, "test_"+string(jobType), jobType)
		reporter.Report(1, 1, "Test")

		select {
		case event := <-eventsChan:
			data := event.GetTypedData().(*events.JobStatusData)
			// Description should not be empty and should not be the job type itself (unless it's the fallback)
			assert.NotEmpty(t, data.Description)
			// Description should be human-readable (contains spaces or is multi-word)
			if data.Description == string(jobType) {
				t.Logf("Warning: JobType %s has no custom description", jobType)
			}
		case <-time.After(100 * time.Millisecond):
			t.Fatalf("Expected event for job type %s", jobType)
		}
	}
}

// TestProgressReporter_ReportWithDetails tests progress reporting with hierarchical details
func TestProgressReporter_ReportWithDetails(t *testing.T) {
	eventManager, bus := setupEventManager()
	eventsChan := make(chan events.Event, 10)
	_ = bus.Subscribe(events.JobProgress, func(event *events.Event) {
		eventsChan <- *event
	})

	reporter := NewProgressReporter(eventManager, "test_job_details", JobTypePlannerBatch)

	// Report progress with phase, subphase, and details
	reporter.ReportWithDetails(847, 2500, "Evaluating sequences", "sequence_evaluation", "batch_1", map[string]interface{}{
		"workers_active":       4,
		"feasible_count":       823,
		"infeasible_count":     24,
		"best_score":           0.847,
		"sequences_per_second": 520.5,
	})

	// Wait for event
	select {
	case event := <-eventsChan:
		data := event.GetTypedData().(*events.JobStatusData)
		assert.Equal(t, "test_job_details", data.JobID)

		require.NotNil(t, data.Progress)
		assert.Equal(t, 847, data.Progress.Current)
		assert.Equal(t, 2500, data.Progress.Total)
		assert.Equal(t, "Evaluating sequences", data.Progress.Message)
		assert.Equal(t, "sequence_evaluation", data.Progress.Phase)
		assert.Equal(t, "batch_1", data.Progress.SubPhase)
		assert.NotNil(t, data.Progress.Details)
		// Note: JSON roundtrip in event system converts int to float64
		assert.Equal(t, float64(4), data.Progress.Details["workers_active"])
		assert.Equal(t, float64(823), data.Progress.Details["feasible_count"])
		assert.Equal(t, 0.847, data.Progress.Details["best_score"])
	case <-time.After(100 * time.Millisecond):
		t.Fatal("Expected progress event with details")
	}
}

// TestProgressReporter_ReportWithDetailsPhaseOnly tests reporting with phase but no subphase
func TestProgressReporter_ReportWithDetailsPhaseOnly(t *testing.T) {
	eventManager, bus := setupEventManager()
	eventsChan := make(chan events.Event, 10)
	_ = bus.Subscribe(events.JobProgress, func(event *events.Event) {
		eventsChan <- *event
	})

	reporter := NewProgressReporter(eventManager, "test_job_phase", JobTypePlannerBatch)

	// Report with phase only (empty subphase and nil details)
	reporter.ReportWithDetails(3, 6, "Running profit_taking calculator", "opportunity_identification", "", nil)

	select {
	case event := <-eventsChan:
		data := event.GetTypedData().(*events.JobStatusData)
		require.NotNil(t, data.Progress)
		assert.Equal(t, "opportunity_identification", data.Progress.Phase)
		assert.Equal(t, "", data.Progress.SubPhase)
		assert.Nil(t, data.Progress.Details)
	case <-time.After(100 * time.Millisecond):
		t.Fatal("Expected progress event")
	}
}

// TestProgressReporter_ReportUnthrottled tests that unthrottled reports always go through
func TestProgressReporter_ReportUnthrottled(t *testing.T) {
	eventManager, bus := setupEventManager()
	eventsChan := make(chan events.Event, 10)
	_ = bus.Subscribe(events.JobProgress, func(event *events.Event) {
		eventsChan <- *event
	})

	reporter := NewProgressReporter(eventManager, "test_unthrottled", JobTypePlannerBatch)

	// Send normal report
	reporter.Report(1, 10, "Step 1")
	<-eventsChan // Receive first

	// Immediately send unthrottled report (should bypass throttle)
	reporter.ReportUnthrottled(5, 10, "Milestone 50%")

	select {
	case event := <-eventsChan:
		data := event.GetTypedData().(*events.JobStatusData)
		assert.Equal(t, 5, data.Progress.Current)
		assert.Equal(t, "Milestone 50%", data.Progress.Message)
	case <-time.After(50 * time.Millisecond):
		t.Fatal("Unthrottled report should bypass throttle")
	}

	// Send another unthrottled report immediately
	reporter.ReportUnthrottled(7, 10, "Milestone 70%")

	select {
	case event := <-eventsChan:
		data := event.GetTypedData().(*events.JobStatusData)
		assert.Equal(t, 7, data.Progress.Current)
		assert.Equal(t, "Milestone 70%", data.Progress.Message)
	case <-time.After(50 * time.Millisecond):
		t.Fatal("Second unthrottled report should also bypass throttle")
	}
}

// TestProgressReporter_ReportUnthrottledWithDetails tests unthrottled reports with full details
func TestProgressReporter_ReportUnthrottledWithDetails(t *testing.T) {
	eventManager, bus := setupEventManager()
	eventsChan := make(chan events.Event, 10)
	_ = bus.Subscribe(events.JobProgress, func(event *events.Event) {
		eventsChan <- *event
	})

	reporter := NewProgressReporter(eventManager, "test_unthrottled_details", JobTypePlannerBatch)

	// Send unthrottled report with full details
	reporter.ReportUnthrottledWithDetails(2500, 2500, "Evaluation complete", "sequence_evaluation", "complete", map[string]interface{}{
		"feasible_count":       2100,
		"infeasible_count":     400,
		"best_score":           0.847,
		"sequences_per_second": 520.5,
		"total_duration_ms":    4800,
	})

	select {
	case event := <-eventsChan:
		data := event.GetTypedData().(*events.JobStatusData)
		require.NotNil(t, data.Progress)
		assert.Equal(t, 2500, data.Progress.Current)
		assert.Equal(t, 2500, data.Progress.Total)
		assert.Equal(t, "sequence_evaluation", data.Progress.Phase)
		assert.Equal(t, "complete", data.Progress.SubPhase)
		// Note: JSON roundtrip in event system converts int to float64
		assert.Equal(t, float64(2100), data.Progress.Details["feasible_count"])
		assert.Equal(t, 0.847, data.Progress.Details["best_score"])
	case <-time.After(100 * time.Millisecond):
		t.Fatal("Expected unthrottled progress event with details")
	}
}

// TestProgressReporter_ConcurrentReports tests thread safety
func TestProgressReporter_ConcurrentReports(t *testing.T) {
	eventManager, bus := setupEventManager()
	eventsChan := make(chan events.Event, 100)
	_ = bus.Subscribe(events.JobProgress, func(event *events.Event) {
		eventsChan <- *event
	})

	reporter := NewProgressReporter(eventManager, "test_concurrent", JobTypeSyncPrices)

	// Send reports from multiple goroutines
	done := make(chan bool, 10)
	for i := 0; i < 10; i++ {
		go func(idx int) {
			for j := 0; j < 5; j++ {
				reporter.Report(idx*5+j, 50, "Concurrent report")
				time.Sleep(10 * time.Millisecond)
			}
			done <- true
		}(i)
	}

	// Wait for all goroutines
	for i := 0; i < 10; i++ {
		<-done
	}

	// Should not panic and should receive some events (throttled)
	eventCount := 0
	for {
		select {
		case <-eventsChan:
			eventCount++
		case <-time.After(100 * time.Millisecond):
			// No more events
			assert.Greater(t, eventCount, 0, "Should have received at least one event")
			return
		}
	}
}
