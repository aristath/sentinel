package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/aristath/arduino-trader/internal/modules/planning"
	"github.com/rs/zerolog"
)

// StatusHandler handles status queries for planning operations.
type StatusHandler struct {
	service *planning.Service
	log     zerolog.Logger
}

// NewStatusHandler creates a new status handler.
func NewStatusHandler(service *planning.Service, log zerolog.Logger) *StatusHandler {
	return &StatusHandler{
		service: service,
		log:     log.With().Str("handler", "status").Logger(),
	}
}

// StatusResponse represents the planning status response.
type StatusResponse struct {
	PortfolioHash     string  `json:"portfolio_hash"`
	Status            string  `json:"status"`            // "idle", "generating", "evaluating", "complete"
	Progress          float64 `json:"progress"`          // 0.0 to 1.0
	SequencesTotal    int     `json:"sequences_total"`
	SequencesEvaluated int     `json:"sequences_evaluated"`
	BestScoreFound    float64 `json:"best_score_found,omitempty"`
	LastUpdated       string  `json:"last_updated"`
	Message           string  `json:"message,omitempty"`
}

// ServeHTTP handles GET /api/planning/status requests.
func (h *StatusHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Get portfolio hash from query param
	portfolioHash := r.URL.Query().Get("portfolio_hash")
	if portfolioHash == "" {
		http.Error(w, "portfolio_hash query parameter required", http.StatusBadRequest)
		return
	}

	h.log.Debug().
		Str("portfolio_hash", portfolioHash).
		Msg("Getting planning status")

	// TODO: Implement actual status retrieval
	// This would:
	// 1. Query database for sequences and evaluations by portfolio hash
	// 2. Calculate progress based on completed evaluations
	// 3. Get best score found so far
	// 4. Determine current status (idle, generating, evaluating, complete)
	// 5. Return comprehensive status

	// For now, return a placeholder response
	response := StatusResponse{
		PortfolioHash:      portfolioHash,
		Status:             "complete",
		Progress:           1.0,
		SequencesTotal:     100,
		SequencesEvaluated: 100,
		BestScoreFound:     0.8542,
		LastUpdated:        "2024-01-02T18:00:00Z",
		Message:            "All sequences evaluated (placeholder)",
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}
