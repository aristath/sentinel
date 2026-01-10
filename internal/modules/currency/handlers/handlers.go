// Package handlers provides HTTP handlers for currency operations.
package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/services"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
)

// Handler handles currency HTTP requests
type Handler struct {
	currencyService *services.CurrencyExchangeService
	cacheService    *services.ExchangeRateCacheService
	cashManager     domain.CashManager
	log             zerolog.Logger
}

// NewHandler creates a new currency handler
func NewHandler(
	currencyService *services.CurrencyExchangeService,
	cacheService *services.ExchangeRateCacheService,
	cashManager domain.CashManager,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		currencyService: currencyService,
		cacheService:    cacheService,
		cashManager:     cashManager,
		log:             log.With().Str("handler", "currency").Logger(),
	}
}

// ConvertRequest represents a request to convert currency
type ConvertRequest struct {
	FromCurrency string  `json:"from_currency"`
	ToCurrency   string  `json:"to_currency"`
	Amount       float64 `json:"amount"`
}

// BalanceCheckRequest represents a request to check balance sufficiency
type BalanceCheckRequest struct {
	Currency string  `json:"currency"`
	Amount   float64 `json:"amount"`
}

// ConversionRequirementsRequest represents a request to calculate conversion requirements
type ConversionRequirementsRequest struct {
	Symbol   string  `json:"symbol"`
	Side     string  `json:"side"`
	Quantity float64 `json:"quantity"`
	Price    float64 `json:"price"`
	Currency string  `json:"currency"`
}

// HandleGetConversionPath handles GET /api/currency/conversion-path/{from}/{to}
func (h *Handler) HandleGetConversionPath(w http.ResponseWriter, r *http.Request) {
	fromCurrency := chi.URLParam(r, "from")
	toCurrency := chi.URLParam(r, "to")

	if fromCurrency == "" || toCurrency == "" {
		http.Error(w, "from and to currencies are required", http.StatusBadRequest)
		return
	}

	path, err := h.currencyService.GetConversionPath(fromCurrency, toCurrency)
	if err != nil {
		h.log.Warn().Err(err).Str("from", fromCurrency).Str("to", toCurrency).Msg("Failed to get conversion path")
		response := map[string]interface{}{
			"data": map[string]interface{}{
				"path":  []interface{}{},
				"steps": 0,
				"note":  fmt.Sprintf("No conversion path available: %v", err),
			},
			"metadata": map[string]interface{}{
				"timestamp": time.Now().Format(time.RFC3339),
			},
		}
		h.writeJSON(w, http.StatusOK, response)
		return
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"from_currency": fromCurrency,
			"to_currency":   toCurrency,
			"path":          path,
			"steps":         len(path),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleConvert handles POST /api/currency/convert
func (h *Handler) HandleConvert(w http.ResponseWriter, r *http.Request) {
	var req ConvertRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request body")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if req.FromCurrency == "" || req.ToCurrency == "" {
		http.Error(w, "from_currency and to_currency are required", http.StatusBadRequest)
		return
	}

	if req.Amount <= 0 {
		http.Error(w, "amount must be greater than 0", http.StatusBadRequest)
		return
	}

	// Get exchange rate with panic recovery
	var rate float64
	var err error
	func() {
		defer func() {
			if r := recover(); r != nil {
				h.log.Warn().Interface("panic", r).Msg("Panic during rate fetch")
				err = fmt.Errorf("service dependencies not available")
			}
		}()
		rate, err = h.cacheService.GetRate(req.FromCurrency, req.ToCurrency)
	}()

	if err != nil {
		h.log.Warn().Err(err).Msg("Failed to get exchange rate")
		response := map[string]interface{}{
			"data": map[string]interface{}{
				"from_currency": req.FromCurrency,
				"to_currency":   req.ToCurrency,
				"from_amount":   req.Amount,
				"to_amount":     0,
				"rate":          0,
				"note":          "Exchange rate not available - requires rate service access",
			},
			"metadata": map[string]interface{}{
				"timestamp": time.Now().Format(time.RFC3339),
				"error":     err.Error(),
			},
		}
		h.writeJSON(w, http.StatusOK, response)
		return
	}

	convertedAmount := req.Amount * rate

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"from_currency": req.FromCurrency,
			"to_currency":   req.ToCurrency,
			"from_amount":   req.Amount,
			"to_amount":     convertedAmount,
			"rate":          rate,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetAvailableCurrencies handles GET /api/currency/available-currencies
func (h *Handler) HandleGetAvailableCurrencies(w http.ResponseWriter, r *http.Request) {
	// List of currencies supported by the system
	currencies := []map[string]interface{}{
		{"code": "EUR", "name": "Euro", "symbol": "€"},
		{"code": "USD", "name": "US Dollar", "symbol": "$"},
		{"code": "GBP", "name": "British Pound", "symbol": "£"},
		{"code": "HKD", "name": "Hong Kong Dollar", "symbol": "HK$"},
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"currencies": currencies,
			"count":      len(currencies),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetRateSources handles GET /api/currency/rates/sources
func (h *Handler) HandleGetRateSources(w http.ResponseWriter, r *http.Request) {
	sources := []map[string]interface{}{
		{
			"name":        "exchangerate-api",
			"priority":    1,
			"description": "Primary exchange rate API (fast, free, no auth)",
		},
		{
			"name":        "tradernet",
			"priority":    2,
			"description": "Broker FX instruments via Tradernet API",
		},
		{
			"name":        "yahoo",
			"priority":    3,
			"description": "Yahoo Finance exchange rates",
		},
		{
			"name":        "cache",
			"priority":    4,
			"description": "Cached rates from history database",
		},
		{
			"name":        "hardcoded",
			"priority":    5,
			"description": "Hardcoded fallback rates",
		},
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"sources": sources,
			"count":   len(sources),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetRateStaleness handles GET /api/currency/rates/staleness
func (h *Handler) HandleGetRateStaleness(w http.ResponseWriter, r *http.Request) {
	h.writeJSON(w, http.StatusNotImplemented, map[string]interface{}{
		"error": map[string]interface{}{
			"message": "Exchange rate staleness tracking not yet implemented as standalone API",
			"code":    "NOT_IMPLEMENTED",
			"details": map[string]string{
				"reason": "Requires time-series database access to track when each rate source was last updated",
				"note":   "This functionality requires database integration for historical rate tracking",
			},
		},
	})
}

// HandleGetFallbackChain handles GET /api/currency/rates/fallback-chain
func (h *Handler) HandleGetFallbackChain(w http.ResponseWriter, r *http.Request) {
	chain := []map[string]interface{}{
		{"order": 1, "source": "exchangerate-api", "condition": "always_try_first"},
		{"order": 2, "source": "tradernet", "condition": "if_exchangerate_api_fails"},
		{"order": 3, "source": "yahoo", "condition": "if_tradernet_fails"},
		{"order": 4, "source": "cache", "condition": "if_yahoo_fails"},
		{"order": 5, "source": "hardcoded", "condition": "if_all_else_fails"},
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"fallback_chain": chain,
			"total_tiers":    len(chain),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleSyncRates handles POST /api/currency/rates/sync
func (h *Handler) HandleSyncRates(w http.ResponseWriter, r *http.Request) {
	h.writeJSON(w, http.StatusNotImplemented, map[string]interface{}{
		"error": map[string]interface{}{
			"message": "Exchange rate synchronization not yet implemented as standalone API",
			"code":    "NOT_IMPLEMENTED",
			"details": map[string]string{
				"reason": "This is a write operation that modifies system state and requires background job integration",
				"note":   "Rate synchronization runs automatically via scheduled background jobs",
			},
		},
	})
}

// HandleGetBalances handles GET /api/currency/balances
func (h *Handler) HandleGetBalances(w http.ResponseWriter, r *http.Request) {
	if h.cashManager == nil {
		response := map[string]interface{}{
			"data": map[string]interface{}{
				"balances": map[string]float64{},
				"note":     "Cash manager not available",
			},
			"metadata": map[string]interface{}{
				"timestamp": time.Now().Format(time.RFC3339),
			},
		}
		h.writeJSON(w, http.StatusOK, response)
		return
	}

	balances, err := h.cashManager.GetAllCashBalances()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get cash balances")
		http.Error(w, "Failed to get cash balances", http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"balances": balances,
			"count":    len(balances),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleBalanceCheck handles POST /api/currency/balance-check
func (h *Handler) HandleBalanceCheck(w http.ResponseWriter, r *http.Request) {
	var req BalanceCheckRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request body")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if req.Currency == "" {
		http.Error(w, "currency is required", http.StatusBadRequest)
		return
	}

	if req.Amount <= 0 {
		http.Error(w, "amount must be greater than 0", http.StatusBadRequest)
		return
	}

	if h.cashManager == nil {
		response := map[string]interface{}{
			"data": map[string]interface{}{
				"currency":          req.Currency,
				"required_amount":   req.Amount,
				"available_balance": 0,
				"sufficient":        false,
				"note":              "Cash manager not available",
			},
			"metadata": map[string]interface{}{
				"timestamp": time.Now().Format(time.RFC3339),
			},
		}
		h.writeJSON(w, http.StatusOK, response)
		return
	}

	balance, err := h.cashManager.GetCashBalance(req.Currency)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get cash balance")
		http.Error(w, "Failed to get cash balance", http.StatusInternalServerError)
		return
	}

	sufficient := balance >= req.Amount
	shortfall := 0.0
	if !sufficient {
		shortfall = req.Amount - balance
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"currency":          req.Currency,
			"required_amount":   req.Amount,
			"available_balance": balance,
			"sufficient":        sufficient,
			"shortfall":         shortfall,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleConversionRequirements handles POST /api/currency/conversion-requirements
func (h *Handler) HandleConversionRequirements(w http.ResponseWriter, r *http.Request) {
	var req ConversionRequirementsRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request body")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if req.Currency == "" {
		req.Currency = "EUR" // Default to EUR
	}

	tradeValue := req.Quantity * req.Price
	commission := 2.0 + (tradeValue * 0.002) // €2 + 0.2%

	var totalRequired float64
	if req.Side == "BUY" {
		totalRequired = tradeValue + commission
	} else {
		totalRequired = 0 // SELL generates cash
	}

	// Check if conversion is needed from EUR
	needsConversion := req.Currency != "EUR"
	var conversionPath []interface{}
	if needsConversion {
		path, err := h.currencyService.GetConversionPath("EUR", req.Currency)
		if err == nil {
			conversionPath = make([]interface{}, len(path))
			for i, step := range path {
				conversionPath[i] = step
			}
		}
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"trade": map[string]interface{}{
				"symbol":      req.Symbol,
				"side":        req.Side,
				"quantity":    req.Quantity,
				"price":       req.Price,
				"currency":    req.Currency,
				"trade_value": tradeValue,
				"commission":  commission,
			},
			"requirements": map[string]interface{}{
				"total_required_in_currency": totalRequired,
				"needs_conversion":           needsConversion,
				"conversion_path":            conversionPath,
			},
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
