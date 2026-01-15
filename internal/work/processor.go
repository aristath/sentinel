package work

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/rs/zerolog/log"
)

// Processor is the main work processor that executes work items.
// It processes one work item at a time, respecting dependencies and market timing.
type Processor struct {
	registry   *Registry
	completion *CompletionTracker
	market     *MarketTimingChecker
	timeout    time.Duration

	trigger    chan struct{}
	done       chan struct{}
	stop       chan struct{}
	stopped    chan struct{}
	retryQueue []*WorkItem
	inFlight   map[string]bool // Track currently executing work
	mu         sync.Mutex
}

// NewProcessor creates a new work processor.
func NewProcessor(registry *Registry, completion *CompletionTracker, market *MarketTimingChecker) *Processor {
	return NewProcessorWithTimeout(registry, completion, market, WorkTimeout)
}

// NewProcessorWithTimeout creates a new work processor with a custom timeout.
// This is primarily used for testing.
func NewProcessorWithTimeout(registry *Registry, completion *CompletionTracker, market *MarketTimingChecker, timeout time.Duration) *Processor {
	return &Processor{
		registry:   registry,
		completion: completion,
		market:     market,
		timeout:    timeout,
		trigger:    make(chan struct{}, 1),
		done:       make(chan struct{}, 1),
		stop:       make(chan struct{}),
		stopped:    make(chan struct{}),
		retryQueue: make([]*WorkItem, 0),
		inFlight:   make(map[string]bool),
	}
}

// Run starts the processor loop. This blocks until Stop() is called.
func (p *Processor) Run() {
	defer close(p.stopped)

	for {
		select {
		case <-p.stop:
			return
		case <-p.trigger:
			p.processOne()
		case <-p.done:
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
func (p *Processor) ExecuteNow(workTypeID string, subject string) error {
	wt := p.registry.Get(workTypeID)
	if wt == nil {
		return fmt.Errorf("unknown work type: %s", workTypeID)
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

		ctx, cancel := context.WithTimeout(context.Background(), p.timeout)
		defer cancel()

		err := p.executeWithContext(ctx, item, wt)
		if err != nil {
			if ctx.Err() == context.DeadlineExceeded {
				log.Error().Str("work", item.ID).Msg("work timed out")
			} else {
				log.Error().Err(err).Str("work", item.ID).Msg("work failed")
			}

			item.Retries++
			if item.Retries < MaxRetries {
				p.pushRetryQueue(item)
			} else {
				log.Warn().Str("work", item.ID).Int("retries", item.Retries).Msg("max retries reached, skipping")
			}
		} else {
			p.completion.MarkCompleted(item)
		}
	}()
}

// findNextWork finds the next work item to execute.
func (p *Processor) findNextWork() (*WorkItem, *WorkType) {
	workTypes := p.registry.ByPriority()

	for _, wt := range workTypes {
		subjects := wt.FindSubjects()
		if subjects == nil {
			continue
		}

		for _, subject := range subjects {
			// Check market timing
			if !p.market.CanExecute(wt.MarketTiming, subject) {
				continue
			}

			// Check interval staleness
			if wt.Interval > 0 && !p.completion.IsStale(wt.ID, subject, wt.Interval) {
				continue
			}

			// Check dependencies
			if !p.dependenciesMet(wt, subject) {
				continue
			}

			return NewWorkItem(wt, subject), wt
		}
	}

	return nil, nil
}

// dependenciesMet checks if all dependencies for a work type have been completed.
// For per-security work, dependencies are scoped to the same subject (ISIN).
func (p *Processor) dependenciesMet(wt *WorkType, subject string) bool {
	if len(wt.DependsOn) == 0 {
		return true
	}

	for _, depID := range wt.DependsOn {
		_, exists := p.completion.GetCompletion(depID, subject)
		if !exists {
			return false
		}
	}

	return true
}

// executeItem executes a work item synchronously.
func (p *Processor) executeItem(item *WorkItem, wt *WorkType) error {
	ctx, cancel := context.WithTimeout(context.Background(), p.timeout)
	defer cancel()

	return p.executeWithContext(ctx, item, wt)
}

// executeWithContext executes a work item with a context.
func (p *Processor) executeWithContext(ctx context.Context, item *WorkItem, wt *WorkType) error {
	return wt.Execute(ctx, item.Subject)
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
