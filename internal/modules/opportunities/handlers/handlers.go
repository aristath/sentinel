// Package handlers provides HTTP handlers for opportunities operations.
package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/aristath/sentinel/internal/modules/opportunities"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	planningrepo "github.com/aristath/sentinel/internal/modules/planning/repository"
	"github.com/aristath/sentinel/internal/services"
	"github.com/rs/zerolog"
)

// Handler handles opportunities HTTP requests
type Handler struct {
	service        *opportunities.Service
	configRepo     *planningrepo.ConfigRepository
	contextBuilder *services.OpportunityContextBuilder
	log            zerolog.Logger
}

// NewHandler creates a new opportunities handler
func NewHandler(
	service *opportunities.Service,
	configRepo *planningrepo.ConfigRepository,
	contextBuilder *services.OpportunityContextBuilder,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		service:        service,
		configRepo:     configRepo,
		contextBuilder: contextBuilder,
		log:            log.With().Str("handler", "opportunities").Logger(),
	}
}

// HandleGetAll handles GET /api/opportunities/all
func (h *Handler) HandleGetAll(w http.ResponseWriter, r *http.Request) {
	// Check for nil contextBuilder
	if h.contextBuilder == nil {
		h.log.Error().Msg("Context builder not configured")
		http.Error(w, "Context builder not configured", http.StatusInternalServerError)
		return
	}

	// Build opportunity context using unified builder
	// Opportunities handler doesn't use optimizer weights, pass nil to use allocation targets
	ctx, err := h.contextBuilder.Build(nil)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to build opportunity context")
		http.Error(w, "Failed to build opportunity context", http.StatusInternalServerError)
		return
	}

	// Load planner configuration
	config, err := h.loadPlannerConfig()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to load planner config")
		http.Error(w, "Failed to load planner config", http.StatusInternalServerError)
		return
	}

	// Apply configuration to context (sets AllowBuy, AllowSell, transaction costs)
	ctx.ApplyConfig(config)

	// Identify opportunities
	opportunities, err := h.service.IdentifyOpportunities(ctx, config)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to identify opportunities")
		http.Error(w, "Failed to identify opportunities", http.StatusInternalServerError)
		return
	}

	// Convert to response format
	allOpportunities := make([]map[string]interface{}, 0)
	for category, candidates := range opportunities {
		for _, candidate := range candidates {
			allOpportunities = append(allOpportunities, map[string]interface{}{
				"symbol":    candidate.Symbol,
				"isin":      candidate.ISIN,
				"name":      candidate.Name,
				"side":      candidate.Side,
				"quantity":  candidate.Quantity,
				"price":     candidate.Price,
				"value_eur": candidate.ValueEUR,
				"currency":  candidate.Currency,
				"reason":    candidate.Reason,
				"priority":  candidate.Priority,
				"category":  string(category),
			})
		}
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"opportunities": allOpportunities,
			"count":         len(allOpportunities),
			"by_category":   opportunities,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// handleCategoryOpportunities is a helper for category-specific endpoints
func (h *Handler) handleCategoryOpportunities(w http.ResponseWriter, r *http.Request, category planningdomain.OpportunityCategory) {
	// Check for nil contextBuilder
	if h.contextBuilder == nil {
		h.log.Error().Msg("Context builder not configured")
		http.Error(w, "Context builder not configured", http.StatusInternalServerError)
		return
	}

	// Build opportunity context using unified builder
	// Opportunities handler doesn't use optimizer weights, pass nil to use allocation targets
	ctx, err := h.contextBuilder.Build(nil)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to build opportunity context")
		http.Error(w, "Failed to build opportunity context", http.StatusInternalServerError)
		return
	}

	// Load planner configuration
	config, err := h.loadPlannerConfig()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to load planner config")
		http.Error(w, "Failed to load planner config", http.StatusInternalServerError)
		return
	}

	// Apply configuration to context (sets AllowBuy, AllowSell, transaction costs)
	ctx.ApplyConfig(config)

	// Identify opportunities
	allOpportunities, err := h.service.IdentifyOpportunities(ctx, config)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to identify opportunities")
		http.Error(w, "Failed to identify opportunities", http.StatusInternalServerError)
		return
	}

	// Filter by category
	categoryOpps := allOpportunities[category]
	if categoryOpps == nil {
		categoryOpps = []planningdomain.ActionCandidate{}
	}

	// Convert to response format
	opps := make([]map[string]interface{}, 0, len(categoryOpps))
	for _, candidate := range categoryOpps {
		opps = append(opps, map[string]interface{}{
			"symbol":    candidate.Symbol,
			"isin":      candidate.ISIN,
			"name":      candidate.Name,
			"side":      candidate.Side,
			"quantity":  candidate.Quantity,
			"price":     candidate.Price,
			"value_eur": candidate.ValueEUR,
			"currency":  candidate.Currency,
			"reason":    candidate.Reason,
			"priority":  candidate.Priority,
		})
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"opportunities": opps,
			"count":         len(opps),
			"category":      string(category),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetProfitTaking handles GET /api/opportunities/profit-taking
func (h *Handler) HandleGetProfitTaking(w http.ResponseWriter, r *http.Request) {
	h.handleCategoryOpportunities(w, r, planningdomain.OpportunityCategoryProfitTaking)
}

// HandleGetAveragingDown handles GET /api/opportunities/averaging-down
func (h *Handler) HandleGetAveragingDown(w http.ResponseWriter, r *http.Request) {
	h.handleCategoryOpportunities(w, r, planningdomain.OpportunityCategoryAveragingDown)
}

// HandleGetOpportunityBuys handles GET /api/opportunities/opportunity-buys
func (h *Handler) HandleGetOpportunityBuys(w http.ResponseWriter, r *http.Request) {
	h.handleCategoryOpportunities(w, r, planningdomain.OpportunityCategoryOpportunityBuys)
}

// HandleGetRebalanceBuys handles GET /api/opportunities/rebalance-buys
func (h *Handler) HandleGetRebalanceBuys(w http.ResponseWriter, r *http.Request) {
	h.handleCategoryOpportunities(w, r, planningdomain.OpportunityCategoryRebalanceBuys)
}

// HandleGetRebalanceSells handles GET /api/opportunities/rebalance-sells
func (h *Handler) HandleGetRebalanceSells(w http.ResponseWriter, r *http.Request) {
	h.handleCategoryOpportunities(w, r, planningdomain.OpportunityCategoryRebalanceSells)
}

// HandleGetWeightBased handles GET /api/opportunities/weight-based
func (h *Handler) HandleGetWeightBased(w http.ResponseWriter, r *http.Request) {
	h.handleCategoryOpportunities(w, r, planningdomain.OpportunityCategoryWeightBased)
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

// loadPlannerConfig loads planner configuration
func (h *Handler) loadPlannerConfig() (*planningdomain.PlannerConfiguration, error) {
	if h.configRepo == nil {
		return nil, fmt.Errorf("config repository not initialized")
	}

	config, err := h.configRepo.GetDefaultConfig()
	if err != nil {
		return nil, fmt.Errorf("failed to load planner config: %w", err)
	}
	return config, nil
}

// writeJSON writes a JSON response
func (h *Handler) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)

	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
	}
}
