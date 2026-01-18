package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/aristath/sentinel/internal/modules/planning"
	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

type RecommendationsHandler struct {
	service            *planning.Service
	recommendationRepo planning.RecommendationRepositoryInterface
	log                zerolog.Logger
}

func NewRecommendationsHandler(
	service *planning.Service,
	recommendationRepo planning.RecommendationRepositoryInterface,
	log zerolog.Logger,
) *RecommendationsHandler {
	return &RecommendationsHandler{
		service:            service,
		recommendationRepo: recommendationRepo,
		log:                log.With().Str("handler", "recommendations").Logger(),
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
	switch r.Method {
	case http.MethodGet:
		h.handleGet(w, r)
	case http.MethodPost:
		h.handlePost(w, r)
	default:
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
	}
}

func (h *RecommendationsHandler) handleGet(w http.ResponseWriter, r *http.Request) {
	// Parse query parameters
	planView := r.URL.Query().Get("plan") == "true"
	limit := 0
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		if l, err := strconv.Atoi(limitStr); err == nil && l > 0 {
			limit = l
		}
	}

	if planView {
		// Return formatted plan view
		plan, err := h.recommendationRepo.GetRecommendationsAsPlan(nil, 0)
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to get recommendations as plan")
			http.Error(w, "Failed to retrieve recommendations", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(plan)
	} else {
		// Return raw recommendations list
		recommendations, err := h.recommendationRepo.GetPendingRecommendations(limit)
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to get pending recommendations")
			http.Error(w, "Failed to retrieve recommendations", http.StatusInternalServerError)
			return
		}

		response := map[string]interface{}{
			"recommendations": recommendations,
		}

		// Include rejected opportunities and pre-filtered securities for debugging
		// Get portfolio hash from first recommendation (if available)
		var portfolioHash string
		if len(recommendations) > 0 {
			portfolioHash = recommendations[0].PortfolioHash
		}

		if portfolioHash != "" {
			// Get rejected opportunities
			if rejected := h.recommendationRepo.GetRejectedOpportunities(portfolioHash); len(rejected) > 0 {
				response["rejected_opportunities"] = rejected
			}

			// Get pre-filtered securities
			if preFiltered := h.recommendationRepo.GetPreFilteredSecurities(portfolioHash); len(preFiltered) > 0 {
				response["pre_filtered_securities"] = preFiltered
			}

			// Get rejected sequences
			if rejectedSeqs := h.recommendationRepo.GetRejectedSequences(portfolioHash); len(rejectedSeqs) > 0 {
				response["rejected_sequences"] = rejectedSeqs
			}
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}
}

func (h *RecommendationsHandler) handlePost(w http.ResponseWriter, r *http.Request) {
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
