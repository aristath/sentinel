package trading

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"

	"github.com/rs/zerolog"
)

// SecurityFetcher provides security information for trades
type SecurityFetcher interface {
	GetSecurityName(symbol string) (string, error)
}

// TradingHandlers contains HTTP handlers for trading API
type TradingHandlers struct {
	tradeRepo       *TradeRepository
	securityFetcher SecurityFetcher
	pythonURL       string
	log             zerolog.Logger
}

// NewTradingHandlers creates a new trading handlers instance
func NewTradingHandlers(
	tradeRepo *TradeRepository,
	securityFetcher SecurityFetcher,
	pythonURL string,
	log zerolog.Logger,
) *TradingHandlers {
	return &TradingHandlers{
		tradeRepo:       tradeRepo,
		securityFetcher: securityFetcher,
		pythonURL:       pythonURL,
		log:             log.With().Str("handler", "trading").Logger(),
	}
}

// HandleGetTrades returns trade history
// Faithful translation from Python: @router.get("")
// GET /api/trades
func (h *TradingHandlers) HandleGetTrades(w http.ResponseWriter, r *http.Request) {
	// Parse limit parameter
	limit := 50
	if limitParam := r.URL.Query().Get("limit"); limitParam != "" {
		if parsed, err := strconv.Atoi(limitParam); err == nil {
			limit = parsed
		}
	}

	// Get trade history
	trades, err := h.tradeRepo.GetHistory(limit)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get trade history")
		http.Error(w, "Failed to get trade history", http.StatusInternalServerError)
		return
	}

	// Build symbol to name mapping for securities
	// Faithful translation from Python API
	stockNames := make(map[string]string)
	for _, trade := range trades {
		if !isCurrencyConversion(trade.Symbol) {
			if _, exists := stockNames[trade.Symbol]; !exists {
				if h.securityFetcher != nil {
					name, err := h.securityFetcher.GetSecurityName(trade.Symbol)
					if err == nil && name != "" {
						stockNames[trade.Symbol] = name
					} else {
						stockNames[trade.Symbol] = trade.Symbol
					}
				} else {
					stockNames[trade.Symbol] = trade.Symbol
				}
			}
		}
	}

	// Convert to response format
	response := make([]map[string]interface{}, 0, len(trades))
	for _, t := range trades {
		var name string
		if isCurrencyConversion(t.Symbol) {
			name = getCurrencyConversionName(t.Symbol)
		} else {
			name = stockNames[t.Symbol]
		}

		response = append(response, map[string]interface{}{
			"id":          t.ID,
			"symbol":      t.Symbol,
			"name":        name,
			"side":        string(t.Side),
			"quantity":    t.Quantity,
			"price":       t.Price,
			"executed_at": t.ExecutedAt.Format("2006-01-02T15:04:05Z07:00"),
			"order_id":    t.OrderID,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(response) // Ignore encode error - already committed response
}

// HandleExecuteTrade proxies trade execution to Python
// POST /api/trades/execute
func (h *TradingHandlers) HandleExecuteTrade(w http.ResponseWriter, r *http.Request) {
	// Proxy to Python - requires Tradernet SDK
	h.proxyToPython(w, r, "/api/trades/execute")
}

// HandleGetAllocation proxies allocation request to Python
// GET /api/trades/allocation
func (h *TradingHandlers) HandleGetAllocation(w http.ResponseWriter, r *http.Request) {
	// Proxy to Python - uses portfolio service and concentration alert service
	h.proxyToPython(w, r, "/api/trades/allocation")
}

// Helper methods

// isCurrencyConversion checks if symbol is a currency conversion pair
func isCurrencyConversion(symbol string) bool {
	return strings.Contains(symbol, "/") && len(strings.Split(symbol, "/")) == 2
}

// getCurrencyConversionName gets display name for currency conversion
func getCurrencyConversionName(symbol string) string {
	parts := strings.Split(symbol, "/")
	if len(parts) == 2 {
		return fmt.Sprintf("%s → %s", parts[0], parts[1])
	}
	return symbol
}

// proxyToPython forwards the request to the Python service
func (h *TradingHandlers) proxyToPython(w http.ResponseWriter, r *http.Request, path string) {
	url := h.pythonURL + path

	// Read request body if present
	var body []byte
	var err error
	if r.Body != nil {
		body, err = io.ReadAll(r.Body)
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to read request body")
			http.Error(w, "Failed to read request body", http.StatusInternalServerError)
			return
		}
	}

	// Create new request with same method and body
	req, err := http.NewRequest(r.Method, url, bytes.NewReader(body))
	if err != nil {
		h.log.Error().Err(err).Str("url", url).Msg("Failed to create proxy request")
		http.Error(w, "Failed to create proxy request", http.StatusInternalServerError)
		return
	}

	// Copy headers
	req.Header.Set("Content-Type", "application/json")
	for key, values := range r.Header {
		for _, value := range values {
			req.Header.Add(key, value)
		}
	}

	// Execute request
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		h.log.Error().Err(err).Str("url", url).Msg("Failed to contact Python service")
		http.Error(w, "Failed to contact Python service", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	// Read response body
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to read Python response")
		http.Error(w, "Failed to read Python response", http.StatusInternalServerError)
		return
	}

	// Copy response headers
	for key, values := range resp.Header {
		for _, value := range values {
			w.Header().Add(key, value)
		}
	}

	// Write response
	w.WriteHeader(resp.StatusCode)
	_, _ = w.Write(respBody) // Ignore write error - already committed response
}
