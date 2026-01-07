// Package handlers provides HTTP handlers for chart data.
package handlers

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/aristath/sentinel/internal/modules/charts"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
)

// Handler provides HTTP handlers for chart endpoints
type Handler struct {
	service *charts.Service
	log     zerolog.Logger
}

// NewHandler creates a new charts handler
func NewHandler(service *charts.Service, log zerolog.Logger) *Handler {
	return &Handler{
		service: service,
		log:     log.With().Str("handler", "charts").Logger(),
	}
}

// HandleGetSparklines handles GET /api/charts/sparklines
// Faithful translation from Python: app/api/charts.py -> get_all_stock_sparklines()
func (h *Handler) HandleGetSparklines(w http.ResponseWriter, r *http.Request) {
	sparklines, err := h.service.GetSparklines()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get sparklines data")
		http.Error(w, "Failed to get sparklines data", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(sparklines); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode sparklines response")
		http.Error(w, "Failed to encode response", http.StatusInternalServerError)
		return
	}
}

// HandleGetSecurityChart handles GET /api/charts/securities/{isin}
// Faithful translation from Python: app/api/charts.py -> get_security_chart()
func (h *Handler) HandleGetSecurityChart(w http.ResponseWriter, r *http.Request) {
	// Get ISIN from URL
	isin := chi.URLParam(r, "isin")
	if isin == "" {
		http.Error(w, "ISIN is required", http.StatusBadRequest)
		return
	}

	// Validate and normalize ISIN
	isin = strings.ToUpper(strings.TrimSpace(isin))
	if !IsValidISIN(isin) {
		http.Error(w, "Invalid ISIN format", http.StatusBadRequest)
		return
	}

	// Get query parameters
	dateRange := r.URL.Query().Get("range")
	if dateRange == "" {
		dateRange = "1Y"
	}

	// Get chart data
	chartData, err := h.service.GetSecurityChart(isin, dateRange)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			http.Error(w, "Security not found", http.StatusNotFound)
			return
		}
		h.log.Error().Err(err).Str("isin", isin).Msg("Failed to get security chart data")
		http.Error(w, "Failed to get security chart data", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(chartData); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode chart response")
		http.Error(w, "Failed to encode response", http.StatusInternalServerError)
		return
	}
}

// IsValidISIN performs basic ISIN validation
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> is_isin()
func IsValidISIN(isin string) bool {
	// ISIN must be exactly 12 characters
	if len(isin) != 12 {
		return false
	}

	// First two characters must be country code (letters)
	if !IsLetter(isin[0]) || !IsLetter(isin[1]) {
		return false
	}

	// Next 9 characters can be alphanumeric
	for i := 2; i < 11; i++ {
		if !IsAlphanumeric(isin[i]) {
			return false
		}
	}

	// Last character must be a digit (check digit)
	if !IsDigit(isin[11]) {
		return false
	}

	return true
}

func IsLetter(c byte) bool {
	return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')
}

func IsDigit(c byte) bool {
	return c >= '0' && c <= '9'
}

func IsAlphanumeric(c byte) bool {
	return IsLetter(c) || IsDigit(c)
}
