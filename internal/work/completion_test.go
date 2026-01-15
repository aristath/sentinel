package work

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewCompletionTracker(t *testing.T) {
	tracker := NewCompletionTracker()

	require.NotNil(t, tracker)
}

func TestCompletionTracker_MarkCompleted(t *testing.T) {
	tracker := NewCompletionTracker()

	item := &WorkItem{
		ID:      "planner:weights",
		TypeID:  "planner:weights",
		Subject: "",
	}

	tracker.MarkCompleted(item)

	completed, exists := tracker.GetCompletion(item.TypeID, item.Subject)
	require.True(t, exists)
	assert.WithinDuration(t, time.Now(), completed, time.Second)
}

func TestCompletionTracker_MarkCompleted_PerSecurity(t *testing.T) {
	tracker := NewCompletionTracker()

	item1 := &WorkItem{
		ID:      "security:sync:NL0010273215",
		TypeID:  "security:sync",
		Subject: "NL0010273215",
	}
	item2 := &WorkItem{
		ID:      "security:sync:US0378331005",
		TypeID:  "security:sync",
		Subject: "US0378331005",
	}

	tracker.MarkCompleted(item1)

	// First item should be completed
	completed, exists := tracker.GetCompletion(item1.TypeID, item1.Subject)
	require.True(t, exists)
	assert.WithinDuration(t, time.Now(), completed, time.Second)

	// Second item should not exist
	assert.Equal(t, "security:sync:US0378331005", item2.ID)
	_, exists = tracker.GetCompletion(item2.TypeID, item2.Subject)
	assert.False(t, exists)
}

func TestCompletionTracker_IsStale(t *testing.T) {
	tracker := NewCompletionTracker()

	t.Run("returns true when never completed", func(t *testing.T) {
		stale := tracker.IsStale("planner:weights", "", time.Hour)
		assert.True(t, stale)
	})

	t.Run("returns false when recently completed", func(t *testing.T) {
		item := &WorkItem{
			ID:      "planner:weights",
			TypeID:  "planner:weights",
			Subject: "",
		}
		tracker.MarkCompleted(item)

		stale := tracker.IsStale("planner:weights", "", time.Hour)
		assert.False(t, stale)
	})

	t.Run("returns true when interval exceeded", func(t *testing.T) {
		// Use a tracker with manual time injection for testing
		tracker := NewCompletionTracker()
		item := &WorkItem{
			ID:      "maintenance:backup",
			TypeID:  "maintenance:backup",
			Subject: "",
		}

		// Mark completed with a past time
		tracker.MarkCompletedAt(item, time.Now().Add(-25*time.Hour))

		// Should be stale with 24h interval
		stale := tracker.IsStale("maintenance:backup", "", 24*time.Hour)
		assert.True(t, stale)
	})

	t.Run("returns false when within interval", func(t *testing.T) {
		tracker := NewCompletionTracker()
		item := &WorkItem{
			ID:      "maintenance:backup",
			TypeID:  "maintenance:backup",
			Subject: "",
		}

		// Mark completed with a recent time
		tracker.MarkCompletedAt(item, time.Now().Add(-12*time.Hour))

		// Should not be stale with 24h interval
		stale := tracker.IsStale("maintenance:backup", "", 24*time.Hour)
		assert.False(t, stale)
	})

	t.Run("zero interval always returns true", func(t *testing.T) {
		tracker := NewCompletionTracker()
		item := &WorkItem{
			ID:      "planner:weights",
			TypeID:  "planner:weights",
			Subject: "",
		}
		tracker.MarkCompleted(item)

		// Zero interval means on-demand only, always eligible
		stale := tracker.IsStale("planner:weights", "", 0)
		assert.True(t, stale)
	})
}

func TestCompletionTracker_Clear(t *testing.T) {
	tracker := NewCompletionTracker()

	item := &WorkItem{
		ID:      "planner:weights",
		TypeID:  "planner:weights",
		Subject: "",
	}
	tracker.MarkCompleted(item)

	// Verify it exists
	_, exists := tracker.GetCompletion(item.TypeID, item.Subject)
	require.True(t, exists)

	// Clear it
	tracker.Clear(item.TypeID, item.Subject)

	// Should no longer exist
	_, exists = tracker.GetCompletion(item.TypeID, item.Subject)
	assert.False(t, exists)
}

func TestCompletionTracker_ClearByPrefix(t *testing.T) {
	tracker := NewCompletionTracker()

	// Add various completions
	tracker.MarkCompleted(&WorkItem{TypeID: "planner:weights", Subject: ""})
	tracker.MarkCompleted(&WorkItem{TypeID: "planner:context", Subject: ""})
	tracker.MarkCompleted(&WorkItem{TypeID: "planner:plan", Subject: ""})
	tracker.MarkCompleted(&WorkItem{TypeID: "sync:portfolio", Subject: ""})

	// Clear all planner completions
	tracker.ClearByPrefix("planner:")

	// Planner completions should be gone
	_, exists := tracker.GetCompletion("planner:weights", "")
	assert.False(t, exists)
	_, exists = tracker.GetCompletion("planner:context", "")
	assert.False(t, exists)
	_, exists = tracker.GetCompletion("planner:plan", "")
	assert.False(t, exists)

	// Sync completion should remain
	_, exists = tracker.GetCompletion("sync:portfolio", "")
	assert.True(t, exists)
}

func TestCompletionTracker_ClearByTypeID(t *testing.T) {
	tracker := NewCompletionTracker()

	// Add per-security completions
	tracker.MarkCompleted(&WorkItem{TypeID: "security:sync", Subject: "NL0010273215"})
	tracker.MarkCompleted(&WorkItem{TypeID: "security:sync", Subject: "US0378331005"})
	tracker.MarkCompleted(&WorkItem{TypeID: "security:technical", Subject: "NL0010273215"})

	// Clear all security:sync completions
	tracker.ClearByTypeID("security:sync")

	// security:sync completions should be gone
	_, exists := tracker.GetCompletion("security:sync", "NL0010273215")
	assert.False(t, exists)
	_, exists = tracker.GetCompletion("security:sync", "US0378331005")
	assert.False(t, exists)

	// security:technical should remain
	_, exists = tracker.GetCompletion("security:technical", "NL0010273215")
	assert.True(t, exists)
}

func TestCompletionTracker_ConcurrentAccess(t *testing.T) {
	tracker := NewCompletionTracker()

	done := make(chan bool)

	// Concurrent writers
	for i := 0; i < 10; i++ {
		go func(id int) {
			for j := 0; j < 100; j++ {
				item := &WorkItem{
					TypeID:  "security:sync",
					Subject: string(rune('A' + id)),
				}
				tracker.MarkCompleted(item)
			}
			done <- true
		}(i)
	}

	// Concurrent readers
	for i := 0; i < 10; i++ {
		go func() {
			for j := 0; j < 100; j++ {
				tracker.IsStale("security:sync", "A", time.Hour)
				tracker.GetCompletion("security:sync", "A")
			}
			done <- true
		}()
	}

	// Wait for all goroutines
	for i := 0; i < 20; i++ {
		<-done
	}
}
