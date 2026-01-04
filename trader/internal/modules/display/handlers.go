package display

import (
	"encoding/json"
	"net/http"

	"github.com/rs/zerolog"
)

// Handlers provides HTTP handlers for display module
type Handlers struct {
	stateManager *StateManager
	log          zerolog.Logger
}

// NewHandlers creates a new display handlers instance
func NewHandlers(stateManager *StateManager, log zerolog.Logger) *Handlers {
	return &Handlers{
		stateManager: stateManager,
		log:          log.With().Str("module", "display_handlers").Logger(),
	}
}

// HandleGetState handles GET /api/display/state
// Returns current display state (text, LED3, LED4)
func (h *Handlers) HandleGetState(w http.ResponseWriter, r *http.Request) {
	state := h.stateManager.GetState()

	h.writeJSON(w, state)
}

// SetTextRequest represents the request to set display text
type SetTextRequest struct {
	Text string `json:"text"`
}

// HandleSetText handles POST /api/display/text
// Sets the display text
func (h *Handlers) HandleSetText(w http.ResponseWriter, r *http.Request) {
	var req SetTextRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode set text request")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	h.stateManager.SetText(req.Text)

	h.writeJSON(w, map[string]string{"status": "ok", "text": req.Text})
}

// SetLEDRequest represents the request to set LED color
type SetLEDRequest struct {
	R int `json:"r"`
	G int `json:"g"`
	B int `json:"b"`
}

// HandleSetLED3 handles POST /api/display/led3
// Sets LED 3 RGB color
func (h *Handlers) HandleSetLED3(w http.ResponseWriter, r *http.Request) {
	var req SetLEDRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode set LED3 request")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	h.stateManager.SetLED3(req.R, req.G, req.B)

	h.writeJSON(w, map[string]string{"status": "ok"})
}

// HandleSetLED4 handles POST /api/display/led4
// Sets LED 4 RGB color
func (h *Handlers) HandleSetLED4(w http.ResponseWriter, r *http.Request) {
	var req SetLEDRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode set LED4 request")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	h.stateManager.SetLED4(req.R, req.G, req.B)

	h.writeJSON(w, map[string]string{"status": "ok"})
}

// writeJSON writes a JSON response
func (h *Handlers) writeJSON(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
		http.Error(w, "Internal server error", http.StatusInternalServerError)
	}
}
