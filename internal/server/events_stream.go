// Package server provides the HTTP server and routing for Sentinel.
package server

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/aristath/sentinel/internal/events"
	"github.com/rs/zerolog"
)

// EventsStreamHandler handles unified Server-Sent Events (SSE) streaming for all system events.
type EventsStreamHandler struct {
	eventBus    *events.Bus
	dataDir     string
	log         zerolog.Logger
	logWatchers map[string]*logWatcher
	mu          sync.RWMutex
}

// logWatcher watches a log file for changes and emits events.
type logWatcher struct {
	filePath    string
	lastModTime time.Time
	lastSize    int64
	ticker      *time.Ticker
	stop        chan struct{}
}

// NewEventsStreamHandler creates a new unified events stream handler.
func NewEventsStreamHandler(eventBus *events.Bus, dataDir string, log zerolog.Logger) *EventsStreamHandler {
	return &EventsStreamHandler{
		eventBus:    eventBus,
		dataDir:     dataDir,
		log:         log.With().Str("component", "events_stream").Logger(),
		logWatchers: make(map[string]*logWatcher),
	}
}

// ServeHTTP handles GET /api/events/stream requests (SSE).
func (h *EventsStreamHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
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

	// Parse query parameters
	typesFilter := r.URL.Query().Get("types")
	logFile := r.URL.Query().Get("log_file")

	var allowedTypes map[events.EventType]bool
	if typesFilter != "" {
		allowedTypes = make(map[events.EventType]bool)
		for _, t := range strings.Split(typesFilter, ",") {
			allowedTypes[events.EventType(strings.TrimSpace(t))] = true
		}
	}

	h.log.Info().
		Str("types_filter", typesFilter).
		Str("log_file", logFile).
		Msg("Client connected to unified event stream")

	// Create event channel for this connection
	eventChan := make(chan *events.Event, 100) // Buffer to prevent blocking

	// Subscribe to all event types (or filtered subset)
	eventHandler := func(event *events.Event) {
		// Apply type filter if specified
		if allowedTypes != nil && !allowedTypes[event.Type] {
			return
		}

		// Non-blocking send (drop if channel full)
		select {
		case eventChan <- event:
		default:
			h.log.Warn().
				Str("event_type", string(event.Type)).
				Msg("Event channel full, dropping event")
		}
	}

	// Subscribe to all event types we care about
	eventTypes := []events.EventType{
		events.PriceUpdated,
		events.ScoreUpdated,
		events.SecuritySynced,
		events.SecurityAdded,
		events.PortfolioChanged,
		events.DepositProcessed,
		events.DividendCreated,
		events.TradeExecuted,
		events.CashUpdated,
		events.AllocationTargetsChanged,
		events.RecommendationsReady,
		events.PlanGenerated,
		events.PlanningStatusUpdated,
		events.SystemStatusChanged,
		events.TradernetStatusChanged,
		events.MarketsStatusChanged,
		events.SettingsChanged,
		events.PlannerConfigChanged,
		events.LogFileChanged,
	}

	// Subscribe to all event types (or just the ones in filter)
	if allowedTypes == nil {
		// Subscribe to all known types
		for _, eventType := range eventTypes {
			h.eventBus.Subscribe(eventType, eventHandler)
		}
	} else {
		// Subscribe only to filtered types
		for eventType := range allowedTypes {
			h.eventBus.Subscribe(eventType, eventHandler)
		}
	}

	// Start log file watcher if requested
	var logWatcher *logWatcher
	if logFile != "" {
		logWatcher = h.startLogWatcher(logFile, eventChan)
	}

	// Create done channel to detect client disconnect
	done := r.Context().Done()

	// Send initial connection message
	fmt.Fprintf(w, "data: %s\n\n", h.encodeEvent(map[string]interface{}{
		"type":    "connected",
		"message": "Connected to unified event stream",
	}))
	flusher.Flush()

	// Heartbeat ticker to keep connection alive
	heartbeat := time.NewTicker(30 * time.Second)
	defer heartbeat.Stop()

	for {
		select {
		case <-done:
			// Client disconnected
			if logWatcher != nil {
				h.stopLogWatcher(logFile)
			}
			h.log.Info().Msg("Client disconnected from event stream")
			return

		case event := <-eventChan:
			// Received event - forward to client
			h.log.Debug().
				Str("event_type", string(event.Type)).
				Msg("Sending event to client")

			// Marshal event to JSON
			eventJSON := h.encodeEvent(map[string]interface{}{
				"type":      string(event.Type),
				"module":    event.Module,
				"timestamp": event.Timestamp.Format(time.RFC3339),
				"data":      event.Data,
			})

			// Send SSE event (default message event)
			fmt.Fprintf(w, "data: %s\n\n", eventJSON)
			flusher.Flush()

		case <-heartbeat.C:
			// Send periodic heartbeat to keep connection alive
			fmt.Fprintf(w, "data: %s\n\n", h.encodeEvent(map[string]interface{}{
				"type":      "heartbeat",
				"timestamp": time.Now().Format(time.RFC3339),
			}))
			flusher.Flush()
		}
	}
}

// encodeEvent encodes an event map to JSON string.
func (h *EventsStreamHandler) encodeEvent(event map[string]interface{}) string {
	data, err := json.Marshal(event)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to marshal event")
		return `{"error":"failed to encode event"}`
	}
	return string(data)
}

// startLogWatcher starts watching a log file for changes.
func (h *EventsStreamHandler) startLogWatcher(logFile string, eventChan chan *events.Event) *logWatcher {
	// Validate log file name (prevent directory traversal)
	if strings.Contains(logFile, "..") || strings.Contains(logFile, "/") {
		h.log.Warn().Str("log_file", logFile).Msg("Invalid log file name")
		return nil
	}

	logsDir := filepath.Join(h.dataDir, "logs")
	logPath := filepath.Join(logsDir, logFile)

	// Verify file is within logs directory
	if !strings.HasPrefix(logPath, logsDir) {
		h.log.Warn().Str("log_path", logPath).Msg("Log file outside logs directory")
		return nil
	}

	h.mu.Lock()
	defer h.mu.Unlock()

	// Check if watcher already exists for this file
	if watcher, exists := h.logWatchers[logFile]; exists {
		return watcher
	}

	// Get initial file state
	info, err := os.Stat(logPath)
	if err != nil {
		h.log.Warn().Err(err).Str("log_file", logFile).Msg("Log file not found")
		return nil
	}

	watcher := &logWatcher{
		filePath:    logPath,
		lastModTime: info.ModTime(),
		lastSize:    info.Size(),
		ticker:      time.NewTicker(2 * time.Second),
		stop:        make(chan struct{}),
	}

	h.logWatchers[logFile] = watcher

	// Start watching in goroutine
	go func() {
		defer watcher.ticker.Stop()

		for {
			select {
			case <-watcher.stop:
				return
			case <-watcher.ticker.C:
				// Check file for changes
				info, err := os.Stat(watcher.filePath)
				if err != nil {
					// File might have been deleted or moved
					continue
				}

				// Check if file changed
				if info.ModTime().After(watcher.lastModTime) || info.Size() != watcher.lastSize {
					watcher.lastModTime = info.ModTime()
					watcher.lastSize = info.Size()

					// Emit log file changed event
					event := &events.Event{
						Type:      events.LogFileChanged,
						Module:    "log_watcher",
						Timestamp: time.Now(),
						Data: map[string]interface{}{
							"log_file": logFile,
						},
					}

					// Non-blocking send
					select {
					case eventChan <- event:
					default:
						// Channel full, drop event
					}
				}
			}
		}
	}()

	h.log.Info().Str("log_file", logFile).Msg("Started log file watcher")

	return watcher
}

// stopLogWatcher stops watching a log file.
func (h *EventsStreamHandler) stopLogWatcher(logFile string) {
	h.mu.Lock()
	defer h.mu.Unlock()

	watcher, exists := h.logWatchers[logFile]
	if !exists {
		return
	}

	close(watcher.stop)
	delete(h.logWatchers, logFile)

	h.log.Info().Str("log_file", logFile).Msg("Stopped log file watcher")
}
