package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/aristath/arduino-trader/internal/modules/planning"
	"github.com/rs/zerolog"
)

// BatchHandler handles triggering batch plan generation.
type BatchHandler struct {
	service *planning.Service
	log     zerolog.Logger
}

// NewBatchHandler creates a new batch handler.
func NewBatchHandler(service *planning.Service, log zerolog.Logger) *BatchHandler {
	return &BatchHandler{
		service: service,
		log:     log.With().Str("handler", "batch").Logger(),
	}
}

// BatchRequest represents a request to trigger batch generation.
type BatchRequest struct {
	PortfolioHash string `json:"portfolio_hash"`
	Force         bool   `json:"force,omitempty"` // Force regeneration even if recent results exist
}

// BatchResponse represents the batch generation response.
type BatchResponse struct {
	Success       bool   `json:"success"`
	Message       string `json:"message"`
	JobID         string `json:"job_id,omitempty"`
	PortfolioHash string `json:"portfolio_hash"`
}

// ServeHTTP handles POST /api/planning/batch requests.
func (h *BatchHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req BatchRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	h.log.Info().
		Str("portfolio_hash", req.PortfolioHash).
		Bool("force", req.Force).
		Msg("Triggering batch plan generation")

	// TODO: Implement actual batch generation logic
	// This would:
	// 1. Generate portfolio hash if not provided
	// 2. Check if recent results exist (unless force=true)
	// 3. Trigger background job for sequence generation
	// 4. Trigger incremental evaluation
	// 5. Return job ID for status tracking

	// For now, return a placeholder response
	response := BatchResponse{
		Success:       true,
		Message:       "Batch generation initiated (placeholder)",
		JobID:         "job_placeholder_123",
		PortfolioHash: req.PortfolioHash,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted) // 202 Accepted for async processing
	json.NewEncoder(w).Encode(response)
}
