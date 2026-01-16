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
	completion := NewCompletionTracker()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	var executionOrder []string
	var mu sync.Mutex
	executed := make(map[string]bool)

	// Register planner work types with dependencies
	registry.Register(&WorkType{
		ID:       "planner:weights",
		Priority: PriorityCritical,
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
		Priority:  PriorityCritical,
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
		Priority:  PriorityCritical,
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
		Priority:  PriorityCritical,
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

	p := NewProcessor(registry, completion, market)

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
	completion := NewCompletionTracker()
	market := NewMarketTimingChecker(&MockMarketChecker{isOpen: true})

	var executionOrder []string
	var mu sync.Mutex
	executed := make(map[string]bool)

	// sync:portfolio - no dependencies
	registry.Register(&WorkType{
		ID:           "sync:portfolio",
		Priority:     PriorityHigh,
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
		Priority:     PriorityHigh,
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
		Priority:     PriorityMedium,
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
		Priority:     PriorityMedium,
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

	p := NewProcessor(registry, completion, market)

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
	completion := NewCompletionTracker()

	// Market is OPEN for this security
	mockMarket := &MockMarketChecker{
		isOpen:         true,
		isSecurityOpen: map[string]bool{"NL0010273215": true},
	}
	market := NewMarketTimingChecker(mockMarket)

	executed := atomic.Bool{}

	registry.Register(&WorkType{
		ID:           "security:sync",
		Priority:     PriorityMedium,
		MarketTiming: AfterMarketClose, // Only run when market closed
		FindSubjects: func() []string {
			return []string{"NL0010273215"}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			executed.Store(true)
			return nil
		},
	})

	p := NewProcessor(registry, completion, market)

	go p.Run()
	defer p.Stop()

	p.Trigger()
	time.Sleep(200 * time.Millisecond)

	// Should NOT have executed because market is open
	assert.False(t, executed.Load(), "security work should not run while market is open")

	// Now close the market
	mockMarket.isOpen = false
	mockMarket.isSecurityOpen["NL0010273215"] = false

	p.Trigger()
	time.Sleep(200 * time.Millisecond)

	// Should have executed now
	assert.True(t, executed.Load(), "security work should run after market closes")
}

func TestIntegration_MaintenanceOnlyDuringAllMarketsClosed(t *testing.T) {
	// Test that maintenance work only runs when ALL markets are closed.

	registry := NewRegistry()
	completion := NewCompletionTracker()

	// Some market is still open
	mockMarket := &MockMarketChecker{
		isOpen:           true,
		allMarketsClosed: false,
	}
	market := NewMarketTimingChecker(mockMarket)

	executed := atomic.Bool{}

	registry.Register(&WorkType{
		ID:           "maintenance:backup",
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed, // Only run when ALL markets closed
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			executed.Store(true)
			return nil
		},
	})

	p := NewProcessor(registry, completion, market)

	go p.Run()
	defer p.Stop()

	p.Trigger()
	time.Sleep(200 * time.Millisecond)

	// Should NOT have executed because not all markets are closed
	assert.False(t, executed.Load(), "maintenance should not run while any market is open")

	// Now close all markets
	mockMarket.isOpen = false
	mockMarket.allMarketsClosed = true

	p.Trigger()
	time.Sleep(200 * time.Millisecond)

	// Should have executed now
	assert.True(t, executed.Load(), "maintenance should run when all markets closed")
}

func TestIntegration_ManualTriggerBypassesTimingChecks(t *testing.T) {
	// Test that ExecuteNow bypasses market timing checks.

	registry := NewRegistry()
	completion := NewCompletionTracker()

	// Market is OPEN
	mockMarket := &MockMarketChecker{
		isOpen:           true,
		allMarketsClosed: false,
	}
	market := NewMarketTimingChecker(mockMarket)

	executed := atomic.Bool{}

	registry.Register(&WorkType{
		ID:           "maintenance:backup",
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed, // Normally only runs when all closed
		FindSubjects: func() []string {
			return nil // No automatic work
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			executed.Store(true)
			return nil
		},
	})

	p := NewProcessor(registry, completion, market)

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
	completion := NewCompletionTracker()
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
			Priority:  PriorityHigh,
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

	p := NewProcessor(registry, completion, market)

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
	completion := NewCompletionTracker()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	execCount := atomic.Int32{}

	registry.Register(&WorkType{
		ID:       "sync:rates",
		Priority: PriorityMedium,
		Interval: time.Hour, // Only run once per hour
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			execCount.Add(1)
			return nil
		},
	})

	p := NewProcessor(registry, completion, market)

	go p.Run()
	defer p.Stop()

	// First trigger should execute
	p.Trigger()
	time.Sleep(200 * time.Millisecond)
	assert.Equal(t, int32(1), execCount.Load(), "first trigger should execute")

	// Second trigger should NOT execute (not stale yet)
	p.Trigger()
	time.Sleep(200 * time.Millisecond)
	assert.Equal(t, int32(1), execCount.Load(), "second trigger should not execute (not stale)")

	// Clear completion to simulate staleness
	completion.Clear("sync:rates", "")

	// Third trigger should execute
	p.Trigger()
	time.Sleep(200 * time.Millisecond)
	assert.Equal(t, int32(2), execCount.Load(), "third trigger should execute after clear")
}

func TestIntegration_CompletionTrackerPersistsDuringSession(t *testing.T) {
	// Test that completion data persists across processor restarts within a session.

	registry := NewRegistry()
	completion := NewCompletionTracker()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	execCount := atomic.Int32{}

	registry.Register(&WorkType{
		ID:       "planner:weights",
		Priority: PriorityCritical,
		Interval: time.Hour,
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			execCount.Add(1)
			return nil
		},
	})

	// First processor run
	p1 := NewProcessor(registry, completion, market)
	go p1.Run()
	p1.Trigger()
	time.Sleep(200 * time.Millisecond)
	p1.Stop()

	assert.Equal(t, int32(1), execCount.Load())

	// Second processor run with same completion tracker
	p2 := NewProcessor(registry, completion, market)
	go p2.Run()
	p2.Trigger()
	time.Sleep(200 * time.Millisecond)
	p2.Stop()

	// Should still be 1 - completion data persisted
	assert.Equal(t, int32(1), execCount.Load(), "completion should persist across processor restarts")
}

func TestIntegration_PriorityOrdering(t *testing.T) {
	// Test that higher priority work runs before lower priority work.

	registry := NewRegistry()
	completion := NewCompletionTracker()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	var executionOrder []string
	var mu sync.Mutex
	executed := make(map[string]bool)

	// Register work types with different priorities
	for _, wt := range []struct {
		id       string
		priority Priority
	}{
		{"maintenance:backup", PriorityLow},
		{"security:sync", PriorityMedium},
		{"sync:portfolio", PriorityHigh},
		{"trading:execute", PriorityCritical},
	} {
		wtID := wt.id
		wtPriority := wt.priority
		registry.Register(&WorkType{
			ID:       wtID,
			Priority: wtPriority,
			FindSubjects: func() []string {
				mu.Lock()
				defer mu.Unlock()
				if executed[wtID] {
					return nil
				}
				return []string{""}
			},
			Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
				mu.Lock()
				executionOrder = append(executionOrder, wtID)
				executed[wtID] = true
				mu.Unlock()
				return nil
			},
		})
	}

	p := NewProcessor(registry, completion, market)

	go p.Run()
	defer p.Stop()

	p.Trigger()
	time.Sleep(800 * time.Millisecond)

	mu.Lock()
	defer mu.Unlock()

	require.Len(t, executionOrder, 4, "all 4 work types should execute")

	// Higher priority should execute first
	tradingIdx := indexOf(executionOrder, "trading:execute")
	syncIdx := indexOf(executionOrder, "sync:portfolio")
	securityIdx := indexOf(executionOrder, "security:sync")
	maintenanceIdx := indexOf(executionOrder, "maintenance:backup")

	assert.Less(t, tradingIdx, syncIdx, "critical should run before high")
	assert.Less(t, syncIdx, securityIdx, "high should run before medium")
	assert.Less(t, securityIdx, maintenanceIdx, "medium should run before low")
}

func TestIntegration_PerSecurityDependencySameSubject(t *testing.T) {
	// Test that per-security dependencies are scoped to the same ISIN.
	// security:technical for AAPL should wait for security:sync for AAPL,
	// not for security:sync for other ISINs.

	registry := NewRegistry()
	completion := NewCompletionTracker()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	var executionOrder []string
	var mu sync.Mutex
	executed := make(map[string]bool)

	// security:sync - syncs AAPL and GOOGL
	registry.Register(&WorkType{
		ID:           "security:sync",
		Priority:     PriorityMedium,
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
		Priority:     PriorityMedium,
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

	p := NewProcessor(registry, completion, market)

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
