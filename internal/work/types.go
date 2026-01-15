// Package work provides a unified work processor for background job execution.
// It replaces the dual job systems (time-based scheduler + idle processor) with
// a single, event-driven system using WordPress-style dependencies and market-aware timing.
package work

import (
	"context"
	"strings"
	"time"
)

// WorkTimeout is the maximum duration a work item can run before being cancelled.
const WorkTimeout = 7 * time.Minute

// MaxRetries is the maximum number of times a failed work item will be retried.
const MaxRetries = 10

// MarketTiming defines when work can be executed based on market state.
type MarketTiming int

const (
	// AnyTime means work can run regardless of market state.
	AnyTime MarketTiming = iota
	// AfterMarketClose means work runs only when the security's market is closed.
	AfterMarketClose
	// DuringMarketOpen means work runs only when the security's market is open.
	DuringMarketOpen
	// AllMarketsClosed means work runs only when all markets are closed (maintenance window).
	AllMarketsClosed
)

// String returns a human-readable name for the market timing.
func (mt MarketTiming) String() string {
	switch mt {
	case AnyTime:
		return "AnyTime"
	case AfterMarketClose:
		return "AfterMarketClose"
	case DuringMarketOpen:
		return "DuringMarketOpen"
	case AllMarketsClosed:
		return "AllMarketsClosed"
	default:
		return "Unknown"
	}
}

// Priority defines the execution priority of work types.
type Priority int

const (
	// PriorityLow is for non-urgent work (maintenance, deployment).
	PriorityLow Priority = iota
	// PriorityMedium is for regular background work (security calculations, analysis).
	PriorityMedium
	// PriorityHigh is for important work (sync, dividends).
	PriorityHigh
	// PriorityCritical is for urgent work (trading, planning).
	PriorityCritical
)

// String returns a human-readable name for the priority.
func (p Priority) String() string {
	switch p {
	case PriorityLow:
		return "Low"
	case PriorityMedium:
		return "Medium"
	case PriorityHigh:
		return "High"
	case PriorityCritical:
		return "Critical"
	default:
		return "Unknown"
	}
}

// WorkType defines a type of work that can be executed.
// Work types are registered once and can generate multiple work items.
type WorkType struct {
	// ID is the unique identifier for this work type (e.g., "security:sync", "planner:weights").
	ID string

	// DependsOn lists work type IDs that must complete before this work can run.
	// For per-security work, dependencies are scoped to the same subject (ISIN).
	DependsOn []string

	// MarketTiming defines when this work can be executed.
	MarketTiming MarketTiming

	// Interval is the minimum time between runs (0 = on-demand only).
	Interval time.Duration

	// Priority determines execution order when multiple work items are eligible.
	Priority Priority

	// FindSubjects returns subjects (ISINs) that need this work.
	// Returns []string{""} for global work, nil if no work needed.
	FindSubjects func() []string

	// Execute performs the work for a given subject.
	// Subject is empty string for global work, ISIN for per-security work.
	Execute func(ctx context.Context, subject string) error
}

// WorkItem represents a specific unit of work to be executed.
type WorkItem struct {
	// ID is the full work ID including subject (e.g., "security:sync:NL0010273215").
	ID string

	// TypeID is the work type ID (e.g., "security:sync").
	TypeID string

	// Subject is the ISIN for per-security work, empty for global work.
	Subject string

	// Retries is the number of times this item has been retried.
	Retries int

	// CreatedAt is when this work item was created.
	CreatedAt time.Time
}

// NewWorkItem creates a new work item from a work type and subject.
func NewWorkItem(workType *WorkType, subject string) *WorkItem {
	id := workType.ID
	if subject != "" {
		id = workType.ID + ":" + subject
	}

	return &WorkItem{
		ID:        id,
		TypeID:    workType.ID,
		Subject:   subject,
		CreatedAt: time.Now(),
	}
}

// ParseWorkID extracts the work type ID and subject from a full work ID.
// For example, "security:sync:NL0010273215" returns ("security:sync", "NL0010273215").
// For "planner:weights", returns ("planner:weights", "").
func ParseWorkID(id string) (typeID string, subject string) {
	// Find the last colon that could be the subject separator
	// Work type IDs have format "category:type", subjects are typically ISINs
	parts := strings.Split(id, ":")
	if len(parts) <= 2 {
		return id, ""
	}

	// Assume the last part is the subject if there are more than 2 parts
	return strings.Join(parts[:len(parts)-1], ":"), parts[len(parts)-1]
}

// CompletionKey uniquely identifies a completed work item.
type CompletionKey struct {
	TypeID  string
	Subject string
}

// NewCompletionKey creates a completion key from a work item.
func NewCompletionKey(item *WorkItem) CompletionKey {
	return CompletionKey{
		TypeID:  item.TypeID,
		Subject: item.Subject,
	}
}

// String returns a string representation of the completion key.
func (ck CompletionKey) String() string {
	if ck.Subject == "" {
		return ck.TypeID
	}
	return ck.TypeID + ":" + ck.Subject
}
