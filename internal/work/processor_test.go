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

func TestNewProcessor(t *testing.T) {
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{})

	p := NewProcessor(registry, market, nil)

	require.NotNil(t, p)
}

func TestProcessor_Trigger(t *testing.T) {
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	executed := atomic.Bool{}
	registry.Register(&WorkType{
		ID: "test:work",
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			executed.Store(true)
			return nil
		},
	})

	p := NewProcessor(registry, market, nil)

	// Start processor
	go p.Run()
	defer p.Stop()

	// Trigger work
	p.Trigger()

	// Wait for execution
	time.Sleep(100 * time.Millisecond)

	assert.True(t, executed.Load())
}

func TestProcessor_DependencyOrdering(t *testing.T) {
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	var executionOrder []string
	var mu sync.Mutex
	executed := make(map[string]bool)

	// Register work with dependencies
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

	p := NewProcessor(registry, market, nil)

	go p.Run()
	defer p.Stop()

	p.Trigger()

	// Wait for all work to complete
	time.Sleep(500 * time.Millisecond)

	mu.Lock()
	defer mu.Unlock()

	// Dependencies should be respected
	require.Len(t, executionOrder, 3)
	assert.Equal(t, "planner:weights", executionOrder[0])
	assert.Equal(t, "planner:context", executionOrder[1])
	assert.Equal(t, "planner:plan", executionOrder[2])
}

func TestProcessor_PerSecurityDependencies(t *testing.T) {
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	var executionOrder []string
	var mu sync.Mutex
	executed := make(map[string]bool)

	registry.Register(&WorkType{
		ID:           "security:sync",
		MarketTiming: AfterMarketClose,
		FindSubjects: func() []string {
			mu.Lock()
			defer mu.Unlock()
			if executed["security:sync:NL0010273215"] {
				return nil
			}
			return []string{"NL0010273215"}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			mu.Lock()
			executionOrder = append(executionOrder, "security:sync:"+subject)
			executed["security:sync:"+subject] = true
			mu.Unlock()
			return nil
		},
	})

	registry.Register(&WorkType{
		ID:           "security:technical",
		DependsOn:    []string{"security:sync"},
		MarketTiming: AfterMarketClose,
		FindSubjects: func() []string {
			mu.Lock()
			defer mu.Unlock()
			if executed["security:technical:NL0010273215"] {
				return nil
			}
			return []string{"NL0010273215"}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			mu.Lock()
			executionOrder = append(executionOrder, "security:technical:"+subject)
			executed["security:technical:"+subject] = true
			mu.Unlock()
			return nil
		},
	})

	p := NewProcessor(registry, market, nil)

	go p.Run()
	defer p.Stop()

	p.Trigger()

	time.Sleep(500 * time.Millisecond)

	mu.Lock()
	defer mu.Unlock()

	// Same-subject dependency should be respected
	require.Len(t, executionOrder, 2)
	assert.Equal(t, "security:sync:NL0010273215", executionOrder[0])
	assert.Equal(t, "security:technical:NL0010273215", executionOrder[1])
}

func TestProcessor_MarketTimingRespected(t *testing.T) {
	registry := NewRegistry()

	// Market is open
	mockMarket := &MockMarketChecker{
		isOpen:           true,
		allMarketsClosed: false,
		isSecurityOpen:   map[string]bool{"NL0010273215": true},
	}
	market := NewMarketTimingChecker(mockMarket)

	executed := atomic.Bool{}
	registry.Register(&WorkType{
		ID:           "security:sync",
		MarketTiming: AfterMarketClose, // Won't run while market open
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

	time.Sleep(100 * time.Millisecond)

	// Should not have executed because market is open
	assert.False(t, executed.Load())
}

func TestProcessor_RetryOnFailure(t *testing.T) {
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	attempts := atomic.Int32{}
	registry.Register(&WorkType{
		ID: "test:failing",
		FindSubjects: func() []string {
			if attempts.Load() < 2 {
				return []string{""}
			}
			return nil // No more work after success
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			count := attempts.Add(1)
			if count < 2 {
				return assert.AnError // Fail first time
			}
			return nil // Succeed second time
		},
	})

	p := NewProcessor(registry, market, nil)

	go p.Run()
	defer p.Stop()

	p.Trigger()

	time.Sleep(500 * time.Millisecond)

	// Should have attempted twice (first failure, then retry success)
	assert.GreaterOrEqual(t, attempts.Load(), int32(2))
}

func TestProcessor_MaxRetries(t *testing.T) {
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	attempts := atomic.Int32{}
	firstRun := atomic.Bool{}
	firstRun.Store(true)

	registry.Register(&WorkType{
		ID: "test:always-fails",
		FindSubjects: func() []string {
			// Only return work on first discovery, then let retry queue handle it
			if firstRun.CompareAndSwap(true, false) {
				return []string{""}
			}
			return nil
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			attempts.Add(1)
			return assert.AnError // Always fail
		},
	})

	p := NewProcessor(registry, market, nil)

	go p.Run()
	defer p.Stop()

	p.Trigger()

	// Wait for retries to complete
	time.Sleep(500 * time.Millisecond)

	// Should stop after MaxRetries (first attempt + 10 retries = 11)
	assert.LessOrEqual(t, attempts.Load(), int32(MaxRetries+1))
}

func TestProcessor_Timeout(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping timeout test in short mode")
	}

	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	started := atomic.Bool{}
	cancelled := atomic.Bool{}

	registry.Register(&WorkType{
		ID: "test:slow",
		FindSubjects: func() []string {
			if !started.Load() {
				return []string{""}
			}
			return nil
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			started.Store(true)
			<-ctx.Done() // Wait for cancellation
			cancelled.Store(true)
			return ctx.Err()
		},
	})

	// Create processor with short timeout for testing
	p := NewProcessorWithTimeout(registry, market, nil, 100*time.Millisecond)

	go p.Run()
	defer p.Stop()

	p.Trigger()

	time.Sleep(300 * time.Millisecond)

	assert.True(t, started.Load())
	assert.True(t, cancelled.Load())
}

func TestProcessor_ExecuteNow(t *testing.T) {
	registry := NewRegistry()

	// Market is closed, but ExecuteNow should bypass timing
	mockMarket := &MockMarketChecker{
		isOpen:           true,
		allMarketsClosed: false,
	}
	market := NewMarketTimingChecker(mockMarket)

	executed := atomic.Bool{}
	executedSubject := ""
	var mu sync.Mutex

	registry.Register(&WorkType{
		ID:           "sync:portfolio",
		MarketTiming: DuringMarketOpen,
		FindSubjects: func() []string {
			return nil // No automatic work
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			executed.Store(true)
			mu.Lock()
			executedSubject = subject
			mu.Unlock()
			return nil
		},
	})

	p := NewProcessor(registry, market, nil)

	go p.Run()
	defer p.Stop()

	// Manually execute
	err := p.ExecuteNow("sync:portfolio", "")

	require.NoError(t, err)
	assert.True(t, executed.Load())

	mu.Lock()
	assert.Equal(t, "", executedSubject)
	mu.Unlock()
}

func TestProcessor_ExecuteNow_UnknownWorkType(t *testing.T) {
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{})

	p := NewProcessor(registry, market, nil)

	err := p.ExecuteNow("unknown:work", "")

	assert.Error(t, err)
}

func TestProcessor_ExecuteNow_WithSubject(t *testing.T) {
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	executedSubject := ""
	var mu sync.Mutex

	registry.Register(&WorkType{
		ID:           "security:sync",
		MarketTiming: AfterMarketClose,
		FindSubjects: func() []string {
			return nil
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			mu.Lock()
			executedSubject = subject
			mu.Unlock()
			return nil
		},
	})

	p := NewProcessor(registry, market, nil)

	go p.Run()
	defer p.Stop()

	err := p.ExecuteNow("security:sync", "NL0010273215")

	require.NoError(t, err)

	mu.Lock()
	assert.Equal(t, "NL0010273215", executedSubject)
	mu.Unlock()
}

func TestProcessor_Stop(t *testing.T) {
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{})

	p := NewProcessor(registry, market, nil)

	go p.Run()

	// Should not block
	done := make(chan bool)
	go func() {
		p.Stop()
		done <- true
	}()

	select {
	case <-done:
		// Success
	case <-time.After(time.Second):
		t.Fatal("Stop() blocked")
	}
}

func TestProcessor_NoDuplicateExecution(t *testing.T) {
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	execCount := atomic.Int32{}

	registry.Register(&WorkType{
		ID: "test:work",
		FindSubjects: func() []string {
			// Only return work on first call
			if execCount.Load() == 0 {
				return []string{""}
			}
			return nil
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			execCount.Add(1)
			time.Sleep(50 * time.Millisecond)
			return nil
		},
	})

	p := NewProcessor(registry, market, nil)

	go p.Run()
	defer p.Stop()

	// Trigger multiple times rapidly
	for i := 0; i < 10; i++ {
		p.Trigger()
	}

	time.Sleep(300 * time.Millisecond)

	// Should only execute once
	assert.Equal(t, int32(1), execCount.Load())
}

func TestProcessor_SystemBusyCheck(t *testing.T) {
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})

	execCount := atomic.Int32{}

	registry.Register(&WorkType{
		ID: "test:work",
		FindSubjects: func() []string {
			return []string{"a", "b", "c"} // Multiple subjects
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			execCount.Add(1)
			time.Sleep(50 * time.Millisecond)
			return nil
		},
	})

	p := NewProcessor(registry, market, nil)

	go p.Run()
	defer p.Stop()

	p.Trigger()

	// Wait for some executions
	time.Sleep(100 * time.Millisecond)

	// Only one should be running at a time (single worker model)
	// After 100ms with 50ms per execution, we expect at most 2 completed
	assert.LessOrEqual(t, execCount.Load(), int32(3))
}

func TestProcessor_GetRegistry(t *testing.T) {
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{})

	p := NewProcessor(registry, market, nil)

	// Should return the same registry instance
	assert.Equal(t, registry, p.GetRegistry())

	// Should allow access to registered work types
	registry.Register(&WorkType{
		ID: "test:work",
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			return nil
		},
	})

	wt := p.GetRegistry().Get("test:work")
	require.NotNil(t, wt)
	assert.Equal(t, "test:work", wt.ID)
}

// Phase 4 Tests: Queue Data Structures

func TestMakeQueueKey_WithSubject(t *testing.T) {
	key := makeQueueKey("security:sync", "US0378331005")
	assert.Equal(t, "security:sync:US0378331005", key)
}

func TestMakeQueueKey_WithoutSubject(t *testing.T) {
	key := makeQueueKey("planner:weights", "")
	assert.Equal(t, "planner:weights", key)
}

// Phase 6 Tests: populateQueue()

func TestProcessor_PopulateQueue_FIFO(t *testing.T) {
	// Test that work is added in registration order
	registry := NewRegistry()
	registry.Register(&WorkType{ID: "first", FindSubjects: func() []string { return []string{""} }})
	registry.Register(&WorkType{ID: "second", FindSubjects: func() []string { return []string{""} }})
	registry.Register(&WorkType{ID: "third", FindSubjects: func() []string { return []string{""} }})

	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})
	processor := NewProcessor(registry, market, nil)
	processor.populateQueue()

	assert.Equal(t, 3, len(processor.workQueue))
	assert.Equal(t, "first", processor.workQueue[0].TypeID)
	assert.Equal(t, "second", processor.workQueue[1].TypeID)
	assert.Equal(t, "third", processor.workQueue[2].TypeID)
}

func TestProcessor_PopulateQueue_NoDuplicates(t *testing.T) {
	// Test that calling populateQueue() twice doesn't duplicate items
	registry := NewRegistry()
	registry.Register(&WorkType{ID: "test", FindSubjects: func() []string { return []string{""} }})

	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})
	processor := NewProcessor(registry, market, nil)
	processor.populateQueue()
	processor.populateQueue()

	assert.Equal(t, 1, len(processor.workQueue))
}

func TestProcessor_PopulateQueue_RespectsMarketTiming(t *testing.T) {
	// Test that work blocked by market timing is not queued
	registry := NewRegistry()
	registry.Register(&WorkType{
		ID:           "blocked",
		MarketTiming: DuringMarketOpen,
		FindSubjects: func() []string { return []string{""} },
	})

	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true}) // Markets closed
	processor := NewProcessor(registry, market, nil)
	processor.populateQueue()

	assert.Equal(t, 0, len(processor.workQueue))
}

func TestProcessor_PopulateQueue_RespectsIntervals(t *testing.T) {
	t.Skip("Requires cache to track intervals - use integration tests for end-to-end testing")
}

func TestProcessor_PopulateQueue_SkipsDependencies(t *testing.T) {
	// Test that dependencies are NOT checked during population
	registry := NewRegistry()
	registry.Register(&WorkType{
		ID:           "dependent",
		DependsOn:    []string{"missing-dep"},
		FindSubjects: func() []string { return []string{""} },
	})

	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})
	processor := NewProcessor(registry, market, nil)
	processor.populateQueue()

	// Should still be queued - dependencies checked at execution time!
	assert.Equal(t, 1, len(processor.workQueue))
}

// Phase 8 Tests: Dependency Resolution

func TestProcessor_ResolveDependencies_Satisfied(t *testing.T) {
	t.Skip("Requires cache to track completed dependencies - use integration tests for end-to-end testing")
	// Test fast path - all dependencies already completed
	// This test needs a real cache to mark dependencies as completed
}

func TestProcessor_ResolveDependencies_AddsMissing(t *testing.T) {
	t.Skip("Requires cache to track dependencies - use integration tests for end-to-end testing")
}

func TestProcessor_ResolveDependencies_MovesToFront(t *testing.T) {
	t.Skip("Requires cache to track dependencies - use integration tests for end-to-end testing")
}

func TestProcessor_ResolveDependencies_Recursive(t *testing.T) {
	t.Skip("Requires cache to track dependencies - use integration tests for end-to-end testing")
}

func TestProcessor_ResolveDependencies_Circular(t *testing.T) {
	t.Skip("Requires cache to track dependencies - use integration tests for end-to-end testing")
}

func TestProcessor_ResolveDependencies_SubjectScoped(t *testing.T) {
	t.Skip("Requires cache to track dependencies - use integration tests for end-to-end testing")
}

// Phase 10 Tests: findNextWork()

func TestProcessor_FindNextWork_FIFO(t *testing.T) {
	// Test that work is pulled from queue in FIFO order
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})
	processor := NewProcessor(registry, market, nil)

	// Manually add items to queue
	processor.workQueue = []*queuedWork{
		{TypeID: "first", Subject: ""},
		{TypeID: "second", Subject: ""},
		{TypeID: "third", Subject: ""},
	}
	processor.queuedItems["first"] = true
	processor.queuedItems["second"] = true
	processor.queuedItems["third"] = true

	// Register work types so they can be found
	registry.Register(&WorkType{ID: "first"})
	registry.Register(&WorkType{ID: "second"})
	registry.Register(&WorkType{ID: "third"})

	item, wt := processor.findNextWork()
	require.NotNil(t, item)
	assert.Equal(t, "first", wt.ID)

	item, wt = processor.findNextWork()
	require.NotNil(t, item)
	assert.Equal(t, "second", wt.ID)
}

func TestProcessor_FindNextWork_EmptyQueue(t *testing.T) {
	// Test empty queue returns nil
	registry := NewRegistry()
	market := NewMarketTimingChecker(&MockMarketChecker{allMarketsClosed: true})
	processor := NewProcessor(registry, market, nil)

	item, wt := processor.findNextWork()
	assert.Nil(t, item)
	assert.Nil(t, wt)
}

func TestProcessor_FindNextWork_ResolvesDependencies(t *testing.T) {
	t.Skip("Requires cache to track dependencies - use integration tests for end-to-end testing")
}

func TestProcessor_FindNextWork_RequeuesUnmetDependencies(t *testing.T) {
	t.Skip("Requires cache to track dependencies - use integration tests for end-to-end testing")
}
