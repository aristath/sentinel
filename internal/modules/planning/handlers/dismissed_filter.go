package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/aristath/sentinel/internal/modules/planning/repository"
	"github.com/rs/zerolog"
)

// DismissedFilterHandler handles dismissed filter operations.
type DismissedFilterHandler struct {
	repo *repository.DismissedFilterRepository
	log  zerolog.Logger
}

// NewDismissedFilterHandler creates a new dismissed filter handler.
func NewDismissedFilterHandler(repo *repository.DismissedFilterRepository, log zerolog.Logger) *DismissedFilterHandler {
	return &DismissedFilterHandler{
		repo: repo,
		log:  log.With().Str("handler", "dismissed_filter").Logger(),
	}
}

// DismissFilterRequest is the request body for dismissing/undismissing a filter.
type DismissFilterRequest struct {
	ISIN       string `json:"isin"`
	Calculator string `json:"calculator"`
	Reason     string `json:"reason"`
}

// Dismiss handles POST /api/planning/dismiss-filter
func (h *DismissedFilterHandler) Dismiss(w http.ResponseWriter, r *http.Request) {
	var req DismissFilterRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode dismiss request")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validate required fields
	if req.ISIN == "" || req.Calculator == "" || req.Reason == "" {
		http.Error(w, "isin, calculator, and reason are required", http.StatusBadRequest)
		return
	}

	if err := h.repo.Dismiss(req.ISIN, req.Calculator, req.Reason); err != nil {
		h.log.Error().Err(err).
			Str("isin", req.ISIN).
			Str("calculator", req.Calculator).
			Str("reason", req.Reason).
			Msg("Failed to dismiss filter")
		http.Error(w, "Failed to dismiss filter", http.StatusInternalServerError)
		return
	}

	h.log.Info().
		Str("isin", req.ISIN).
		Str("calculator", req.Calculator).
		Str("reason", req.Reason).
		Msg("Filter dismissed")

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "dismissed"})
}

// Undismiss handles DELETE /api/planning/dismiss-filter
func (h *DismissedFilterHandler) Undismiss(w http.ResponseWriter, r *http.Request) {
	var req DismissFilterRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode undismiss request")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validate required fields
	if req.ISIN == "" || req.Calculator == "" || req.Reason == "" {
		http.Error(w, "isin, calculator, and reason are required", http.StatusBadRequest)
		return
	}

	if err := h.repo.Undismiss(req.ISIN, req.Calculator, req.Reason); err != nil {
		h.log.Error().Err(err).
			Str("isin", req.ISIN).
			Str("calculator", req.Calculator).
			Str("reason", req.Reason).
			Msg("Failed to undismiss filter")
		http.Error(w, "Failed to undismiss filter", http.StatusInternalServerError)
		return
	}

	h.log.Info().
		Str("isin", req.ISIN).
		Str("calculator", req.Calculator).
		Str("reason", req.Reason).
		Msg("Filter undismissed")

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "undismissed"})
}

// GetAll handles GET /api/planning/dismissed-filters
func (h *DismissedFilterHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	filters, err := h.repo.GetAll()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get dismissed filters")
		http.Error(w, "Failed to get dismissed filters", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(filters); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode dismissed filters response")
	}
}
