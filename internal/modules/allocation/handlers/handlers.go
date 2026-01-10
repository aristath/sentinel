// Package handlers provides HTTP handlers for portfolio allocation management.
package handlers

import (
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"strings"
	"time"

	"github.com/aristath/sentinel/internal/events"
	"github.com/aristath/sentinel/internal/modules/allocation"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
)

// Handler handles allocation HTTP requests
// Faithful translation from Python: app/modules/allocation/api/allocation.py
type Handler struct {
	allocRepo                *allocation.Repository
	groupingRepo             *allocation.GroupingRepository
	alertService             *allocation.ConcentrationAlertService
	portfolioSummaryProvider allocation.PortfolioSummaryProvider
	eventManager             *events.Manager
	log                      zerolog.Logger
}

// NewHandler creates a new allocation handler
func NewHandler(
	allocRepo *allocation.Repository,
	groupingRepo *allocation.GroupingRepository,
	alertService *allocation.ConcentrationAlertService,
	portfolioSummaryProvider allocation.PortfolioSummaryProvider,
	eventManager *events.Manager,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		allocRepo:                allocRepo,
		groupingRepo:             groupingRepo,
		alertService:             alertService,
		portfolioSummaryProvider: portfolioSummaryProvider,
		eventManager:             eventManager,
		log:                      log.With().Str("handler", "allocation").Logger(),
	}
}

// HandleGetTargets returns allocation targets for country and industry groups
// Returns all groups from grouping tables, with target_pct from allocation_targets if set, otherwise 0.0
func (h *Handler) HandleGetTargets(w http.ResponseWriter, r *http.Request) {
	// Get all groups from grouping tables
	countryGroups, err := h.groupingRepo.GetCountryGroups()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	industryGroups, err := h.groupingRepo.GetIndustryGroups()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Get allocation targets (may be empty)
	countryTargets, err := h.allocRepo.GetCountryGroupTargets()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	industryTargets, err := h.allocRepo.GetIndustryGroupTargets()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Merge: Use target from allocation_targets if exists, otherwise default to 0.0
	mergedCountryTargets := make(map[string]float64)
	for groupName := range countryGroups {
		if targetPct, exists := countryTargets[groupName]; exists {
			mergedCountryTargets[groupName] = targetPct
		} else {
			mergedCountryTargets[groupName] = 0.0
		}
	}

	mergedIndustryTargets := make(map[string]float64)
	for groupName := range industryGroups {
		if targetPct, exists := industryTargets[groupName]; exists {
			mergedIndustryTargets[groupName] = targetPct
		} else {
			mergedIndustryTargets[groupName] = 0.0
		}
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"country":  mergedCountryTargets,
		"industry": mergedIndustryTargets,
	})
}

// HandleGetCountryGroups returns all country groups
// Faithful translation of Python: @router.get("/groups/country")
func (h *Handler) HandleGetCountryGroups(w http.ResponseWriter, r *http.Request) {
	groups, err := h.groupingRepo.GetCountryGroups()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"groups": groups,
	})
}

// HandleGetIndustryGroups returns all industry groups
// Faithful translation of Python: @router.get("/groups/industry")
func (h *Handler) HandleGetIndustryGroups(w http.ResponseWriter, r *http.Request) {
	groups, err := h.groupingRepo.GetIndustryGroups()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"groups": groups,
	})
}

// HandleUpdateCountryGroup creates or updates a country group
// Faithful translation of Python: @router.put("/groups/country")
func (h *Handler) HandleUpdateCountryGroup(w http.ResponseWriter, r *http.Request) {
	var req allocation.CountryGroup
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// Validate group name
	if strings.TrimSpace(req.GroupName) == "" {
		h.writeError(w, http.StatusBadRequest, "Group name is required")
		return
	}

	// Filter out empty strings and duplicates (same logic as Python)
	seen := make(map[string]bool)
	var countryNames []string
	for _, country := range req.CountryNames {
		trimmed := strings.TrimSpace(country)
		if trimmed != "" && !seen[trimmed] {
			seen[trimmed] = true
			countryNames = append(countryNames, trimmed)
		}
	}

	groupName := strings.TrimSpace(req.GroupName)
	if err := h.groupingRepo.SetCountryGroup(groupName, countryNames); err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"group_name":    groupName,
		"country_names": countryNames,
	})
}

// HandleUpdateIndustryGroup creates or updates an industry group
// Faithful translation of Python: @router.put("/groups/industry")
func (h *Handler) HandleUpdateIndustryGroup(w http.ResponseWriter, r *http.Request) {
	var req allocation.IndustryGroup
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// Validate group name
	if strings.TrimSpace(req.GroupName) == "" {
		h.writeError(w, http.StatusBadRequest, "Group name is required")
		return
	}

	// Filter out empty strings and duplicates (same logic as Python)
	seen := make(map[string]bool)
	var industryNames []string
	for _, industry := range req.IndustryNames {
		trimmed := strings.TrimSpace(industry)
		if trimmed != "" && !seen[trimmed] {
			seen[trimmed] = true
			industryNames = append(industryNames, trimmed)
		}
	}

	groupName := strings.TrimSpace(req.GroupName)
	if err := h.groupingRepo.SetIndustryGroup(groupName, industryNames); err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"group_name":     groupName,
		"industry_names": industryNames,
	})
}

// HandleDeleteCountryGroup deletes a country group
// Faithful translation of Python: @router.delete("/groups/country/{group_name}")
func (h *Handler) HandleDeleteCountryGroup(w http.ResponseWriter, r *http.Request) {
	groupName := chi.URLParam(r, "group_name")
	if groupName == "" {
		h.writeError(w, http.StatusBadRequest, "Group name is required")
		return
	}

	if err := h.groupingRepo.DeleteCountryGroup(groupName); err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"deleted": groupName,
	})
}

// HandleDeleteIndustryGroup deletes an industry group
// Faithful translation of Python: @router.delete("/groups/industry/{group_name}")
func (h *Handler) HandleDeleteIndustryGroup(w http.ResponseWriter, r *http.Request) {
	groupName := chi.URLParam(r, "group_name")
	if groupName == "" {
		h.writeError(w, http.StatusBadRequest, "Group name is required")
		return
	}

	if err := h.groupingRepo.DeleteIndustryGroup(groupName); err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"deleted": groupName,
	})
}

// HandleGetAvailableCountries returns list of all available countries
// Faithful translation of Python: @router.get("/groups/available/countries")
func (h *Handler) HandleGetAvailableCountries(w http.ResponseWriter, r *http.Request) {
	countries, err := h.groupingRepo.GetAvailableCountries()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"countries": countries,
	})
}

// HandleGetAvailableIndustries returns list of all available industries
// Faithful translation of Python: @router.get("/groups/available/industries")
func (h *Handler) HandleGetAvailableIndustries(w http.ResponseWriter, r *http.Request) {
	industries, err := h.groupingRepo.GetAvailableIndustries()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"industries": industries,
	})
}

// HandleUpdateCountryGroupTargets updates country group targets
// Faithful translation of Python: @router.put("/groups/targets/country")
func (h *Handler) HandleUpdateCountryGroupTargets(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Targets map[string]float64 `json:"targets"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	if len(req.Targets) == 0 {
		h.writeError(w, http.StatusBadRequest, "No weights provided")
		return
	}

	// Verify groups exist
	countryGroups, err := h.groupingRepo.GetCountryGroups()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	if len(countryGroups) == 0 {
		h.writeError(w, http.StatusBadRequest, "No country groups defined. Please create groups first.")
		return
	}

	// Store group targets directly (same logic as Python)
	for groupName, groupWeight := range req.Targets {
		if groupWeight < 0 || groupWeight > 1 {
			h.writeError(w, http.StatusBadRequest, fmt.Sprintf("Weight for %s must be between 0 and 1", groupName))
			return
		}

		target := allocation.AllocationTarget{
			Type:      "country_group",
			Name:      groupName,
			TargetPct: groupWeight,
		}

		if err := h.allocRepo.Upsert(target); err != nil {
			h.writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
	}

	// Return updated group targets
	resultGroups, err := h.allocRepo.GetCountryGroupTargets()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Only return groups with non-zero targets (same as Python)
	filteredGroups := make(map[string]float64)
	for k, v := range resultGroups {
		if v != 0 {
			filteredGroups[k] = v
		}
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"weights": filteredGroups,
		"count":   len(filteredGroups),
	})
}

// HandleUpdateIndustryGroupTargets updates industry group targets
// Faithful translation of Python: @router.put("/groups/targets/industry")
func (h *Handler) HandleUpdateIndustryGroupTargets(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Targets map[string]float64 `json:"targets"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	if len(req.Targets) == 0 {
		h.writeError(w, http.StatusBadRequest, "No weights provided")
		return
	}

	// Verify groups exist
	industryGroups, err := h.groupingRepo.GetIndustryGroups()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	if len(industryGroups) == 0 {
		h.writeError(w, http.StatusBadRequest, "No industry groups defined. Please create groups first.")
		return
	}

	// Store group targets directly (same logic as Python)
	for groupName, groupWeight := range req.Targets {
		if groupWeight < 0 || groupWeight > 1 {
			h.writeError(w, http.StatusBadRequest, fmt.Sprintf("Weight for %s must be between 0 and 1", groupName))
			return
		}

		target := allocation.AllocationTarget{
			Type:      "industry_group",
			Name:      groupName,
			TargetPct: groupWeight,
		}

		if err := h.allocRepo.Upsert(target); err != nil {
			h.writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
	}

	// Return updated group targets
	resultGroups, err := h.allocRepo.GetIndustryGroupTargets()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Only return groups with non-zero targets (same as Python)
	filteredGroups := make(map[string]float64)
	for k, v := range resultGroups {
		if v != 0 {
			filteredGroups[k] = v
		}
	}

	// Emit ALLOCATION_TARGETS_CHANGED event
	if h.eventManager != nil {
		h.eventManager.Emit(events.AllocationTargetsChanged, "allocation", map[string]interface{}{
			"type":  "industry",
			"count": len(filteredGroups),
		})
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"weights": filteredGroups,
		"count":   len(filteredGroups),
	})
}

// HandleGetGroupAllocation returns current allocation aggregated by groups
// Faithful translation of Python: @router.get("/groups/allocation")
func (h *Handler) HandleGetGroupAllocation(w http.ResponseWriter, r *http.Request) {
	// Get portfolio summary
	summary, err := h.portfolioSummaryProvider.GetPortfolioSummary()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Get group mappings
	countryGroups, err := h.groupingRepo.GetCountryGroups()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	industryGroups, err := h.groupingRepo.GetIndustryGroups()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Get saved group targets
	countryTargets, err := h.allocRepo.GetCountryGroupTargets()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	industryTargets, err := h.allocRepo.GetIndustryGroupTargets()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Calculate group allocations
	countryGroupAllocs, industryGroupAllocs := allocation.CalculateGroupAllocation(
		summary,
		countryGroups,
		industryGroups,
		countryTargets,
		industryTargets,
	)

	response := map[string]interface{}{
		"total_value":  summary.TotalValue,
		"cash_balance": summary.CashBalance,
		"country":      countryGroupAllocs,
		"industry":     industryGroupAllocs,
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetCurrentAllocation returns current allocation vs targets
// Faithful translation of Python: @router.get("/current")
func (h *Handler) HandleGetCurrentAllocation(w http.ResponseWriter, r *http.Request) {
	// Get portfolio summary
	summary, err := h.portfolioSummaryProvider.GetPortfolioSummary()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Detect concentration alerts
	alerts, err := h.alertService.DetectAlerts(summary)
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Build response matching Python structure
	response := map[string]interface{}{
		"total_value":  summary.TotalValue,
		"cash_balance": summary.CashBalance,
		"country":      buildAllocationArray(summary.CountryAllocations),
		"industry":     buildAllocationArray(summary.IndustryAllocations),
		"alerts":       buildAlertsArray(alerts),
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetDeviations returns allocation deviation scores
// Faithful translation of Python: @router.get("/deviations")
func (h *Handler) HandleGetDeviations(w http.ResponseWriter, r *http.Request) {
	// Get portfolio summary
	summary, err := h.portfolioSummaryProvider.GetPortfolioSummary()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Calculate deviations
	response := map[string]interface{}{
		"country":  calculateDeviationMap(summary.CountryAllocations),
		"industry": calculateDeviationMap(summary.IndustryAllocations),
	}

	h.writeJSON(w, http.StatusOK, response)
}

// Helper methods

// calculateDeviationMap converts allocations to deviation status map
func calculateDeviationMap(allocations []allocation.PortfolioAllocation) map[string]interface{} {
	result := make(map[string]interface{})

	for _, a := range allocations {
		status := "balanced"
		if a.Deviation < -0.02 {
			status = "underweight"
		} else if a.Deviation > 0.02 {
			status = "overweight"
		}

		result[a.Name] = map[string]interface{}{
			"deviation": a.Deviation,
			"need":      math.Max(0, -a.Deviation),
			"status":    status,
		}
	}

	return result
}

// buildAllocationArray converts PortfolioAllocation slice to response format
func buildAllocationArray(allocations []allocation.PortfolioAllocation) []map[string]interface{} {
	result := make([]map[string]interface{}, len(allocations))
	for i, a := range allocations {
		result[i] = map[string]interface{}{
			"name":          a.Name,
			"target_pct":    a.TargetPct,
			"current_pct":   a.CurrentPct,
			"current_value": a.CurrentValue,
			"deviation":     a.Deviation,
		}
	}
	return result
}

// buildAlertsArray converts ConcentrationAlert slice to response format
func buildAlertsArray(alerts []allocation.ConcentrationAlert) []map[string]interface{} {
	result := make([]map[string]interface{}, len(alerts))
	for i, alert := range alerts {
		result[i] = map[string]interface{}{
			"type":                alert.Type,
			"name":                alert.Name,
			"current_pct":         alert.CurrentPct,
			"limit_pct":           alert.LimitPct,
			"alert_threshold_pct": alert.AlertThresholdPct,
			"severity":            alert.Severity,
		}
	}
	return result
}

// HandleGetAllocationHistory handles GET /api/allocation/history
func (h *Handler) HandleGetAllocationHistory(w http.ResponseWriter, r *http.Request) {
	// Return 501 Not Implemented - requires time-series storage
	h.writeJSON(w, http.StatusNotImplemented, map[string]interface{}{
		"error": map[string]interface{}{
			"message": "Allocation history not yet implemented",
			"code":    "NOT_IMPLEMENTED",
			"details": map[string]string{
				"reason": "Requires time-series database integration for historical allocation snapshots",
			},
		},
	})
}

// HandleGetAllocationVsTargets handles GET /api/allocation/vs-targets
func (h *Handler) HandleGetAllocationVsTargets(w http.ResponseWriter, r *http.Request) {
	// Get portfolio summary
	summary, err := h.portfolioSummaryProvider.GetPortfolioSummary()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get portfolio summary")
		h.writeError(w, http.StatusInternalServerError, "Failed to get portfolio summary")
		return
	}

	// Combine country and industry allocations
	allocations := append(summary.CountryAllocations, summary.IndustryAllocations...)

	// Build detailed comparison - country allocations
	comparison := make([]map[string]interface{}, 0)
	var totalDeviation float64
	var overweightCount int
	var underweightCount int

	for _, alloc := range allocations {
		deviation := alloc.CurrentPct - alloc.TargetPct
		totalDeviation += abs(deviation)

		status := "on_target"
		if deviation > 1.0 {
			status = "overweight"
			overweightCount++
		} else if deviation < -1.0 {
			status = "underweight"
			underweightCount++
		}

		// Determine type based on which list this came from
		allocType := "country"
		if len(summary.CountryAllocations) > 0 && len(comparison) >= len(summary.CountryAllocations) {
			allocType = "industry"
		}

		comparison = append(comparison, map[string]interface{}{
			"group":        alloc.Name,
			"type":         allocType,
			"target_pct":   alloc.TargetPct,
			"current_pct":  alloc.CurrentPct,
			"deviation":    deviation,
			"status":       status,
			"current_value": alloc.CurrentValue,
		})
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"comparison":       comparison,
			"total_deviation":  totalDeviation,
			"overweight_count": overweightCount,
			"underweight_count": underweightCount,
			"on_target_count":  len(allocations) - overweightCount - underweightCount,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetRebalanceNeeds handles GET /api/allocation/rebalance-needs
func (h *Handler) HandleGetRebalanceNeeds(w http.ResponseWriter, r *http.Request) {
	// Get portfolio summary
	summary, err := h.portfolioSummaryProvider.GetPortfolioSummary()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get portfolio summary")
		h.writeError(w, http.StatusInternalServerError, "Failed to get portfolio summary")
		return
	}

	// Combine country and industry allocations
	allocations := append(summary.CountryAllocations, summary.IndustryAllocations...)

	// Calculate rebalancing needs
	rebalanceNeeds := make([]map[string]interface{}, 0)
	var totalRebalanceValue float64
	processed := 0

	for _, alloc := range allocations {
		deviation := alloc.CurrentPct - alloc.TargetPct

		// Only include groups that need rebalancing (>1% deviation)
		if abs(deviation) > 1.0 {
			// Calculate value needed to rebalance
			// Assumes total portfolio value from current_value and current_pct
			totalValue := 0.0
			if alloc.CurrentPct > 0 {
				totalValue = alloc.CurrentValue / (alloc.CurrentPct / 100.0)
			}
			targetValue := totalValue * (alloc.TargetPct / 100.0)
			valueChange := targetValue - alloc.CurrentValue

			totalRebalanceValue += abs(valueChange)

			// Determine type based on position in combined list
			allocType := "country"
			if len(summary.CountryAllocations) > 0 && processed >= len(summary.CountryAllocations) {
				allocType = "industry"
			}

			rebalanceNeeds = append(rebalanceNeeds, map[string]interface{}{
				"group":          alloc.Name,
				"type":           allocType,
				"current_value":  alloc.CurrentValue,
				"target_value":   targetValue,
				"value_change":   valueChange,
				"action":         getRebalanceAction(valueChange),
				"priority":       getPriority(abs(deviation)),
			})
		}
		processed++
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"rebalance_needs": rebalanceNeeds,
			"total_groups_needing_rebalance": len(rebalanceNeeds),
			"total_rebalance_value":          totalRebalanceValue,
			"note":                           "Rebalancing requires trading module integration",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetGroupContribution handles GET /api/allocation/groups/contribution
func (h *Handler) HandleGetGroupContribution(w http.ResponseWriter, r *http.Request) {
	// Get portfolio summary
	summary, err := h.portfolioSummaryProvider.GetPortfolioSummary()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get portfolio summary")
		h.writeError(w, http.StatusInternalServerError, "Failed to get portfolio summary")
		return
	}

	// Calculate diversification metrics by type
	geographicContribution := make(map[string]float64)
	industryContribution := make(map[string]float64)

	for _, alloc := range summary.CountryAllocations {
		geographicContribution[alloc.Name] = alloc.CurrentPct
	}
	for _, alloc := range summary.IndustryAllocations {
		industryContribution[alloc.Name] = alloc.CurrentPct
	}

	// Calculate Herfindahl-Hirschman Index for each type
	geographicHHI := calculateHHI(geographicContribution)
	industryHHI := calculateHHI(industryContribution)

	// Calculate effective number of groups (1/HHI)
	effectiveGeographicGroups := 1.0 / geographicHHI
	effectiveIndustryGroups := 1.0 / industryHHI

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"geographic": map[string]interface{}{
				"contributions":     geographicContribution,
				"hhi":               geographicHHI,
				"effective_groups":  effectiveGeographicGroups,
				"diversification_score": (1.0 - geographicHHI) * 100,
			},
			"industry": map[string]interface{}{
				"contributions":     industryContribution,
				"hhi":               industryHHI,
				"effective_groups":  effectiveIndustryGroups,
				"diversification_score": (1.0 - industryHHI) * 100,
			},
			"interpretation": map[string]string{
				"hhi":                 "Lower is more diversified (range: 0-1)",
				"effective_groups":    "Number of equally-weighted groups equivalent to current allocation",
				"diversification_score": "Higher is better (range: 0-100)",
			},
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// Helper functions

func abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}

func getRebalanceAction(valueChange float64) string {
	if valueChange > 0 {
		return "BUY"
	} else if valueChange < 0 {
		return "SELL"
	}
	return "HOLD"
}

func getPriority(deviation float64) string {
	if deviation >= 5.0 {
		return "high"
	} else if deviation >= 2.0 {
		return "medium"
	}
	return "low"
}

func calculateHHI(weights map[string]float64) float64 {
	var hhi float64
	for _, weight := range weights {
		// Convert percentage to decimal
		decimal := weight / 100.0
		hhi += decimal * decimal
	}
	return hhi
}

func (h *Handler) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
	}
}

func (h *Handler) writeError(w http.ResponseWriter, status int, message string) {
	h.writeJSON(w, status, map[string]string{"error": message})
}
