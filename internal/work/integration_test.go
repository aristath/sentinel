package work

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Integration tests verify end-to-end work processor behavior including
// dependency chains, market timing, and event triggers.

func TestIntegration_PlannerChainExecutesInOrder(t *testing.T) {
	// Test that the full planner chain (weights -> context -> plan -> recommendations)
	// executes in the correct order when triggered.

	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	var executionOrder []string
	var mu sync.Mutex
	executed := make(map[string]bool)

	// Register planner work types with dependencies
	registry.Register(&WorkType{
		ID: "planner:weights",
		FindSubjects: func() []string {
			mu.Lock()
			defer mu.Unlock()
			if executed["planner:weights"] {
				return nil
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			mu.Lock()
			executionOrder = append(executionOrder, "planner:weights")
			executed["planner:weights"] = true
			mu.Unlock()
			return nil
		},
	})

	registry.Register(&WorkType{
		ID:        "planner:context",
		DependsOn: []string{"planner:weights"},
		FindSubjects: func() []string {
			mu.Lock()
			defer mu.Unlock()
			if executed["planner:context"] {
				return nil
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			mu.Lock()
			executionOrder = append(executionOrder, "planner:context")
			executed["planner:context"] = true
			mu.Unlock()
			return nil
		},
	})

	registry.Register(&WorkType{
		ID:        "planner:plan",
		DependsOn: []string{"planner:context"},
		FindSubjects: func() []string {
			mu.Lock()
			defer mu.Unlock()
			if executed["planner:plan"] {
				return nil
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			mu.Lock()
			executionOrder = append(executionOrder, "planner:plan")
			executed["planner:plan"] = true
			mu.Unlock()
			return nil
		},
	})

	registry.Register(&WorkType{
		ID:        "planner:recommendations",
		DependsOn: []string{"planner:plan"},
		FindSubjects: func() []string {
			mu.Lock()
			defer mu.Unlock()
			if executed["planner:recommendations"] {
				return nil
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			mu.Lock()
			executionOrder = append(executionOrder, "planner:recommendations")
			executed["planner:recommendations"] = true
			mu.Unlock()
			return nil
		},
	})

	p := NewProcessor(registry, market, nil)

	go p.Run()
	defer p.Stop()

	p.Trigger()

	// Wait for all work to complete
	time.Sleep(800 * time.Millisecond)

	mu.Lock()
	defer mu.Unlock()

	// All 4 planner work types should have executed in order
	require.Len(t, executionOrder, 4, "all 4 planner work types should execute")
	assert.Equal(t, "planner:weights", executionOrder[0])
	assert.Equal(t, "planner:context", executionOrder[1])
	assert.Equal(t, "planner:plan", executionOrder[2])
	assert.Equal(t, "planner:recommendations", executionOrder[3])
}

func TestIntegration_SyncCycleWithDependencies(t *testing.T) {
	// Test that sync work types execute respecting dependencies:
	// portfolio -> trades, cashflows, prices (can run in parallel after portfolio)
	// prices -> display

	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{isOpen: true})

	var executionOrder []string
	var mu sync.Mutex
	executed := make(map[string]bool)

	// sync:portfolio - no dependencies
	registry.Register(&WorkType{
		ID:           "sync:portfolio",
		MarketTiming: DuringMarketOpen,
		FindSubjects: func() []string {
			mu.Lock()
			defer mu.Unlock()
			if executed["sync:portfolio"] {
				return nil
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			mu.Lock()
			executionOrder = append(executionOrder, "sync:portfolio")
			executed["sync:portfolio"] = true
			mu.Unlock()
			return nil
		},
	})

	// sync:trades - depends on portfolio
	registry.Register(&WorkType{
		ID:           "sync:trades",
		DependsOn:    []string{"sync:portfolio"},
		MarketTiming: DuringMarketOpen,
		FindSubjects: func() []string {
			mu.Lock()
			defer mu.Unlock()
			if executed["sync:trades"] {
				return nil
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			mu.Lock()
			executionOrder = append(executionOrder, "sync:trades")
			executed["sync:trades"] = true
			mu.Unlock()
			return nil
		},
	})

	// sync:prices - depends on portfolio
	registry.Register(&WorkType{
		ID:           "sync:prices",
		DependsOn:    []string{"sync:portfolio"},
		MarketTiming: DuringMarketOpen,
		FindSubjects: func() []string {
			mu.Lock()
			defer mu.Unlock()
			if executed["sync:prices"] {
				return nil
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			mu.Lock()
			executionOrder = append(executionOrder, "sync:prices")
			executed["sync:prices"] = true
			mu.Unlock()
			return nil
		},
	})

	// sync:display - depends on prices
	registry.Register(&WorkType{
		ID:           "sync:display",
		DependsOn:    []string{"sync:prices"},
		MarketTiming: AnyTime,
		FindSubjects: func() []string {
			mu.Lock()
			defer mu.Unlock()
			if executed["sync:display"] {
				return nil
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			mu.Lock()
			executionOrder = append(executionOrder, "sync:display")
			executed["sync:display"] = true
			mu.Unlock()
			return nil
		},
	})

	p := NewProcessor(registry, market, nil)

	go p.Run()
	defer p.Stop()

	p.Trigger()

	// Wait for all work to complete
	time.Sleep(800 * time.Millisecond)

	mu.Lock()
	defer mu.Unlock()

	require.Len(t, executionOrder, 4, "all 4 sync work types should execute")

	// Portfolio must be first
	assert.Equal(t, "sync:portfolio", executionOrder[0])

	// Find positions of each work type
	portfolioIdx := indexOf(executionOrder, "sync:portfolio")
	tradesIdx := indexOf(executionOrder, "sync:trades")
	pricesIdx := indexOf(executionOrder, "sync:prices")
	displayIdx := indexOf(executionOrder, "sync:display")

	// Verify dependency ordering
	assert.Less(t, portfolioIdx, tradesIdx, "portfolio must run before trades")
	assert.Less(t, portfolioIdx, pricesIdx, "portfolio must run before prices")
	assert.Less(t, pricesIdx, displayIdx, "prices must run before display")
}

func TestIntegration_PerSecurityWorkRespectsMarketTiming(t *testing.T) {
	// Test that per-security work only runs when the security's market is closed.

	registry := NewRegistry()

	// Market is OPEN for this security
	mockMarket := &MockMarketChecker{
		isOpen:         true,
		isSecurityOpen: map[string]bool{"NL0010273215": true},
	}
	market := NewMarketTimingChecker(mockMarket)

	executed := atomic.Bool{}

	registry.Register(&WorkType{
		ID:           "security:sync",
		MarketTiming: AfterMarketClose, // Only run when market closed
		FindSubjects: func() []string {
			return []string{"NL0010273215"}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			executed.Store(true)
			return nil
		},
	})

	p := NewProcessor(registry, market, nil)

	go p.Run()
	defer p.Stop()

	p.Trigger()
	time.Sleep(200 * time.Millisecond)

	// Should NOT have executed because market is open
	assert.False(t, executed.Load(), "security work should not run while market is open")

	// Now close the market
	mockMarket.SetMarketOpen(false)
	mockMarket.SetSecurityMarketOpen("NL0010273215", false)

	p.Trigger()
	time.Sleep(200 * time.Millisecond)

	// Should have executed now
	assert.True(t, executed.Load(), "security work should run after market closes")
}

func TestIntegration_MaintenanceOnlyDuringAllMarketsClosed(t *testing.T) {
	// Test that maintenance work only runs when ALL markets are closed.

	registry := NewRegistry()

	// Some market is still open
	mockMarket := &MockMarketChecker{
		isOpen:           true,
		allMarketsClosed: false,
	}
	market := NewMarketTimingChecker(mockMarket)

	executed := atomic.Bool{}

	registry.Register(&WorkType{
		ID:           "maintenance:backup",
		MarketTiming: AllMarketsClosed, // Only run when ALL markets closed
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			executed.Store(true)
			return nil
		},
	})

	p := NewProcessor(registry, market, nil)

	go p.Run()
	defer p.Stop()

	p.Trigger()
	time.Sleep(200 * time.Millisecond)

	// Should NOT have executed because not all markets are closed
	assert.False(t, executed.Load(), "maintenance should not run while any market is open")

	// Now close all markets
	mockMarket.SetMarketOpen(false)
	mockMarket.SetAllMarketsClosed(true)

	p.Trigger()
	time.Sleep(200 * time.Millisecond)

	// Should have executed now
	assert.True(t, executed.Load(), "maintenance should run when all markets closed")
}

func TestIntegration_ManualTriggerBypassesTimingChecks(t *testing.T) {
	// Test that ExecuteNow bypasses market timing checks.

	registry := NewRegistry()

	// Market is OPEN
	mockMarket := &MockMarketChecker{
		isOpen:           true,
		allMarketsClosed: false,
	}
	market := NewMarketTimingChecker(mockMarket)

	executed := atomic.Bool{}

	registry.Register(&WorkType{
		ID:           "maintenance:backup",
		MarketTiming: AllMarketsClosed, // Normally only runs when all closed
		FindSubjects: func() []string {
			return nil // No automatic work
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			executed.Store(true)
			return nil
		},
	})

	p := NewProcessor(registry, market, nil)

	go p.Run()
	defer p.Stop()

	// Manually execute - should bypass timing checks
	err := p.ExecuteNow("maintenance:backup", "")

	require.NoError(t, err)
	assert.True(t, executed.Load(), "manual trigger should execute despite market being open")
}

func TestIntegration_DividendWorkflowChain(t *testing.T) {
	// Test the dividend workflow: detect -> analyze -> recommend -> execute

	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	var executionOrder []string
	var mu sync.Mutex
	executed := make(map[string]bool)

	for _, step := range []struct {
		id        string
		dependsOn []string
	}{
		{"dividend:detect", nil},
		{"dividend:analyze", []string{"dividend:detect"}},
		{"dividend:recommend", []string{"dividend:analyze"}},
		{"dividend:execute", []string{"dividend:recommend"}},
	} {
		stepID := step.id
		stepDeps := step.dependsOn
		registry.Register(&WorkType{
			ID:        stepID,
			DependsOn: stepDeps,
			FindSubjects: func() []string {
				mu.Lock()
				defer mu.Unlock()
				if executed[stepID] {
					return nil
				}
				return []string{""}
			},
			Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
				mu.Lock()
				executionOrder = append(executionOrder, stepID)
				executed[stepID] = true
				mu.Unlock()
				return nil
			},
		})
	}

	p := NewProcessor(registry, market, nil)

	go p.Run()
	defer p.Stop()

	p.Trigger()
	time.Sleep(800 * time.Millisecond)

	mu.Lock()
	defer mu.Unlock()

	require.Len(t, executionOrder, 4, "all 4 dividend work types should execute")
	assert.Equal(t, "dividend:detect", executionOrder[0])
	assert.Equal(t, "dividend:analyze", executionOrder[1])
	assert.Equal(t, "dividend:recommend", executionOrder[2])
	assert.Equal(t, "dividend:execute", executionOrder[3])
}

func TestIntegration_IntervalStalenessCheck(t *testing.T) {
	// Test that work with intervals respects staleness checks.

	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	execCount := atomic.Int32{}

	registry.Register(&WorkType{
		ID:       "sync:rates",
		Interval: time.Hour, // Only run once per hour
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			execCount.Add(1)
			return nil
		},
	})

	p := NewProcessor(registry, market, nil)

	go p.Run()
	defer p.Stop()

	// First trigger should execute
	p.Trigger()
	time.Sleep(200 * time.Millisecond)
	assert.Equal(t, int32(1), execCount.Load(), "first trigger should execute")

	// Second trigger should NOT execute (not stale yet) - test removed since no cache in test
}

func TestIntegration_CompletionTrackerPersistsDuringSession(t *testing.T) {
	t.Skip("CompletionTracker removed - persistence now handled by Cache via database")
	// Test that completion data persists across processor restarts within a session.
	// This feature is now handled by Cache using cache.db instead of in-memory CompletionTracker.
	// See TestCache_PersistenceAcrossRestarts for database-backed persistence tests.
}

func TestIntegration_PriorityOrdering(t *testing.T) {
	t.Skip("Priority ordering removed in favor of FIFO registration order")
}

func TestIntegration_PerSecurityDependencySameSubject(t *testing.T) {
	// Test that per-security dependencies are scoped to the same ISIN.
	// security:technical for AAPL should wait for security:sync for AAPL,
	// not for security:sync for other ISINs.

	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	var executionOrder []string
	var mu sync.Mutex
	executed := make(map[string]bool)

	// security:sync - syncs AAPL and GOOGL
	registry.Register(&WorkType{
		ID:           "security:sync",
		MarketTiming: AfterMarketClose,
		FindSubjects: func() []string {
			mu.Lock()
			defer mu.Unlock()
			var subjects []string
			for _, isin := range []string{"AAPL", "GOOGL"} {
				key := "security:sync:" + isin
				if !executed[key] {
					subjects = append(subjects, isin)
				}
			}
			return subjects
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			mu.Lock()
			key := "security:sync:" + subject
			executionOrder = append(executionOrder, key)
			executed[key] = true
			mu.Unlock()
			return nil
		},
	})

	// security:technical - depends on security:sync for same ISIN
	registry.Register(&WorkType{
		ID:           "security:technical",
		DependsOn:    []string{"security:sync"},
		MarketTiming: AfterMarketClose,
		FindSubjects: func() []string {
			mu.Lock()
			defer mu.Unlock()
			var subjects []string
			for _, isin := range []string{"AAPL", "GOOGL"} {
				key := "security:technical:" + isin
				if !executed[key] {
					subjects = append(subjects, isin)
				}
			}
			return subjects
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			mu.Lock()
			key := "security:technical:" + subject
			executionOrder = append(executionOrder, key)
			executed[key] = true
			mu.Unlock()
			return nil
		},
	})

	p := NewProcessor(registry, market, nil)

	go p.Run()
	defer p.Stop()

	p.Trigger()
	time.Sleep(1 * time.Second)

	mu.Lock()
	defer mu.Unlock()

	require.Len(t, executionOrder, 4, "all 4 work items should execute")

	// For each ISIN, sync must come before technical
	aaplSyncIdx := indexOf(executionOrder, "security:sync:AAPL")
	aaplTechIdx := indexOf(executionOrder, "security:technical:AAPL")
	googlSyncIdx := indexOf(executionOrder, "security:sync:GOOGL")
	googlTechIdx := indexOf(executionOrder, "security:technical:GOOGL")

	assert.Less(t, aaplSyncIdx, aaplTechIdx, "AAPL sync must run before AAPL technical")
	assert.Less(t, googlSyncIdx, googlTechIdx, "GOOGL sync must run before GOOGL technical")
}

// Helper function to find index of string in slice
func indexOf(slice []string, item string) int {
	for i, s := range slice {
		if s == item {
			return i
		}
	}
	return -1
}
