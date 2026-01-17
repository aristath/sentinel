package work

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/rs/zerolog/log"
)

// PeriodicTriggerInterval is the fallback interval for checking time-based work eligibility.
// This ensures interval-based work runs even when no events fire.
const PeriodicTriggerInterval = 1 * time.Minute

// queuedWork represents an item in the work queue
type queuedWork struct {
	TypeID  string
	Subject string
}

// Processor is the main work processor that executes work items.
// It processes one work item at a time, respecting dependencies and market timing.
type Processor struct {
	registry     *Registry
	market       *MarketTimingChecker
	cache        *Cache
	eventEmitter EventEmitter
	timeout      time.Duration

	trigger    chan struct{}
	done       chan struct{}
	stop       chan struct{}
	stopped    chan struct{}
	retryQueue []*WorkItem
	inFlight   map[string]bool // Track currently executing work

	// FIFO queue fields
	workQueue   []*queuedWork   // FIFO queue of pending work
	queuedItems map[string]bool // Prevents duplicates ("typeID:subject" → true)

	mu sync.Mutex
}

// NewProcessor creates a new work processor.
func NewProcessor(registry *Registry, market *MarketTimingChecker, cache *Cache) *Processor {
	return NewProcessorWithTimeout(registry, market, cache, WorkTimeout)
}

// NewProcessorWithTimeout creates a new work processor with a custom timeout.
// This is primarily used for testing.
func NewProcessorWithTimeout(registry *Registry, market *MarketTimingChecker, cache *Cache, timeout time.Duration) *Processor {
	return &Processor{
		registry:    registry,
		market:      market,
		cache:       cache,
		timeout:     timeout,
		trigger:     make(chan struct{}, 1),
		done:        make(chan struct{}, 1),
		stop:        make(chan struct{}),
		stopped:     make(chan struct{}),
		retryQueue:  make([]*WorkItem, 0),
		inFlight:    make(map[string]bool),
		workQueue:   make([]*queuedWork, 0),
		queuedItems: make(map[string]bool),
	}
}

// SetEventEmitter sets the event emitter for progress reporting.
// This should be called before Run() to enable progress events.
func (p *Processor) SetEventEmitter(emitter EventEmitter) {
	p.eventEmitter = emitter
}

// makeQueueKey creates unique key for tracking queued items
func makeQueueKey(typeID, subject string) string {
	if subject == "" {
		return typeID
	}
	return typeID + ":" + subject
}

// Run starts the processor loop. This blocks until Stop() is called.
func (p *Processor) Run() {
	defer close(p.stopped)

	// Create periodic ticker for time-based eligibility checks
	ticker := time.NewTicker(PeriodicTriggerInterval)
	defer ticker.Stop()

	for {
		select {
		case <-p.stop:
			return
		case <-p.trigger:
			p.populateQueue()
			p.processOne()
		case <-p.done:
			p.processOne() // Previous work done, immediately check for next
		case <-ticker.C:
			// Periodic check for new eligible work (failsafe)
			// populateQueue() already prevents duplicates via queuedItems map
			p.populateQueue()
			p.processOne()
		}
	}
}

// Stop stops the processor.
func (p *Processor) Stop() {
	close(p.stop)
	<-p.stopped
}

// Trigger wakes up the processor to check for work.
// This is non-blocking and can be called from any goroutine.
func (p *Processor) Trigger() {
	select {
	case p.trigger <- struct{}{}:
	default:
		// Trigger already pending
	}
}

// ExecuteNow immediately executes a specific work type, bypassing timing checks.
// This is used for manual triggers via the API.
// Note: This bypasses market timing and interval checks, but still respects dependencies.
func (p *Processor) ExecuteNow(workTypeID string, subject string) error {
	wt := p.registry.Get(workTypeID)
	if wt == nil {
		return fmt.Errorf("unknown work type: %s", workTypeID)
	}

	// Still check dependencies - can't run work if deps haven't completed
	if !p.dependenciesMet(wt, subject) {
		return fmt.Errorf("dependencies not met for work type %s", workTypeID)
	}

	item := NewWorkItem(wt, subject)
	return p.executeItem(item, wt)
}

// processOne finds and executes the next eligible work item.
func (p *Processor) processOne() {
	p.mu.Lock()
	// Check if we're already executing something
	if len(p.inFlight) > 0 {
		p.mu.Unlock()
		return
	}
	p.mu.Unlock()

	// Try regular work first
	item, wt := p.findNextWork()
	if item == nil {
		// Try retry queue
		item, wt = p.popRetryQueue()
	}
	if item == nil {
		return
	}

	// Mark as in-flight
	p.mu.Lock()
	p.inFlight[item.ID] = true
	p.mu.Unlock()

	// Execute asynchronously
	go func() {
		defer func() {
			p.mu.Lock()
			delete(p.inFlight, item.ID)
			p.mu.Unlock()

			// Signal done to trigger next work
			select {
			case p.done <- struct{}{}:
			default:
			}
		}()

		err := p.executeItem(item, wt)

		// Handle retries on failure
		if err != nil {
			item.Retries++
			if item.Retries < MaxRetries {
				p.pushRetryQueue(item)
			} else {
				log.Warn().Str("work", item.ID).Int("retries", item.Retries).Msg("max retries reached, skipping")
			}
		}
	}()
}

// populateQueue scans all work types and adds eligible work to queue.
// Does NOT check dependencies - those are resolved at execution time.
func (p *Processor) populateQueue() {
	workTypes := p.registry.All() // Registration order

	for _, wt := range workTypes {
		subjects := wt.FindSubjects()
		if subjects == nil {
			continue
		}

		for _, subject := range subjects {
			key := makeQueueKey(wt.ID, subject)

			// Check if already queued (needs lock for read)
			p.mu.Lock()
			alreadyQueued := p.queuedItems[key]
			p.mu.Unlock()

			if alreadyQueued {
				continue
			}

			// Check market timing
			if !p.market.CanExecute(wt.MarketTiming, subject) {
				continue
			}

			// Check interval staleness via cache
			if wt.Interval > 0 && p.cache != nil {
				expiresAt := p.cache.GetExpiresAt(makeQueueKey(wt.ID, subject))
				if time.Now().Unix() < expiresAt {
					continue // Not expired yet
				}
			}

			// Add to queue (needs lock for write)
			p.mu.Lock()
			// Double-check in case another goroutine added it
			if !p.queuedItems[key] {
				p.workQueue = append(p.workQueue, &queuedWork{
					TypeID:  wt.ID,
					Subject: subject,
				})
				p.queuedItems[key] = true
			}
			p.mu.Unlock()
		}
	}
}

// resolveDependencies ensures all dependencies are satisfied.
// If dependency not completed:
// - If in queue: move to front
// - If not in queue: add to front recursively
// Returns true if dependencies were added/moved (retry needed)
func (p *Processor) resolveDependencies(wt *WorkType, subject string, visited map[string]bool) bool {
	if len(wt.DependsOn) == 0 {
		return false // No dependencies
	}

	// If cache is not available (e.g., in integration tests), assume dependencies are met
	// Integration tests use FindSubjects to control execution flow
	// Unit tests of this function should provide a real cache
	if p.cache == nil {
		return false
	}

	needsResolution := false

	for _, depID := range wt.DependsOn {
		// Check if dependency completed (cache entry exists)
		if p.cache.GetExpiresAt(makeQueueKey(depID, subject)) != 0 {
			continue // Dependency completed
		}

		// Circular dependency detection
		depKey := makeQueueKey(depID, subject)
		if visited[depKey] {
			log.Warn().
				Str("work", wt.ID).
				Str("dependency", depID).
				Str("subject", subject).
				Msg("Circular dependency detected, skipping")
			continue
		}
		visited[depKey] = true

		// Get dependency work type
		depWT := p.registry.Get(depID)
		if depWT == nil {
			log.Warn().
				Str("work", wt.ID).
				Str("dependency", depID).
				Msg("Unknown dependency, skipping")
			continue
		}

		// If dependency in queue, move to front
		if p.queuedItems[depKey] {
			p.moveToFront(depID, subject)
			needsResolution = true
			continue
		}

		// Check if dependency can run now
		if !p.market.CanExecute(depWT.MarketTiming, subject) {
			needsResolution = true
			continue
		}

		// Recursively resolve dependency's dependencies
		if p.resolveDependencies(depWT, subject, visited) {
			needsResolution = true
		}

		// Add dependency to front
		p.workQueue = append([]*queuedWork{{TypeID: depID, Subject: subject}}, p.workQueue...)
		p.queuedItems[depKey] = true
		needsResolution = true
	}

	return needsResolution
}

// moveToFront moves queued item to front of queue
func (p *Processor) moveToFront(typeID, subject string) {
	for i, qw := range p.workQueue {
		if qw.TypeID == typeID && qw.Subject == subject {
			// Remove from current position
			p.workQueue = append(p.workQueue[:i], p.workQueue[i+1:]...)
			// Add to front
			p.workQueue = append([]*queuedWork{{TypeID: typeID, Subject: subject}}, p.workQueue...)
			return
		}
	}
}

// findNextWork gets next work item from FIFO queue.
// Performs dependency resolution at execution time.
func (p *Processor) findNextWork() (*WorkItem, *WorkType) {
	p.mu.Lock()
	defer p.mu.Unlock()

	// Try each queued item until we find one with satisfied dependencies
	for len(p.workQueue) > 0 {
		// Pop from front (FIFO)
		qw := p.workQueue[0]
		p.workQueue = p.workQueue[1:]

		key := makeQueueKey(qw.TypeID, qw.Subject)
		delete(p.queuedItems, key)

		// Get work type
		wt := p.registry.Get(qw.TypeID)
		if wt == nil {
			continue
		}

		// Resolve dependencies at execution time
		visited := make(map[string]bool)
		if p.resolveDependencies(wt, qw.Subject, visited) {
			// Dependencies were added/moved - re-queue this item at end
			p.workQueue = append(p.workQueue, qw)
			p.queuedItems[key] = true
			continue
		}

		// All dependencies satisfied - execute!
		return NewWorkItem(wt, qw.Subject), wt
	}

	return nil, nil
}

// dependenciesMet checks if all dependencies for a work type have been completed.
// For per-security work, dependencies are scoped to the same subject (ISIN).
func (p *Processor) dependenciesMet(wt *WorkType, subject string) bool {
	if len(wt.DependsOn) == 0 {
		return true
	}

	// If cache is not available (e.g., in tests), assume dependencies are met
	// Tests use FindSubjects to prevent re-execution
	if p.cache == nil {
		return true
	}

	for _, depID := range wt.DependsOn {
		// Check if dependency completed (cache entry exists)
		if p.cache.GetExpiresAt(makeQueueKey(depID, subject)) == 0 {
			return false // Dependency not completed
		}
	}

	return true
}

// executeItem executes a work item synchronously.
func (p *Processor) executeItem(item *WorkItem, wt *WorkType) error {
	// Check cache expiration before executing
	if p.cache != nil {
		expiresAt := p.cache.GetExpiresAt(item.ID)
		if time.Now().Unix() < expiresAt {
			// Cache not expired, skip execution
			return nil
		}
	}

	startTime := time.Now()

	// Create progress reporter
	progress := NewProgressReporter(p.eventEmitter, item.ID, item.TypeID, item.Subject)

	// Emit started event
	progress.emitStarted()

	ctx, cancel := context.WithTimeout(context.Background(), p.timeout)
	defer cancel()

	err := p.executeWithContext(ctx, item, wt, progress)
	duration := time.Since(startTime)

	if err != nil {
		progress.emitFailed(err, duration, item.Retries)
	} else {
		progress.emitCompleted(duration)

		// Update cache with new expiration
		if p.cache != nil && wt.Interval > 0 {
			expiresAt := time.Now().Add(wt.Interval).Unix()
			if err := p.cache.Set(item.ID, expiresAt); err != nil {
				log.Warn().Err(err).Str("work", item.ID).Msg("Failed to update cache")
			}
		}
	}

	return err
}

// executeWithContext executes a work item with a context.
func (p *Processor) executeWithContext(ctx context.Context, item *WorkItem, wt *WorkType, progress *ProgressReporter) error {
	return wt.Execute(ctx, item.Subject, progress)
}

// pushRetryQueue adds an item to the retry queue.
func (p *Processor) pushRetryQueue(item *WorkItem) {
	p.mu.Lock()
	defer p.mu.Unlock()

	p.retryQueue = append(p.retryQueue, item)
}

// popRetryQueue removes and returns the first item from the retry queue.
func (p *Processor) popRetryQueue() (*WorkItem, *WorkType) {
	p.mu.Lock()
	defer p.mu.Unlock()

	if len(p.retryQueue) == 0 {
		return nil, nil
	}

	item := p.retryQueue[0]
	p.retryQueue = p.retryQueue[1:]

	wt := p.registry.Get(item.TypeID)
	if wt == nil {
		return nil, nil
	}

	return item, wt
}

// GetRegistry returns the work type registry.
// This allows external access to registered work types for status reporting.
func (p *Processor) GetRegistry() *Registry {
	return p.registry
}
