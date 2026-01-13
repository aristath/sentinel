// Package handlers provides HTTP handlers for sequence generation operations.
package handlers

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/sequences"
	"github.com/rs/zerolog"
)

// Handler handles sequence generation HTTP requests
type Handler struct {
	service *sequences.Service
	log     zerolog.Logger
}

// NewHandler creates a new sequences handler
func NewHandler(
	service *sequences.Service,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		service: service,
		log:     log.With().Str("handler", "sequences").Logger(),
	}
}

// GenerateRequest represents a request to generate sequences
type GenerateRequest struct {
	Opportunities domain.OpportunitiesByCategory `json:"opportunities"`
	Context       *domain.OpportunityContext     `json:"context"`
	Config        *domain.PlannerConfiguration   `json:"config"`
}

// FilterRequest represents a request to filter sequences
type FilterRequest struct {
	Sequences []domain.ActionSequence      `json:"sequences"`
	Config    *domain.PlannerConfiguration `json:"config"`
}

// HandleGenerate handles POST /api/sequences/generate
// This is the main entry point for sequence generation using the exhaustive generator.
func (h *Handler) HandleGenerate(w http.ResponseWriter, r *http.Request) {
	var req GenerateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request body")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Create a minimal context if not provided
	ctx := req.Context
	if ctx == nil {
		ctx = &domain.OpportunityContext{
			AllowSell:           true,
			AllowBuy:            true,
			RecentlySoldISINs:   make(map[string]bool),
			RecentlyBoughtISINs: make(map[string]bool),
			IneligibleISINs:     make(map[string]bool),
		}
	}

	// Use default configuration if not provided
	if req.Config == nil {
		req.Config = domain.NewDefaultConfiguration()
	}

	// Pass nil for progress callback in HTTP handlers (no streaming support)
	sequences, err := h.service.GenerateSequences(req.Opportunities, ctx, req.Config, nil)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to generate sequences")
		http.Error(w, "Failed to generate sequences", http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"sequences": sequences,
			"count":     len(sequences),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
			"generator": "exhaustive",
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetInfo handles GET /api/sequences/info
// Returns information about the sequence generation system.
func (h *Handler) HandleGetInfo(w http.ResponseWriter, r *http.Request) {
	response := map[string]interface{}{
		"data": map[string]interface{}{
			"generator":   "exhaustive",
			"description": "Generates all valid combinations of opportunities up to max_depth",
			"features": []string{
				"combinatorial generation",
				"constraint filtering during generation",
				"cash feasibility pruning",
				"order-independent deduplication",
			},
			"filters": []string{
				"dedupe",
				"correlation",
				"diversity",
			},
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleFilterCorrelation handles POST /api/sequences/filter/correlation
func (h *Handler) HandleFilterCorrelation(w http.ResponseWriter, r *http.Request) {
	var req FilterRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request body")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Note: Correlation filtering requires historical data
	// For direct API calls, we return sequences as-is
	response := map[string]interface{}{
		"data": map[string]interface{}{
			"sequences": req.Sequences,
			"count":     len(req.Sequences),
			"filter":    "correlation",
			"note":      "Correlation filtering requires historical data - use full planner flow",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// writeJSON writes a JSON response
func (h *Handler) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)

	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
	}
}
