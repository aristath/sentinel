package handlers

import (
	"fmt"
	"net/http"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/planning"
	"github.com/rs/zerolog"
)

// StreamHandler handles Server-Sent Events (SSE) for cache invalidation and updates.
type StreamHandler struct {
	service *planning.Service
	log     zerolog.Logger
}

// NewStreamHandler creates a new stream handler.
func NewStreamHandler(service *planning.Service, log zerolog.Logger) *StreamHandler {
	return &StreamHandler{
		service: service,
		log:     log.With().Str("handler", "stream").Logger(),
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

	// Get portfolio hash from query param
	portfolioHash := r.URL.Query().Get("portfolio_hash")

	h.log.Info().
		Str("portfolio_hash", portfolioHash).
		Msg("Client connected to event stream")

	// Create done channel to detect client disconnect
	done := r.Context().Done()

	// Send initial connection message
	fmt.Fprintf(w, "event: connected\n")
	fmt.Fprintf(w, "data: {\"message\": \"Connected to planning event stream\"}\n\n")
	flusher.Flush()

	// TODO: Implement actual SSE event broadcasting
	// This would:
	// 1. Subscribe to a Redis pub/sub channel or event bus
	// 2. Listen for events: "sequences_updated", "evaluation_progress", "plan_ready"
	// 3. Stream events to client in real-time
	// 4. Handle client disconnection gracefully

	// For now, send periodic heartbeat messages
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-done:
			h.log.Info().
				Str("portfolio_hash", portfolioHash).
				Msg("Client disconnected from event stream")
			return

		case <-ticker.C:
			// Send heartbeat
			fmt.Fprintf(w, "event: heartbeat\n")
			fmt.Fprintf(w, "data: {\"timestamp\": \"%s\"}\n\n", time.Now().Format(time.RFC3339))
			flusher.Flush()
		}
	}
}
