// Package handlers provides HTTP handlers for market hours operations.
package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"github.com/aristath/sentinel/internal/modules/market_hours"
	"github.com/rs/zerolog"
)

// Handler handles market hours HTTP requests
type Handler struct {
	service *market_hours.MarketHoursService
	log     zerolog.Logger
}

// NewHandler creates a new market hours handler
func NewHandler(
	service *market_hours.MarketHoursService,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		service: service,
		log:     log.With().Str("handler", "market_hours").Logger(),
	}
}

// HandleGetStatus handles GET /api/market-hours/status
// Returns current market status for all configured exchanges
func (h *Handler) HandleGetStatus(w http.ResponseWriter, r *http.Request) {
	now := time.Now()

	// Get all exchange codes
	exchangeCodes := getAllExchangeCodes()

	markets := make([]map[string]interface{}, 0, len(exchangeCodes))
	for _, code := range exchangeCodes {
		status, err := h.service.GetMarketStatus(code, now)
		if err != nil {
			h.log.Warn().Err(err).Str("exchange", code).Msg("Failed to get market status")
			continue
		}

		marketData := map[string]interface{}{
			"exchange": status.Exchange,
			"open":     status.Open,
			"timezone": status.Timezone,
		}

		if status.Open {
			marketData["closes_at"] = status.ClosesAt
		} else {
			if status.OpensAt != "" {
				marketData["opens_at"] = status.OpensAt
			}
			if status.OpensDate != "" {
				marketData["opens_date"] = status.OpensDate
			}
		}

		markets = append(markets, marketData)
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"timestamp": now.Format(time.RFC3339),
			"markets":   markets,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetStatusByExchange handles GET /api/market-hours/status/{exchange}
// Returns current market status for a specific exchange
func (h *Handler) HandleGetStatusByExchange(w http.ResponseWriter, r *http.Request, exchange string) {
	now := time.Now()

	status, err := h.service.GetMarketStatus(exchange, now)
	if err != nil {
		h.log.Error().Err(err).Str("exchange", exchange).Msg("Failed to get market status")
		http.Error(w, "Failed to get market status", http.StatusInternalServerError)
		return
	}

	data := map[string]interface{}{
		"exchange": status.Exchange,
		"open":     status.Open,
		"timezone": status.Timezone,
	}

	if status.Open {
		data["closes_at"] = status.ClosesAt
	} else {
		if status.OpensAt != "" {
			data["opens_at"] = status.OpensAt
		}
		if status.OpensDate != "" {
			data["opens_date"] = status.OpensDate
		}
	}

	response := map[string]interface{}{
		"data": data,
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetOpenMarkets handles GET /api/market-hours/open-markets
// Returns list of currently open exchanges
func (h *Handler) HandleGetOpenMarkets(w http.ResponseWriter, r *http.Request) {
	now := time.Now()

	openMarkets := h.service.GetOpenMarkets(now)

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"timestamp":    now.Format(time.RFC3339),
			"open_markets": openMarkets,
			"count":        len(openMarkets),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetHolidays handles GET /api/market-hours/holidays
// Returns upcoming market holidays
func (h *Handler) HandleGetHolidays(w http.ResponseWriter, r *http.Request) {
	// Get year from query param, default to current year
	year := time.Now().Year()
	if yearStr := r.URL.Query().Get("year"); yearStr != "" {
		if parsedYear, err := strconv.Atoi(yearStr); err == nil && parsedYear > 0 {
			year = parsedYear
		}
	}

	// Get exchange from query param, default to all exchanges
	exchange := r.URL.Query().Get("exchange")

	exchangesToCheck := []string{}
	if exchange != "" {
		exchangesToCheck = []string{exchange}
	} else {
		exchangesToCheck = getAllExchangeCodes()
	}

	holidaysByExchange := make(map[string][]string)

	for _, code := range exchangesToCheck {
		holidays := getHolidaysForExchange(h.service, code, year)
		if len(holidays) > 0 {
			holidaysByExchange[code] = holidays
		}
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"year":     year,
			"holidays": holidaysByExchange,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleValidateTradingWindow handles GET /api/market-hours/validate-trading-window
// Checks if a symbol can be traded now
func (h *Handler) HandleValidateTradingWindow(w http.ResponseWriter, r *http.Request) {
	// Get query parameters
	symbol := r.URL.Query().Get("symbol")
	side := r.URL.Query().Get("side")
	exchange := r.URL.Query().Get("exchange")

	// Validate required parameters
	if symbol == "" {
		http.Error(w, "symbol parameter is required", http.StatusBadRequest)
		return
	}
	if side == "" {
		http.Error(w, "side parameter is required", http.StatusBadRequest)
		return
	}

	// Default exchange if not provided
	if exchange == "" {
		exchange = "XNYS"
	}

	now := time.Now()

	// Check if market is open
	isOpen := h.service.IsMarketOpen(exchange, now)

	// Check if market hours validation is required for this trade
	shouldCheck := h.service.ShouldCheckMarketHours(exchange, side)

	// Determine if trade can proceed
	canTrade := !shouldCheck || isOpen

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"symbol":                symbol,
			"side":                  side,
			"exchange":              exchange,
			"can_trade":             canTrade,
			"market_open":           isOpen,
			"requires_market_hours": shouldCheck,
			"checked_at":            now.Format(time.RFC3339),
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

// getAllExchangeCodes returns all configured exchange codes
func getAllExchangeCodes() []string {
	// All exchange codes from market_hours/exchanges.go
	return []string{
		"XNYS", // New York
		"XNAS", // NASDAQ
		"XETR", // Frankfurt/XETRA
		"XLON", // London
		"XPAR", // Paris
		"XAMS", // Amsterdam
		"XMIL", // Milan
		"XCSE", // Copenhagen
		"ASEX", // Athens
		"XHKG", // Hong Kong
		"XSHG", // Shanghai/Shenzhen
		"XTSE", // Tokyo
		"XASX", // Sydney
	}
}

// getHolidaysForExchange returns holidays for a specific exchange and year
func getHolidaysForExchange(service *market_hours.MarketHoursService, exchangeCode string, year int) []string {
	// This is a helper that would need to access the service's internal holiday calculation
	// For now, return empty slice - this can be enhanced when we expose holiday data from the service
	return []string{}
}
