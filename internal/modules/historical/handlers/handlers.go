// Package handlers provides HTTP handlers for historical data operations.
package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// Handler handles historical data HTTP requests
type Handler struct {
	historyDB *universe.HistoryDB
	log       zerolog.Logger
}

// NewHandler creates a new historical data handler
func NewHandler(
	historyDB *universe.HistoryDB,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		historyDB: historyDB,
		log:       log.With().Str("handler", "historical").Logger(),
	}
}

// HandleGetDailyPrices handles GET /api/historical/prices/daily/{isin}
func (h *Handler) HandleGetDailyPrices(w http.ResponseWriter, r *http.Request, isin string) {
	// Parse query parameters
	limit := 100 // default
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		if parsedLimit, err := strconv.Atoi(limitStr); err == nil && parsedLimit > 0 {
			limit = parsedLimit
		}
	}

	prices, err := h.historyDB.GetDailyPrices(isin, limit)
	if err != nil {
		h.log.Error().Err(err).Str("isin", isin).Msg("Failed to get daily prices")
		http.Error(w, "Failed to get daily prices", http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"isin":   isin,
			"prices": prices,
			"count":  len(prices),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetMonthlyPrices handles GET /api/historical/prices/monthly/{isin}
func (h *Handler) HandleGetMonthlyPrices(w http.ResponseWriter, r *http.Request, isin string) {
	limit := 120 // default: 10 years
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		if parsedLimit, err := strconv.Atoi(limitStr); err == nil && parsedLimit > 0 {
			limit = parsedLimit
		}
	}

	prices, err := h.historyDB.GetMonthlyPrices(isin, limit)
	if err != nil {
		h.log.Error().Err(err).Str("isin", isin).Msg("Failed to get monthly prices")
		http.Error(w, "Failed to get monthly prices", http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"isin":   isin,
			"prices": prices,
			"count":  len(prices),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetLatestPrice handles GET /api/historical/prices/latest/{isin}
func (h *Handler) HandleGetLatestPrice(w http.ResponseWriter, r *http.Request, isin string) {
	prices, err := h.historyDB.GetDailyPrices(isin, 1)
	if err != nil {
		h.log.Error().Err(err).Str("isin", isin).Msg("Failed to get latest price")
		http.Error(w, "Failed to get latest price", http.StatusInternalServerError)
		return
	}

	var latestPrice interface{}
	if len(prices) > 0 {
		latestPrice = prices[0]
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"isin":  isin,
			"price": latestPrice,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetPriceRange handles GET /api/historical/prices/range
func (h *Handler) HandleGetPriceRange(w http.ResponseWriter, r *http.Request) {
	// Get ISINs from query parameter
	isinsStr := r.URL.Query().Get("isins")
	if isinsStr == "" {
		http.Error(w, "isins parameter is required", http.StatusBadRequest)
		return
	}

	isins := strings.Split(isinsStr, ",")
	limit := 100
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		if parsedLimit, err := strconv.Atoi(limitStr); err == nil && parsedLimit > 0 {
			limit = parsedLimit
		}
	}

	pricesByISIN := make(map[string]interface{})
	for _, isin := range isins {
		isin = strings.TrimSpace(isin)
		if isin == "" {
			continue
		}

		prices, err := h.historyDB.GetDailyPrices(isin, limit)
		if err != nil {
			h.log.Warn().Err(err).Str("isin", isin).Msg("Failed to get prices for ISIN")
			continue
		}

		pricesByISIN[isin] = prices
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"prices": pricesByISIN,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetDailyReturns handles GET /api/historical/returns/daily/{isin}
func (h *Handler) HandleGetDailyReturns(w http.ResponseWriter, r *http.Request, isin string) {
	limit := 100
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		if parsedLimit, err := strconv.Atoi(limitStr); err == nil && parsedLimit > 0 {
			limit = parsedLimit
		}
	}

	prices, err := h.historyDB.GetDailyPrices(isin, limit+1) // Need one extra for return calculation
	if err != nil {
		h.log.Error().Err(err).Str("isin", isin).Msg("Failed to get daily prices")
		http.Error(w, "Failed to get daily prices", http.StatusInternalServerError)
		return
	}

	// Calculate returns
	returns := calculateReturns(prices)

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"isin":    isin,
			"returns": returns,
			"count":   len(returns),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetMonthlyReturns handles GET /api/historical/returns/monthly/{isin}
func (h *Handler) HandleGetMonthlyReturns(w http.ResponseWriter, r *http.Request, isin string) {
	limit := 120
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		if parsedLimit, err := strconv.Atoi(limitStr); err == nil && parsedLimit > 0 {
			limit = parsedLimit
		}
	}

	prices, err := h.historyDB.GetMonthlyPrices(isin, limit+1)
	if err != nil {
		h.log.Error().Err(err).Str("isin", isin).Msg("Failed to get monthly prices")
		http.Error(w, "Failed to get monthly prices", http.StatusInternalServerError)
		return
	}

	// Calculate returns from monthly prices
	returns := make([]map[string]interface{}, 0)
	for i := 0; i < len(prices)-1; i++ {
		currentPrice := prices[i].AvgAdjClose
		previousPrice := prices[i+1].AvgAdjClose

		if previousPrice > 0 {
			returnPct := ((currentPrice - previousPrice) / previousPrice) * 100
			returns = append(returns, map[string]interface{}{
				"period": prices[i].YearMonth,
				"return": returnPct,
			})
		}
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"isin":    isin,
			"returns": returns,
			"count":   len(returns),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetCorrelationMatrix handles GET /api/historical/returns/correlation-matrix
func (h *Handler) HandleGetCorrelationMatrix(w http.ResponseWriter, r *http.Request) {
	// Get ISINs from query parameter (optional - if not provided, return empty)
	isinsStr := r.URL.Query().Get("isins")

	var isins []string
	if isinsStr != "" {
		isins = strings.Split(isinsStr, ",")
	}

	// For now, return placeholder structure
	// Full implementation would calculate correlation matrix using formulas package
	correlationMatrix := make(map[string]map[string]float64)

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"correlation_matrix": correlationMatrix,
			"isins":              isins,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetExchangeRateHistory handles GET /api/historical/exchange-rates/history
func (h *Handler) HandleGetExchangeRateHistory(w http.ResponseWriter, r *http.Request) {
	fromCurrency := r.URL.Query().Get("from_currency")
	toCurrency := r.URL.Query().Get("to_currency")

	if fromCurrency == "" {
		http.Error(w, "from_currency parameter is required", http.StatusBadRequest)
		return
	}
	if toCurrency == "" {
		http.Error(w, "to_currency parameter is required", http.StatusBadRequest)
		return
	}

	// Get latest rate (history DB only stores latest)
	rate, err := h.historyDB.GetLatestExchangeRate(fromCurrency, toCurrency)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get exchange rate")
		http.Error(w, "Failed to get exchange rate", http.StatusInternalServerError)
		return
	}

	var rateData interface{}
	if rate != nil {
		rateData = map[string]interface{}{
			"from_currency": rate.FromCurrency,
			"to_currency":   rate.ToCurrency,
			"rate":          rate.Rate,
			"date":          rate.Date.Format("2006-01-02"),
		}
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"rate": rateData,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetCurrentExchangeRates handles GET /api/historical/exchange-rates/current
func (h *Handler) HandleGetCurrentExchangeRates(w http.ResponseWriter, r *http.Request) {
	// Return placeholder - would need to query all currency pairs
	rates := make(map[string]interface{})

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"rates": rates,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetExchangeRate handles GET /api/historical/exchange-rates/{from}/{to}
func (h *Handler) HandleGetExchangeRate(w http.ResponseWriter, r *http.Request, from, to string) {
	rate, err := h.historyDB.GetLatestExchangeRate(from, to)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get exchange rate")
		http.Error(w, "Failed to get exchange rate", http.StatusInternalServerError)
		return
	}

	var rateData interface{}
	if rate != nil {
		rateData = map[string]interface{}{
			"from_currency": rate.FromCurrency,
			"to_currency":   rate.ToCurrency,
			"rate":          rate.Rate,
			"date":          rate.Date.Format("2006-01-02"),
		}
	}

	response := map[string]interface{}{
		"data": rateData,
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

// calculateReturns calculates percentage returns from price series
func calculateReturns(prices []universe.DailyPrice) []map[string]interface{} {
	returns := make([]map[string]interface{}, 0)

	for i := 0; i < len(prices)-1; i++ {
		currentPrice := prices[i].Close
		previousPrice := prices[i+1].Close

		if previousPrice > 0 {
			returnPct := ((currentPrice - previousPrice) / previousPrice) * 100
			returns = append(returns, map[string]interface{}{
				"date":   prices[i].Date,
				"return": returnPct,
			})
		}
	}

	return returns
}
