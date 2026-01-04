package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/rs/zerolog"
)

// PlanningEvent represents an event in the planning system.
type PlanningEvent struct {
	Type          string                 `json:"type"`           // Event type: "sequences_updated", "evaluation_progress", "plan_ready"
	PortfolioHash string                 `json:"portfolio_hash"` // Portfolio this event relates to
	Timestamp     time.Time              `json:"timestamp"`
	Data          map[string]interface{} `json:"data,omitempty"`
}

// EventBroadcaster manages SSE event subscriptions and broadcasting.
type EventBroadcaster struct {
	subscribers map[chan PlanningEvent]string // channel -> portfolioHash
	mu          sync.RWMutex
	log         zerolog.Logger
}

// NewEventBroadcaster creates a new event broadcaster.
func NewEventBroadcaster(log zerolog.Logger) *EventBroadcaster {
	return &EventBroadcaster{
		subscribers: make(map[chan PlanningEvent]string),
		log:         log.With().Str("component", "event_broadcaster").Logger(),
	}
}

// Subscribe adds a new subscriber for a specific portfolio hash.
func (eb *EventBroadcaster) Subscribe(portfolioHash string) chan PlanningEvent {
	eb.mu.Lock()
	defer eb.mu.Unlock()

	ch := make(chan PlanningEvent, 10) // Buffer to prevent blocking
	eb.subscribers[ch] = portfolioHash

	eb.log.Debug().
		Str("portfolio_hash", portfolioHash).
		Int("total_subscribers", len(eb.subscribers)).
		Msg("New subscriber added")

	return ch
}

// Unsubscribe removes a subscriber.
func (eb *EventBroadcaster) Unsubscribe(ch chan PlanningEvent) {
	eb.mu.Lock()
	defer eb.mu.Unlock()

	portfolioHash := eb.subscribers[ch]
	delete(eb.subscribers, ch)
	close(ch)

	eb.log.Debug().
		Str("portfolio_hash", portfolioHash).
		Int("total_subscribers", len(eb.subscribers)).
		Msg("Subscriber removed")
}

// Publish broadcasts an event to all relevant subscribers.
func (eb *EventBroadcaster) Publish(event PlanningEvent) {
	eb.mu.RLock()
	defer eb.mu.RUnlock()

	event.Timestamp = time.Now()

	eb.log.Debug().
		Str("event_type", event.Type).
		Str("portfolio_hash", event.PortfolioHash).
		Int("subscriber_count", len(eb.subscribers)).
		Msg("Publishing event")

	// Broadcast to all subscribers for this portfolio (or all if hash is empty)
	for ch, portfolioHash := range eb.subscribers {
		// Send to subscribers for this specific portfolio or subscribers with no filter
		if event.PortfolioHash == "" || portfolioHash == "" || portfolioHash == event.PortfolioHash {
			select {
			case ch <- event:
				// Event sent successfully
			default:
				// Channel buffer full, skip this subscriber
				eb.log.Warn().
					Str("portfolio_hash", portfolioHash).
					Msg("Subscriber channel full, event dropped")
			}
		}
	}
}

// StreamHandler handles Server-Sent Events (SSE) for cache invalidation and updates.
type StreamHandler struct {
	broadcaster *EventBroadcaster
	log         zerolog.Logger
}

// NewStreamHandler creates a new stream handler.
func NewStreamHandler(broadcaster *EventBroadcaster, log zerolog.Logger) *StreamHandler {
	return &StreamHandler{
		broadcaster: broadcaster,
		log:         log.With().Str("handler", "stream").Logger(),
	}
}

// ServeHTTP handles GET /api/planning/stream requests (SSE).
func (h *StreamHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Set SSE headers
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	// Get flusher for streaming
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "Streaming not supported", http.StatusInternalServerError)
		return
	}

	// Get portfolio hash from query param (optional - if empty, receives all events)
	portfolioHash := r.URL.Query().Get("portfolio_hash")

	h.log.Info().
		Str("portfolio_hash", portfolioHash).
		Msg("Client connected to event stream")

	// Subscribe to planning events
	eventChan := h.broadcaster.Subscribe(portfolioHash)
	defer h.broadcaster.Unsubscribe(eventChan)

	// Create done channel to detect client disconnect
	done := r.Context().Done()

	// Send initial connection message
	fmt.Fprintf(w, "event: connected\n")
	fmt.Fprintf(w, "data: {\"message\": \"Connected to planning event stream\"}\n\n")
	flusher.Flush()

	// Heartbeat ticker to keep connection alive
	heartbeat := time.NewTicker(30 * time.Second)
	defer heartbeat.Stop()

	for {
		select {
		case <-done:
			// Client disconnected
			h.log.Info().
				Str("portfolio_hash", portfolioHash).
				Msg("Client disconnected from event stream")
			return

		case event := <-eventChan:
			// Received planning event - forward to client
			h.log.Debug().
				Str("event_type", event.Type).
				Str("portfolio_hash", event.PortfolioHash).
				Msg("Sending event to client")

			// Marshal event data to JSON
			eventData, err := json.Marshal(event)
			if err != nil {
				h.log.Error().Err(err).Msg("Failed to marshal event")
				continue
			}

			// Send SSE event
			fmt.Fprintf(w, "event: %s\n", event.Type)
			fmt.Fprintf(w, "data: %s\n\n", string(eventData))
			flusher.Flush()

		case <-heartbeat.C:
			// Send periodic heartbeat to keep connection alive
			fmt.Fprintf(w, "event: heartbeat\n")
			fmt.Fprintf(w, "data: {\"timestamp\": \"%s\"}\n\n", time.Now().Format(time.RFC3339))
			flusher.Flush()
		}
	}
}
