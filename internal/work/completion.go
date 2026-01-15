package work

import (
	"strings"
	"sync"
	"time"
)

// CompletionTracker tracks when work items were last completed.
// It's used to determine staleness based on intervals.
type CompletionTracker struct {
	completions map[string]time.Time // key: "typeID:subject"
	mu          sync.RWMutex
}

// NewCompletionTracker creates a new completion tracker.
func NewCompletionTracker() *CompletionTracker {
	return &CompletionTracker{
		completions: make(map[string]time.Time),
	}
}

// makeKey creates a unique key for a work type and subject combination.
func makeKey(typeID, subject string) string {
	if subject == "" {
		return typeID
	}
	return typeID + ":" + subject
}

// MarkCompleted records that a work item has been completed.
func (t *CompletionTracker) MarkCompleted(item *WorkItem) {
	t.MarkCompletedAt(item, time.Now())
}

// MarkCompletedAt records that a work item was completed at a specific time.
// This is primarily used for testing.
func (t *CompletionTracker) MarkCompletedAt(item *WorkItem, completedAt time.Time) {
	t.mu.Lock()
	defer t.mu.Unlock()

	key := makeKey(item.TypeID, item.Subject)
	t.completions[key] = completedAt
}

// GetCompletion returns when a work type/subject combination was last completed.
// Returns the completion time and whether the completion exists.
func (t *CompletionTracker) GetCompletion(typeID, subject string) (time.Time, bool) {
	t.mu.RLock()
	defer t.mu.RUnlock()

	key := makeKey(typeID, subject)
	completedAt, exists := t.completions[key]
	return completedAt, exists
}

// IsStale returns true if the work should be re-executed based on the interval.
// Returns true if:
// - Work has never been completed
// - Interval is zero (on-demand work, always eligible)
// - Time since last completion exceeds the interval
func (t *CompletionTracker) IsStale(typeID, subject string, interval time.Duration) bool {
	// Zero interval means on-demand only - always eligible when triggered
	if interval == 0 {
		return true
	}

	t.mu.RLock()
	defer t.mu.RUnlock()

	key := makeKey(typeID, subject)
	completedAt, exists := t.completions[key]
	if !exists {
		return true
	}

	return time.Since(completedAt) > interval
}

// Clear removes the completion record for a specific work type/subject.
func (t *CompletionTracker) Clear(typeID, subject string) {
	t.mu.Lock()
	defer t.mu.Unlock()

	key := makeKey(typeID, subject)
	delete(t.completions, key)
}

// ClearByPrefix removes all completion records matching a prefix.
// For example, ClearByPrefix("planner:") clears all planner completions.
func (t *CompletionTracker) ClearByPrefix(prefix string) {
	t.mu.Lock()
	defer t.mu.Unlock()

	for key := range t.completions {
		if strings.HasPrefix(key, prefix) {
			delete(t.completions, key)
		}
	}
}

// ClearByTypeID removes all completion records for a specific work type ID.
// This clears completions for all subjects of that type.
func (t *CompletionTracker) ClearByTypeID(typeID string) {
	t.mu.Lock()
	defer t.mu.Unlock()

	// Match exact typeID or typeID: prefix
	for key := range t.completions {
		if key == typeID || strings.HasPrefix(key, typeID+":") {
			delete(t.completions, key)
		}
	}
}
