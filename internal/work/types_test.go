package work

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestMarketTimingString(t *testing.T) {
	tests := []struct {
		timing   MarketTiming
		expected string
	}{
		{AnyTime, "AnyTime"},
		{AfterMarketClose, "AfterMarketClose"},
		{DuringMarketOpen, "DuringMarketOpen"},
		{AllMarketsClosed, "AllMarketsClosed"},
		{MarketTiming(99), "Unknown"},
	}

	for _, tt := range tests {
		t.Run(tt.expected, func(t *testing.T) {
			assert.Equal(t, tt.expected, tt.timing.String())
		})
	}
}

func TestPriorityString(t *testing.T) {
	tests := []struct {
		priority Priority
		expected string
	}{
		{PriorityLow, "Low"},
		{PriorityMedium, "Medium"},
		{PriorityHigh, "High"},
		{PriorityCritical, "Critical"},
		{Priority(99), "Unknown"},
	}

	for _, tt := range tests {
		t.Run(tt.expected, func(t *testing.T) {
			assert.Equal(t, tt.expected, tt.priority.String())
		})
	}
}

func TestNewWorkItem_GlobalWork(t *testing.T) {
	wt := &WorkType{
		ID:       "planner:weights",
		Priority: PriorityCritical,
	}

	item := NewWorkItem(wt, "")

	assert.Equal(t, "planner:weights", item.ID)
	assert.Equal(t, "planner:weights", item.TypeID)
	assert.Equal(t, "", item.Subject)
	assert.Equal(t, 0, item.Retries)
	assert.WithinDuration(t, time.Now(), item.CreatedAt, time.Second)
}

func TestNewWorkItem_PerSecurityWork(t *testing.T) {
	wt := &WorkType{
		ID:           "security:sync",
		MarketTiming: AfterMarketClose,
		Priority:     PriorityMedium,
	}

	item := NewWorkItem(wt, "NL0010273215")

	assert.Equal(t, "security:sync:NL0010273215", item.ID)
	assert.Equal(t, "security:sync", item.TypeID)
	assert.Equal(t, "NL0010273215", item.Subject)
	assert.Equal(t, 0, item.Retries)
}

func TestParseWorkID(t *testing.T) {
	tests := []struct {
		name        string
		id          string
		wantTypeID  string
		wantSubject string
	}{
		{
			name:        "global work - single part",
			id:          "backup",
			wantTypeID:  "backup",
			wantSubject: "",
		},
		{
			name:        "global work - two parts",
			id:          "planner:weights",
			wantTypeID:  "planner:weights",
			wantSubject: "",
		},
		{
			name:        "per-security work - three parts",
			id:          "security:sync:NL0010273215",
			wantTypeID:  "security:sync",
			wantSubject: "NL0010273215",
		},
		{
			name:        "per-security work - US ISIN",
			id:          "security:technical:US0378331005",
			wantTypeID:  "security:technical",
			wantSubject: "US0378331005",
		},
		{
			name:        "maintenance cleanup - three parts",
			id:          "maintenance:cleanup:history",
			wantTypeID:  "maintenance:cleanup",
			wantSubject: "history",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gotTypeID, gotSubject := ParseWorkID(tt.id)
			assert.Equal(t, tt.wantTypeID, gotTypeID)
			assert.Equal(t, tt.wantSubject, gotSubject)
		})
	}
}

func TestCompletionKey(t *testing.T) {
	t.Run("from work item - global", func(t *testing.T) {
		item := &WorkItem{
			ID:      "planner:weights",
			TypeID:  "planner:weights",
			Subject: "",
		}

		key := NewCompletionKey(item)

		assert.Equal(t, "planner:weights", key.TypeID)
		assert.Equal(t, "", key.Subject)
		assert.Equal(t, "planner:weights", key.String())
	})

	t.Run("from work item - per-security", func(t *testing.T) {
		item := &WorkItem{
			ID:      "security:sync:NL0010273215",
			TypeID:  "security:sync",
			Subject: "NL0010273215",
		}

		key := NewCompletionKey(item)

		assert.Equal(t, "security:sync", key.TypeID)
		assert.Equal(t, "NL0010273215", key.Subject)
		assert.Equal(t, "security:sync:NL0010273215", key.String())
	})
}

func TestWorkTypeExecution(t *testing.T) {
	executed := false
	executedSubject := ""

	wt := &WorkType{
		ID:       "test:work",
		Priority: PriorityMedium,
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			executed = true
			executedSubject = subject
			return nil
		},
	}

	assert.Equal(t, "test:work", wt.ID)
	assert.Equal(t, PriorityMedium, wt.Priority)
	err := wt.Execute(context.Background(), "test-subject", nil)

	require.NoError(t, err)
	assert.True(t, executed)
	assert.Equal(t, "test-subject", executedSubject)
}

func TestWorkTypeFindSubjects(t *testing.T) {
	t.Run("returns subjects needing work", func(t *testing.T) {
		wt := &WorkType{
			ID: "security:sync",
			FindSubjects: func() []string {
				return []string{"ISIN1", "ISIN2", "ISIN3"}
			},
		}

		assert.Equal(t, "security:sync", wt.ID)
		subjects := wt.FindSubjects()

		assert.Equal(t, []string{"ISIN1", "ISIN2", "ISIN3"}, subjects)
	})

	t.Run("returns nil when no work needed", func(t *testing.T) {
		wt := &WorkType{
			ID: "planner:weights",
			FindSubjects: func() []string {
				return nil
			},
		}

		assert.Equal(t, "planner:weights", wt.ID)
		subjects := wt.FindSubjects()

		assert.Nil(t, subjects)
	})

	t.Run("returns empty string slice for global work", func(t *testing.T) {
		wt := &WorkType{
			ID: "planner:weights",
			FindSubjects: func() []string {
				return []string{""}
			},
		}

		assert.Equal(t, "planner:weights", wt.ID)
		subjects := wt.FindSubjects()

		assert.Equal(t, []string{""}, subjects)
	})
}

func TestConstants(t *testing.T) {
	assert.Equal(t, 7*time.Minute, WorkTimeout)
	assert.Equal(t, 10, MaxRetries)
}
