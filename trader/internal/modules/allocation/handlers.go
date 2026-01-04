package allocation

import (
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
)

// Handler handles allocation HTTP requests
// Faithful translation from Python: app/modules/allocation/api/allocation.py
type Handler struct {
	allocRepo                *Repository
	groupingRepo             *GroupingRepository
	alertService             *ConcentrationAlertService
	portfolioSummaryProvider PortfolioSummaryProvider
	log                      zerolog.Logger
	pythonURL                string // URL of Python service (temporary during migration)
}

// NewHandler creates a new allocation handler
func NewHandler(
	allocRepo *Repository,
	groupingRepo *GroupingRepository,
	alertService *ConcentrationAlertService,
	portfolioSummaryProvider PortfolioSummaryProvider,
	log zerolog.Logger,
	pythonURL string,
) *Handler {
	return &Handler{
		allocRepo:                allocRepo,
		groupingRepo:             groupingRepo,
		alertService:             alertService,
		portfolioSummaryProvider: portfolioSummaryProvider,
		log:                      log.With().Str("handler", "allocation").Logger(),
		pythonURL:                pythonURL,
	}
}

// HandleGetTargets returns allocation targets for country and industry groups
// Faithful translation of Python: @router.get("/targets")
func (h *Handler) HandleGetTargets(w http.ResponseWriter, r *http.Request) {
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

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"country":  countryTargets,
		"industry": industryTargets,
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
	var req CountryGroup
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
	var req IndustryGroup
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
		if groupWeight < -1 || groupWeight > 1 {
			h.writeError(w, http.StatusBadRequest, fmt.Sprintf("Weight for %s must be between -1 and 1", groupName))
			return
		}

		target := AllocationTarget{
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
		if groupWeight < -1 || groupWeight > 1 {
			h.writeError(w, http.StatusBadRequest, fmt.Sprintf("Weight for %s must be between -1 and 1", groupName))
			return
		}

		target := AllocationTarget{
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
	countryGroupAllocs, industryGroupAllocs := CalculateGroupAllocation(
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
func calculateDeviationMap(allocations []PortfolioAllocation) map[string]interface{} {
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
func buildAllocationArray(allocations []PortfolioAllocation) []map[string]interface{} {
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
func buildAlertsArray(alerts []ConcentrationAlert) []map[string]interface{} {
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
