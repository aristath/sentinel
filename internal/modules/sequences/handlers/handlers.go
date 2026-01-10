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

// GenerateFromPatternRequest represents a request to generate sequences from a specific pattern
type GenerateFromPatternRequest struct {
	PatternType   string                         `json:"pattern_type"`
	Opportunities domain.OpportunitiesByCategory `json:"opportunities"`
	Config        *domain.PlannerConfiguration   `json:"config"`
}

// GenerateCombinatorialRequest represents a request to combine multiple patterns
type GenerateCombinatorialRequest struct {
	PatternTypes  []string                       `json:"pattern_types"`
	Opportunities domain.OpportunitiesByCategory `json:"opportunities"`
	Config        *domain.PlannerConfiguration   `json:"config"`
}

// GenerateFromAllRequest represents a request to generate from all patterns
type GenerateFromAllRequest struct {
	Opportunities domain.OpportunitiesByCategory `json:"opportunities"`
	Config        *domain.PlannerConfiguration   `json:"config"`
}

// FilterRequest represents a request to filter sequences
type FilterRequest struct {
	Sequences []domain.ActionSequence      `json:"sequences"`
	Config    *domain.PlannerConfiguration `json:"config"`
}

// HandleGenerateFromPattern handles POST /api/sequences/generate/pattern
func (h *Handler) HandleGenerateFromPattern(w http.ResponseWriter, r *http.Request) {
	var req GenerateFromPatternRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request body")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if req.PatternType == "" {
		http.Error(w, "pattern_type is required", http.StatusBadRequest)
		return
	}

	// Enable only the specified pattern
	if req.Config == nil {
		req.Config = domain.NewDefaultConfiguration()
		// Disable all patterns first
		h.disableAllPatterns(req.Config)
	}

	// Enable the requested pattern
	h.enablePattern(req.Config, req.PatternType)

	sequences, err := h.service.GenerateSequences(req.Opportunities, req.Config)
	if err != nil {
		h.log.Error().Err(err).Str("pattern_type", req.PatternType).Msg("Failed to generate sequences")
		http.Error(w, "Failed to generate sequences", http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"sequences":    sequences,
			"count":        len(sequences),
			"pattern_type": req.PatternType,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGenerateCombinatorial handles POST /api/sequences/generate/combinatorial
func (h *Handler) HandleGenerateCombinatorial(w http.ResponseWriter, r *http.Request) {
	var req GenerateCombinatorialRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request body")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if len(req.PatternTypes) == 0 {
		http.Error(w, "pattern_types is required and must not be empty", http.StatusBadRequest)
		return
	}

	// Enable only the specified patterns
	if req.Config == nil {
		req.Config = domain.NewDefaultConfiguration()
		// Disable all patterns first
		h.disableAllPatterns(req.Config)
	}

	// Enable the requested patterns
	for _, patternType := range req.PatternTypes {
		h.enablePattern(req.Config, patternType)
	}

	sequences, err := h.service.GenerateSequences(req.Opportunities, req.Config)
	if err != nil {
		h.log.Error().Err(err).Strs("pattern_types", req.PatternTypes).Msg("Failed to generate combinatorial sequences")
		http.Error(w, "Failed to generate sequences", http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"sequences":     sequences,
			"count":         len(sequences),
			"pattern_types": req.PatternTypes,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGenerateFromAllPatterns handles POST /api/sequences/generate/all-patterns
func (h *Handler) HandleGenerateFromAllPatterns(w http.ResponseWriter, r *http.Request) {
	var req GenerateFromAllRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request body")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Use default configuration which has all patterns enabled
	if req.Config == nil {
		req.Config = domain.NewDefaultConfiguration()
	} else {
		// Enable all patterns
		h.enableAllPatterns(req.Config)
	}

	sequences, err := h.service.GenerateSequences(req.Opportunities, req.Config)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to generate sequences from all patterns")
		http.Error(w, "Failed to generate sequences", http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"sequences": sequences,
			"count":     len(sequences),
			"note":      "Generated from all 13 available patterns",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleListPatterns handles GET /api/sequences/patterns
func (h *Handler) HandleListPatterns(w http.ResponseWriter, r *http.Request) {
	patterns := []map[string]interface{}{
		{"name": "adaptive", "description": "Adaptive pattern based on market regime"},
		{"name": "averaging_down", "description": "Buy more of losing positions at lower prices"},
		{"name": "cash_generation", "description": "Generate cash through strategic sells"},
		{"name": "cost_optimized", "description": "Optimize for commission costs"},
		{"name": "deep_rebalance", "description": "Deep portfolio rebalancing"},
		{"name": "direct_buy", "description": "Direct buy opportunities"},
		{"name": "market_regime", "description": "Market regime-based pattern"},
		{"name": "mixed_strategy", "description": "Mixed buy and sell strategy"},
		{"name": "multi_sell", "description": "Multiple sell opportunities"},
		{"name": "opportunity_first", "description": "Prioritize best opportunities"},
		{"name": "profit_taking", "description": "Take profits from winning positions"},
		{"name": "rebalance", "description": "Portfolio rebalancing"},
		{"name": "single_best", "description": "Single best opportunity"},
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"patterns": patterns,
			"count":    len(patterns),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleFilterEligibility handles POST /api/sequences/filter/eligibility
func (h *Handler) HandleFilterEligibility(w http.ResponseWriter, r *http.Request) {
	var req FilterRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request body")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Note: This is a placeholder - proper filtering requires full context
	// For now, we return the sequences as-is
	response := map[string]interface{}{
		"data": map[string]interface{}{
			"sequences": req.Sequences,
			"count":     len(req.Sequences),
			"filter":    "eligibility",
			"note":      "Eligibility filtering requires full planner context",
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

	// Note: This is a placeholder - proper correlation filtering requires historical data
	// For now, we return the sequences as-is
	response := map[string]interface{}{
		"data": map[string]interface{}{
			"sequences": req.Sequences,
			"count":     len(req.Sequences),
			"filter":    "correlation",
			"note":      "Correlation filtering requires historical data access",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleFilterRecentlyTraded handles POST /api/sequences/filter/recently-traded
func (h *Handler) HandleFilterRecentlyTraded(w http.ResponseWriter, r *http.Request) {
	var req FilterRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request body")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Note: This is a placeholder - proper recently-traded filtering requires ledger data
	response := map[string]interface{}{
		"data": map[string]interface{}{
			"sequences": req.Sequences,
			"count":     len(req.Sequences),
			"filter":    "recently_traded",
			"note":      "Recently-traded filtering requires ledger database access",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleFilterTags handles POST /api/sequences/filter/tags
func (h *Handler) HandleFilterTags(w http.ResponseWriter, r *http.Request) {
	var req FilterRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request body")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Note: This is a placeholder - proper tag filtering requires universe database
	response := map[string]interface{}{
		"data": map[string]interface{}{
			"sequences": req.Sequences,
			"count":     len(req.Sequences),
			"filter":    "tags",
			"note":      "Tag filtering requires universe database access",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetContext handles GET /api/sequences/context
func (h *Handler) HandleGetContext(w http.ResponseWriter, r *http.Request) {
	patterns := []string{
		"adaptive", "averaging_down", "cash_generation", "cost_optimized",
		"deep_rebalance", "direct_buy", "market_regime", "mixed_strategy",
		"multi_sell", "opportunity_first", "profit_taking", "rebalance", "single_best",
	}

	filters := []string{
		"eligibility", "correlation", "recently_traded", "tags",
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"patterns": map[string]interface{}{
				"available": patterns,
				"count":     len(patterns),
			},
			"filters": map[string]interface{}{
				"available": filters,
				"count":     len(filters),
			},
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// enablePattern enables a specific pattern in the configuration
func (h *Handler) enablePattern(config *domain.PlannerConfiguration, patternType string) {
	switch patternType {
	case "adaptive":
		config.EnableAdaptivePattern = true
	case "averaging_down":
		config.EnableAveragingDownPattern = true
	case "cash_generation":
		config.EnableCashGenerationPattern = true
	case "cost_optimized":
		config.EnableCostOptimizedPattern = true
	case "deep_rebalance":
		config.EnableDeepRebalancePattern = true
	case "direct_buy":
		config.EnableDirectBuyPattern = true
	case "market_regime":
		config.EnableMarketRegimePattern = true
	case "mixed_strategy":
		config.EnableMixedStrategyPattern = true
	case "multi_sell":
		config.EnableMultiSellPattern = true
	case "opportunity_first":
		config.EnableOpportunityFirstPattern = true
	case "profit_taking":
		config.EnableProfitTakingPattern = true
	case "rebalance":
		config.EnableRebalancePattern = true
	case "single_best":
		config.EnableSingleBestPattern = true
	}
}

// disableAllPatterns disables all patterns in the configuration
func (h *Handler) disableAllPatterns(config *domain.PlannerConfiguration) {
	config.EnableAdaptivePattern = false
	config.EnableAveragingDownPattern = false
	config.EnableCashGenerationPattern = false
	config.EnableCostOptimizedPattern = false
	config.EnableDeepRebalancePattern = false
	config.EnableDirectBuyPattern = false
	config.EnableMarketRegimePattern = false
	config.EnableMixedStrategyPattern = false
	config.EnableMultiSellPattern = false
	config.EnableOpportunityFirstPattern = false
	config.EnableProfitTakingPattern = false
	config.EnableRebalancePattern = false
	config.EnableSingleBestPattern = false
}

// enableAllPatterns enables all patterns in the configuration
func (h *Handler) enableAllPatterns(config *domain.PlannerConfiguration) {
	config.EnableAdaptivePattern = true
	config.EnableAveragingDownPattern = true
	config.EnableCashGenerationPattern = true
	config.EnableCostOptimizedPattern = true
	config.EnableDeepRebalancePattern = true
	config.EnableDirectBuyPattern = true
	config.EnableMarketRegimePattern = true
	config.EnableMixedStrategyPattern = true
	config.EnableMultiSellPattern = true
	config.EnableOpportunityFirstPattern = true
	config.EnableProfitTakingPattern = true
	config.EnableRebalancePattern = true
	config.EnableSingleBestPattern = true
}

// writeJSON writes a JSON response
func (h *Handler) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)

	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
	}
}
