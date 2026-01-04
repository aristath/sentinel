package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/aristath/arduino-trader/internal/modules/opportunities"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// IdentifyHandler handles POST /api/opportunities/identify requests.
type IdentifyHandler struct {
	service *opportunities.Service
	log     zerolog.Logger
}

// NewIdentifyHandler creates a new identify handler.
func NewIdentifyHandler(service *opportunities.Service, log zerolog.Logger) *IdentifyHandler {
	return &IdentifyHandler{
		service: service,
		log:     log.With().Str("handler", "identify_opportunities").Logger(),
	}
}

// IdentifyRequest represents the request body for identifying opportunities.
type IdentifyRequest struct {
	OpportunityContext *domain.OpportunityContext   `json:"opportunity_context"`
	Config             *domain.PlannerConfiguration `json:"config"`
}

// IdentifyResponse represents the response for identifying opportunities.
type IdentifyResponse struct {
	Opportunities domain.OpportunitiesByCategory `json:"opportunities"`
	Summary       OpportunitySummary             `json:"summary"`
}

// OpportunitySummary provides a summary of identified opportunities.
type OpportunitySummary struct {
	TotalCandidates int                        `json:"total_candidates"`
	ByCategory      map[string]CategorySummary `json:"by_category"`
}

// CategorySummary provides summary stats for a category.
type CategorySummary struct {
	Count          int     `json:"count"`
	TotalBuyValue  float64 `json:"total_buy_value,omitempty"`
	TotalSellValue float64 `json:"total_sell_value,omitempty"`
}

// ServeHTTP handles the HTTP request.
func (h *IdentifyHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Parse request
	var req IdentifyRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validate request
	if req.OpportunityContext == nil {
		http.Error(w, "opportunity_context is required", http.StatusBadRequest)
		return
	}

	if req.Config == nil {
		http.Error(w, "config is required", http.StatusBadRequest)
		return
	}

	h.log.Info().
		Float64("available_cash", req.OpportunityContext.AvailableCashEUR).
		Int("positions", len(req.OpportunityContext.Positions)).
		Msg("Identifying opportunities")

	// Identify opportunities
	opportunities, err := h.service.IdentifyOpportunities(req.OpportunityContext, req.Config)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to identify opportunities")
		http.Error(w, "Failed to identify opportunities", http.StatusInternalServerError)
		return
	}

	// Build summary
	summary := h.buildSummary(opportunities)

	// Build response
	response := IdentifyResponse{
		Opportunities: opportunities,
		Summary:       summary,
	}

	h.log.Info().
		Int("total_candidates", summary.TotalCandidates).
		Int("categories", len(summary.ByCategory)).
		Msg("Opportunities identified successfully")

	// Return response
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(response); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode response")
	}
}

// buildSummary builds a summary of the opportunities.
func (h *IdentifyHandler) buildSummary(opportunities domain.OpportunitiesByCategory) OpportunitySummary {
	summary := OpportunitySummary{
		ByCategory: make(map[string]CategorySummary),
	}

	for category, candidates := range opportunities {
		var buyValue, sellValue float64
		for _, candidate := range candidates {
			if candidate.Side == "BUY" {
				buyValue += candidate.ValueEUR
			} else if candidate.Side == "SELL" {
				sellValue += candidate.ValueEUR
			}
		}

		summary.ByCategory[string(category)] = CategorySummary{
			Count:          len(candidates),
			TotalBuyValue:  buyValue,
			TotalSellValue: sellValue,
		}

		summary.TotalCandidates += len(candidates)
	}

	return summary
}
