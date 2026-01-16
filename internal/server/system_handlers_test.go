package server

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/aristath/sentinel/internal/work"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestSystemHandlers_HandleJobsStatus(t *testing.T) {
	tests := []struct {
		name           string
		setupProcessor func() *work.Processor
		expectedCount  int
		validate       func(t *testing.T, response JobsStatusResponse)
	}{
		{
			name: "returns all work types from registry",
			setupProcessor: func() *work.Processor {
				registry := work.NewRegistry()
				completion := work.NewCompletionTracker()
				market := work.NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

				// Register multiple work types
				registry.Register(&work.WorkType{
					ID:           "sync:portfolio",
					Priority:     work.PriorityHigh,
					MarketTiming: work.AnyTime,
					Interval:     5 * time.Minute,
					DependsOn:    []string{},
					FindSubjects: func() []string {
						return []string{""}
					},
					Execute: func(ctx context.Context, subject string, progress *work.ProgressReporter) error {
						return nil
					},
				})

				registry.Register(&work.WorkType{
					ID:           "planner:weights",
					Priority:     work.PriorityCritical,
					MarketTiming: work.AnyTime,
					Interval:     0, // On-demand
					DependsOn:    []string{},
					FindSubjects: func() []string {
						return []string{""}
					},
					Execute: func(ctx context.Context, subject string, progress *work.ProgressReporter) error {
						return nil
					},
				})

				return work.NewProcessor(registry, completion, market)
			},
			expectedCount: 2,
			validate: func(t *testing.T, response JobsStatusResponse) {
				assert.Len(t, response.WorkTypes, 2)
				// Should be ordered by priority (Critical first)
				assert.Equal(t, "planner:weights", response.WorkTypes[0].ID)
				assert.Equal(t, "sync:portfolio", response.WorkTypes[1].ID)
			},
		},
		{
			name: "includes last run time from completion tracker",
			setupProcessor: func() *work.Processor {
				registry := work.NewRegistry()
				completion := work.NewCompletionTracker()
				market := work.NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

				registry.Register(&work.WorkType{
					ID:           "sync:portfolio",
					Priority:     work.PriorityHigh,
					MarketTiming: work.AnyTime,
					Interval:     5 * time.Minute,
					DependsOn:    []string{},
					FindSubjects: func() []string {
						return []string{""}
					},
					Execute: func(ctx context.Context, subject string, progress *work.ProgressReporter) error {
						return nil
					},
				})

				// Mark as completed
				item := &work.WorkItem{
					ID:      "sync:portfolio",
					TypeID:  "sync:portfolio",
					Subject: "",
				}
				completion.MarkCompletedAt(item, time.Date(2026, 1, 16, 10, 0, 0, 0, time.UTC))

				return work.NewProcessor(registry, completion, market)
			},
			expectedCount: 1,
			validate: func(t *testing.T, response JobsStatusResponse) {
				require.Len(t, response.WorkTypes, 1)
				wt := response.WorkTypes[0]
				assert.NotNil(t, wt.LastRun)
				assert.Equal(t, "2026-01-16T10:00:00Z", *wt.LastRun)
			},
		},
		{
			name: "calculates next run time correctly based on intervals",
			setupProcessor: func() *work.Processor {
				registry := work.NewRegistry()
				completion := work.NewCompletionTracker()
				market := work.NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

				registry.Register(&work.WorkType{
					ID:           "sync:portfolio",
					Priority:     work.PriorityHigh,
					MarketTiming: work.AnyTime,
					Interval:     5 * time.Minute,
					DependsOn:    []string{},
					FindSubjects: func() []string {
						return []string{""}
					},
					Execute: func(ctx context.Context, subject string, progress *work.ProgressReporter) error {
						return nil
					},
				})

				// Mark as completed 2 minutes ago
				item := &work.WorkItem{
					ID:      "sync:portfolio",
					TypeID:  "sync:portfolio",
					Subject: "",
				}
				completion.MarkCompletedAt(item, time.Now().Add(-2*time.Minute))

				return work.NewProcessor(registry, completion, market)
			},
			expectedCount: 1,
			validate: func(t *testing.T, response JobsStatusResponse) {
				require.Len(t, response.WorkTypes, 1)
				wt := response.WorkTypes[0]
				assert.NotNil(t, wt.NextRun)
				// Next run should be approximately 3 minutes from now (5 min interval - 2 min elapsed)
				nextRun, err := time.Parse(time.RFC3339, *wt.NextRun)
				require.NoError(t, err)
				expectedNextRun := time.Now().Add(3 * time.Minute)
				// Allow 5 second tolerance
				assert.InDelta(t, expectedNextRun.Unix(), nextRun.Unix(), 5)
			},
		},
		{
			name: "handles work types with no completion history",
			setupProcessor: func() *work.Processor {
				registry := work.NewRegistry()
				completion := work.NewCompletionTracker()
				market := work.NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

				registry.Register(&work.WorkType{
					ID:           "sync:portfolio",
					Priority:     work.PriorityHigh,
					MarketTiming: work.AnyTime,
					Interval:     5 * time.Minute,
					DependsOn:    []string{},
					FindSubjects: func() []string {
						return []string{""}
					},
					Execute: func(ctx context.Context, subject string, progress *work.ProgressReporter) error {
						return nil
					},
				})

				return work.NewProcessor(registry, completion, market)
			},
			expectedCount: 1,
			validate: func(t *testing.T, response JobsStatusResponse) {
				require.Len(t, response.WorkTypes, 1)
				wt := response.WorkTypes[0]
				assert.Nil(t, wt.LastRun)
				// Next run should be null for work with interval but no last run
				assert.Nil(t, wt.NextRun)
			},
		},
		{
			name: "handles zero-interval on-demand work types",
			setupProcessor: func() *work.Processor {
				registry := work.NewRegistry()
				completion := work.NewCompletionTracker()
				market := work.NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

				registry.Register(&work.WorkType{
					ID:           "planner:weights",
					Priority:     work.PriorityCritical,
					MarketTiming: work.AnyTime,
					Interval:     0, // On-demand
					DependsOn:    []string{},
					FindSubjects: func() []string {
						return []string{""}
					},
					Execute: func(ctx context.Context, subject string, progress *work.ProgressReporter) error {
						return nil
					},
				})

				// Mark as completed
				item := &work.WorkItem{
					ID:      "planner:weights",
					TypeID:  "planner:weights",
					Subject: "",
				}
				completion.MarkCompletedAt(item, time.Now().Add(-1*time.Hour))

				return work.NewProcessor(registry, completion, market)
			},
			expectedCount: 1,
			validate: func(t *testing.T, response JobsStatusResponse) {
				require.Len(t, response.WorkTypes, 1)
				wt := response.WorkTypes[0]
				assert.Equal(t, "0", wt.Interval)
				assert.NotNil(t, wt.LastRun)
				// Next run should be null for on-demand work
				assert.Nil(t, wt.NextRun)
			},
		},
		{
			name: "works with empty registry",
			setupProcessor: func() *work.Processor {
				registry := work.NewRegistry()
				completion := work.NewCompletionTracker()
				market := work.NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})
				return work.NewProcessor(registry, completion, market)
			},
			expectedCount: 0,
			validate: func(t *testing.T, response JobsStatusResponse) {
				assert.Len(t, response.WorkTypes, 0)
			},
		},
		{
			name: "includes all work type metadata",
			setupProcessor: func() *work.Processor {
				registry := work.NewRegistry()
				completion := work.NewCompletionTracker()
				market := work.NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

				registry.Register(&work.WorkType{
					ID:           "planner:context",
					Priority:     work.PriorityCritical,
					MarketTiming: work.DuringMarketOpen,
					Interval:     10 * time.Minute,
					DependsOn:    []string{"planner:weights"},
					FindSubjects: func() []string {
						return []string{""}
					},
					Execute: func(ctx context.Context, subject string, progress *work.ProgressReporter) error {
						return nil
					},
				})

				return work.NewProcessor(registry, completion, market)
			},
			expectedCount: 1,
			validate: func(t *testing.T, response JobsStatusResponse) {
				require.Len(t, response.WorkTypes, 1)
				wt := response.WorkTypes[0]
				assert.Equal(t, "planner:context", wt.ID)
				assert.Equal(t, "Critical", wt.Priority)
				assert.Equal(t, "DuringMarketOpen", wt.MarketTiming)
				assert.Equal(t, "10m", wt.Interval)
				assert.Equal(t, []string{"planner:weights"}, wt.DependsOn)
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			processor := tt.setupProcessor()

			// Create minimal SystemHandlers for testing
			log := zerolog.Nop()
			handlers := &SystemHandlers{
				log:           log,
				workProcessor: processor,
			}

			req := httptest.NewRequest(http.MethodGet, "/api/system/jobs", nil)
			rec := httptest.NewRecorder()

			handlers.HandleJobsStatus(rec, req)

			assert.Equal(t, http.StatusOK, rec.Code)
			assert.Equal(t, "application/json", rec.Header().Get("Content-Type"))

			var response JobsStatusResponse
			err := json.Unmarshal(rec.Body.Bytes(), &response)
			require.NoError(t, err)

			assert.Len(t, response.WorkTypes, tt.expectedCount)
			tt.validate(t, response)
		})
	}
}

// MockMarketChecker is a simple mock for market timing checks
type MockMarketChecker struct {
	isOpen           bool
	allMarketsClosed bool
	isSecurityOpen   map[string]bool
}

func (m *MockMarketChecker) IsAnyMarketOpen() bool {
	return m.isOpen
}

func (m *MockMarketChecker) IsSecurityMarketOpen(isin string) bool {
	if m.isSecurityOpen != nil {
		if open, ok := m.isSecurityOpen[isin]; ok {
			return open
		}
	}
	return m.isOpen
}

func (m *MockMarketChecker) AreAllMarketsClosed() bool {
	return m.allMarketsClosed
}
