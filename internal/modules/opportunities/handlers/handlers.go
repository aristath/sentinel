// Package handlers provides HTTP handlers for opportunities operations.
package handlers

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/aristath/sentinel/internal/modules/opportunities"
	"github.com/rs/zerolog"
)

// Handler handles opportunities HTTP requests
type Handler struct {
	service *opportunities.Service
	log     zerolog.Logger
}

// NewHandler creates a new opportunities handler
func NewHandler(
	service *opportunities.Service,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		service: service,
		log:     log.With().Str("handler", "opportunities").Logger(),
	}
}

// HandleGetAll handles GET /api/opportunities/all
func (h *Handler) HandleGetAll(w http.ResponseWriter, r *http.Request) {
	// Return 501 Not Implemented - requires complex planning context
	h.writeJSON(w, http.StatusNotImplemented, map[string]interface{}{
		"error": map[string]interface{}{
			"message": "Opportunity identification not yet implemented as standalone API",
			"code":    "NOT_IMPLEMENTED",
			"details": map[string]string{
				"reason": "Requires full planning context (portfolio state, market conditions, allocation targets) which cannot be easily constructed from API request alone",
				"note":   "This functionality is available internally to the planner but not exposed as a standalone API endpoint yet",
			},
		},
	})
}

// HandleGetProfitTaking handles GET /api/opportunities/profit-taking
func (h *Handler) HandleGetProfitTaking(w http.ResponseWriter, r *http.Request) {
	h.writeJSON(w, http.StatusNotImplemented, map[string]interface{}{
		"error": map[string]interface{}{
			"message": "Profit-taking opportunities not yet implemented as standalone API",
			"code":    "NOT_IMPLEMENTED",
			"details": map[string]string{
				"reason": "Requires full planning context (portfolio state, market conditions, allocation targets) which cannot be easily constructed from API request alone",
				"note":   "This functionality is available internally to the planner but not exposed as a standalone API endpoint yet",
			},
		},
	})
}

// HandleGetAveragingDown handles GET /api/opportunities/averaging-down
func (h *Handler) HandleGetAveragingDown(w http.ResponseWriter, r *http.Request) {
	h.writeJSON(w, http.StatusNotImplemented, map[string]interface{}{
		"error": map[string]interface{}{
			"message": "Averaging-down opportunities not yet implemented as standalone API",
			"code":    "NOT_IMPLEMENTED",
			"details": map[string]string{
				"reason": "Requires full planning context (portfolio state, market conditions, allocation targets) which cannot be easily constructed from API request alone",
				"note":   "This functionality is available internally to the planner but not exposed as a standalone API endpoint yet",
			},
		},
	})
}

// HandleGetOpportunityBuys handles GET /api/opportunities/opportunity-buys
func (h *Handler) HandleGetOpportunityBuys(w http.ResponseWriter, r *http.Request) {
	h.writeJSON(w, http.StatusNotImplemented, map[string]interface{}{
		"error": map[string]interface{}{
			"message": "Opportunity buys not yet implemented as standalone API",
			"code":    "NOT_IMPLEMENTED",
			"details": map[string]string{
				"reason": "Requires full planning context (portfolio state, market conditions, allocation targets) which cannot be easily constructed from API request alone",
				"note":   "This functionality is available internally to the planner but not exposed as a standalone API endpoint yet",
			},
		},
	})
}

// HandleGetRebalanceBuys handles GET /api/opportunities/rebalance-buys
func (h *Handler) HandleGetRebalanceBuys(w http.ResponseWriter, r *http.Request) {
	h.writeJSON(w, http.StatusNotImplemented, map[string]interface{}{
		"error": map[string]interface{}{
			"message": "Rebalance buys not yet implemented as standalone API",
			"code":    "NOT_IMPLEMENTED",
			"details": map[string]string{
				"reason": "Requires full planning context (portfolio state, market conditions, allocation targets) which cannot be easily constructed from API request alone",
				"note":   "This functionality is available internally to the planner but not exposed as a standalone API endpoint yet",
			},
		},
	})
}

// HandleGetRebalanceSells handles GET /api/opportunities/rebalance-sells
func (h *Handler) HandleGetRebalanceSells(w http.ResponseWriter, r *http.Request) {
	h.writeJSON(w, http.StatusNotImplemented, map[string]interface{}{
		"error": map[string]interface{}{
			"message": "Rebalance sells not yet implemented as standalone API",
			"code":    "NOT_IMPLEMENTED",
			"details": map[string]string{
				"reason": "Requires full planning context (portfolio state, market conditions, allocation targets) which cannot be easily constructed from API request alone",
				"note":   "This functionality is available internally to the planner but not exposed as a standalone API endpoint yet",
			},
		},
	})
}

// HandleGetWeightBased handles GET /api/opportunities/weight-based
func (h *Handler) HandleGetWeightBased(w http.ResponseWriter, r *http.Request) {
	h.writeJSON(w, http.StatusNotImplemented, map[string]interface{}{
		"error": map[string]interface{}{
			"message": "Weight-based opportunities not yet implemented as standalone API",
			"code":    "NOT_IMPLEMENTED",
			"details": map[string]string{
				"reason": "Requires full planning context (portfolio state, market conditions, allocation targets) which cannot be easily constructed from API request alone",
				"note":   "This functionality is available internally to the planner but not exposed as a standalone API endpoint yet",
			},
		},
	})
}

// HandleGetRegistry handles GET /api/opportunities/registry
func (h *Handler) HandleGetRegistry(w http.ResponseWriter, r *http.Request) {
	registry := h.service.GetRegistry()
	calculators := registry.List()

	calcInfo := make([]map[string]interface{}, 0, len(calculators))
	for _, calc := range calculators {
		calcInfo = append(calcInfo, map[string]interface{}{
			"name":     calc.Name(),
			"category": string(calc.Category()),
		})
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"calculators": calcInfo,
			"count":       len(calcInfo),
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
