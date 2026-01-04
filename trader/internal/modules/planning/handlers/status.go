package handlers

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/planning/repository"
	"github.com/rs/zerolog"
)

// StatusHandler handles status queries for planning operations.
type StatusHandler struct {
	repository *repository.PlannerRepository
	log        zerolog.Logger
}

// NewStatusHandler creates a new status handler.
func NewStatusHandler(repo *repository.PlannerRepository, log zerolog.Logger) *StatusHandler {
	return &StatusHandler{
		repository: repo,
		log:        log.With().Str("handler", "status").Logger(),
	}
}

// StatusResponse represents the planning status response.
type StatusResponse struct {
	PortfolioHash      string  `json:"portfolio_hash"`
	Status             string  `json:"status"`   // "idle", "generating", "evaluating", "complete"
	Progress           float64 `json:"progress"` // 0.0 to 1.0
	SequencesTotal     int     `json:"sequences_total"`
	SequencesEvaluated int     `json:"sequences_evaluated"`
	BestScoreFound     float64 `json:"best_score_found,omitempty"`
	LastUpdated        string  `json:"last_updated"`
	Message            string  `json:"message,omitempty"`
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

	// Query database for sequences and evaluations
	totalSequences, err := h.repository.CountSequences(portfolioHash)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to count sequences")
		http.Error(w, "Failed to retrieve status", http.StatusInternalServerError)
		return
	}

	totalEvaluations, err := h.repository.CountEvaluations(portfolioHash)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to count evaluations")
		http.Error(w, "Failed to retrieve status", http.StatusInternalServerError)
		return
	}

	// Get best result if available
	var bestScore float64
	var lastUpdated string
	bestResult, err := h.repository.GetBestResult(portfolioHash)
	if err == nil && bestResult != nil {
		bestScore = bestResult.EndStateScore
		lastUpdated = time.Now().Format(time.RFC3339) // Use current time since HolisticPlan doesn't have timestamp
	}

	// Determine status
	var status string
	var progress float64
	var message string

	if totalSequences == 0 {
		status = "idle"
		progress = 0.0
		message = "No sequences generated yet"
	} else if totalEvaluations == 0 {
		status = "generating"
		progress = 0.0
		message = "Sequences generated, awaiting evaluation"
	} else if totalEvaluations < totalSequences {
		status = "evaluating"
		progress = float64(totalEvaluations) / float64(totalSequences)
		message = "Evaluation in progress"
	} else {
		status = "complete"
		progress = 1.0
		message = "All sequences evaluated"
	}

	if lastUpdated == "" {
		lastUpdated = time.Now().Format(time.RFC3339)
	}

	response := StatusResponse{
		PortfolioHash:      portfolioHash,
		Status:             status,
		Progress:           progress,
		SequencesTotal:     totalSequences,
		SequencesEvaluated: totalEvaluations,
		BestScoreFound:     bestScore,
		LastUpdated:        lastUpdated,
		Message:            message,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}
