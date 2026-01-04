package dividends

import (
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
)

// DividendHandlers contains HTTP handlers for dividend API
// Faithful translation of dividend repository operations to HTTP endpoints
type DividendHandlers struct {
	repo *DividendRepository
	log  zerolog.Logger
}

// NewDividendHandlers creates a new dividend handlers instance
func NewDividendHandlers(repo *DividendRepository, log zerolog.Logger) *DividendHandlers {
	return &DividendHandlers{
		repo: repo,
		log:  log.With().Str("handler", "dividends").Logger(),
	}
}

// HandleGetDividends returns all dividend records
// GET /api/dividends?limit=N
func (h *DividendHandlers) HandleGetDividends(w http.ResponseWriter, r *http.Request) {
	// Parse limit parameter
	limit := 100
	if limitParam := r.URL.Query().Get("limit"); limitParam != "" {
		if parsed, err := strconv.Atoi(limitParam); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	dividends, err := h.repo.GetAll(limit)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get dividends")
		http.Error(w, "Failed to get dividends", http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, dividends)
}

// HandleGetDividendByID returns a single dividend by ID
// GET /api/dividends/{id}
func (h *DividendHandlers) HandleGetDividendByID(w http.ResponseWriter, r *http.Request) {
	idStr := chi.URLParam(r, "id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		http.Error(w, "Invalid dividend ID", http.StatusBadRequest)
		return
	}

	dividend, err := h.repo.GetByID(id)
	if err != nil {
		h.log.Error().Err(err).Int("id", id).Msg("Failed to get dividend")
		http.Error(w, "Failed to get dividend", http.StatusInternalServerError)
		return
	}

	if dividend == nil {
		http.Error(w, "Dividend not found", http.StatusNotFound)
		return
	}

	h.writeJSON(w, dividend)
}

// HandleGetDividendsBySymbol returns dividends for a specific symbol
// GET /api/dividends/symbol/{symbol}
func (h *DividendHandlers) HandleGetDividendsBySymbol(w http.ResponseWriter, r *http.Request) {
	symbol := chi.URLParam(r, "symbol")

	dividends, err := h.repo.GetBySymbol(symbol)
	if err != nil {
		h.log.Error().Err(err).Str("symbol", symbol).Msg("Failed to get dividends by symbol")
		http.Error(w, "Failed to get dividends", http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, dividends)
}

// HandleGetUnreinvestedDividends returns unreinvested dividends
// GET /api/dividends/unreinvested?min_amount_eur=X
// CRITICAL: Used by dividend_reinvestment.py job
func (h *DividendHandlers) HandleGetUnreinvestedDividends(w http.ResponseWriter, r *http.Request) {
	// Parse min_amount_eur parameter
	minAmount := 0.0
	if minAmountParam := r.URL.Query().Get("min_amount_eur"); minAmountParam != "" {
		if parsed, err := strconv.ParseFloat(minAmountParam, 64); err == nil {
			minAmount = parsed
		}
	}

	dividends, err := h.repo.GetUnreinvestedDividends(minAmount)
	if err != nil {
		h.log.Error().Err(err).Float64("min_amount", minAmount).Msg("Failed to get unreinvested dividends")
		http.Error(w, "Failed to get unreinvested dividends", http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, dividends)
}

// HandleGetPendingBonuses returns all pending bonuses
// GET /api/dividends/pending-bonuses
func (h *DividendHandlers) HandleGetPendingBonuses(w http.ResponseWriter, r *http.Request) {
	bonuses, err := h.repo.GetPendingBonuses()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get pending bonuses")
		http.Error(w, "Failed to get pending bonuses", http.StatusInternalServerError)
		return
	}

	// Convert to API response format
	type BonusResponse struct {
		Symbol       string  `json:"symbol"`
		PendingBonus float64 `json:"pending_bonus"`
	}

	response := make([]BonusResponse, 0, len(bonuses))
	for symbol, amount := range bonuses {
		response = append(response, BonusResponse{
			Symbol:       symbol,
			PendingBonus: amount,
		})
	}

	h.writeJSON(w, response)
}

// HandleCreateDividend creates a new dividend record
// POST /api/dividends
func (h *DividendHandlers) HandleCreateDividend(w http.ResponseWriter, r *http.Request) {
	var dividend DividendRecord
	if err := json.NewDecoder(r.Body).Decode(&dividend); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode dividend")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validate dividend
	if err := dividend.Validate(); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	// Set created_at if not provided
	now := time.Now()
	if dividend.CreatedAt == nil {
		dividend.CreatedAt = &now
	}

	// Create dividend (ID will be set on the record)
	if err := h.repo.Create(&dividend); err != nil {
		h.log.Error().Err(err).Msg("Failed to create dividend")
		http.Error(w, "Failed to create dividend", http.StatusInternalServerError)
		return
	}

	// Return created dividend with ID
	w.WriteHeader(http.StatusCreated)
	h.writeJSON(w, dividend)
}

// SetPendingBonusRequest is the request body for setting pending bonus
type SetPendingBonusRequest struct {
	Amount float64 `json:"amount"`
}

// HandleSetPendingBonus sets pending bonus for a dividend
// POST /api/dividends/{id}/pending-bonus
// CRITICAL: Used by dividend_reinvestment.py job
func (h *DividendHandlers) HandleSetPendingBonus(w http.ResponseWriter, r *http.Request) {
	idStr := chi.URLParam(r, "id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		http.Error(w, "Invalid dividend ID", http.StatusBadRequest)
		return
	}

	var req SetPendingBonusRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if req.Amount < 0 {
		http.Error(w, "Amount cannot be negative", http.StatusBadRequest)
		return
	}

	if err := h.repo.SetPendingBonus(id, req.Amount); err != nil {
		h.log.Error().Err(err).Int("id", id).Float64("amount", req.Amount).Msg("Failed to set pending bonus")
		http.Error(w, "Failed to set pending bonus", http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// MarkReinvestedRequest is the request body for marking dividend as reinvested
type MarkReinvestedRequest struct {
	Quantity int `json:"quantity"`
}

// HandleMarkReinvested marks a dividend as reinvested
// POST /api/dividends/{id}/mark-reinvested
// CRITICAL: Used by dividend_reinvestment.py job
func (h *DividendHandlers) HandleMarkReinvested(w http.ResponseWriter, r *http.Request) {
	idStr := chi.URLParam(r, "id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		http.Error(w, "Invalid dividend ID", http.StatusBadRequest)
		return
	}

	var req MarkReinvestedRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if req.Quantity <= 0 {
		http.Error(w, "Quantity must be positive", http.StatusBadRequest)
		return
	}

	if err := h.repo.MarkReinvested(id, req.Quantity); err != nil {
		h.log.Error().Err(err).Int("id", id).Int("quantity", req.Quantity).Msg("Failed to mark dividend as reinvested")
		http.Error(w, "Failed to mark dividend as reinvested", http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// HandleClearBonus clears pending bonus for a symbol
// POST /api/dividends/clear-bonus/{symbol}
func (h *DividendHandlers) HandleClearBonus(w http.ResponseWriter, r *http.Request) {
	symbol := chi.URLParam(r, "symbol")

	rowsAffected, err := h.repo.ClearBonus(symbol)
	if err != nil {
		h.log.Error().Err(err).Str("symbol", symbol).Msg("Failed to clear bonus")
		http.Error(w, "Failed to clear bonus", http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]interface{}{
		"symbol":        symbol,
		"rows_affected": rowsAffected,
	})
}

// HandleGetTotalDividendsBySymbol returns total dividends for all symbols
// GET /api/dividends/analytics/total
func (h *DividendHandlers) HandleGetTotalDividendsBySymbol(w http.ResponseWriter, r *http.Request) {
	totals, err := h.repo.GetTotalDividendsBySymbol()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get total dividends")
		http.Error(w, "Failed to get total dividends", http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, totals)
}

// HandleGetReinvestmentRate returns overall reinvestment rate
// GET /api/dividends/analytics/reinvestment-rate
func (h *DividendHandlers) HandleGetReinvestmentRate(w http.ResponseWriter, r *http.Request) {
	rate, err := h.repo.GetReinvestmentRate()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get reinvestment rate")
		http.Error(w, "Failed to get reinvestment rate", http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]interface{}{
		"rate": rate,
	})
}

// writeJSON writes JSON response
func (h *DividendHandlers) writeJSON(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
	}
}
