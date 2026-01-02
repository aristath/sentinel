package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/aristath/arduino-trader/internal/modules/planning"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

type RecommendationsHandler struct {
	service *planning.Service
	log     zerolog.Logger
}

func NewRecommendationsHandler(service *planning.Service, log zerolog.Logger) *RecommendationsHandler {
	return &RecommendationsHandler{
		service: service,
		log:     log.With().Str("handler", "recommendations").Logger(),
	}
}

type RecommendationsRequest struct {
	OpportunityContext *domain.OpportunityContext   `json:"opportunity_context"`
	Config             *domain.PlannerConfiguration `json:"config"`
}

type RecommendationsResponse struct {
	Plan *domain.HolisticPlan `json:"plan"`
}

func (h *RecommendationsHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req RecommendationsRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	plan, err := h.service.CreatePlan(req.OpportunityContext, req.Config)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to create plan")
		http.Error(w, "Failed to create plan", http.StatusInternalServerError)
		return
	}

	response := RecommendationsResponse{Plan: plan}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}
