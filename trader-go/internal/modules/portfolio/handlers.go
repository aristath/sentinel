package portfolio

import (
	"encoding/json"
	"net/http"
	"sort"
	"strconv"

	"github.com/rs/zerolog"
)

// Handler handles portfolio HTTP requests
// Faithful translation from Python: app/modules/portfolio/api/portfolio.py
type Handler struct {
	positionRepo  *PositionRepository
	portfolioRepo *PortfolioRepository
	service       *PortfolioService
	log           zerolog.Logger
	pythonURL     string // URL of Python service for proxied endpoints
}

// NewHandler creates a new portfolio handler
func NewHandler(
	positionRepo *PositionRepository,
	portfolioRepo *PortfolioRepository,
	service *PortfolioService,
	log zerolog.Logger,
	pythonURL string,
) *Handler {
	return &Handler{
		positionRepo:  positionRepo,
		portfolioRepo: portfolioRepo,
		service:       service,
		log:           log.With().Str("handler", "portfolio").Logger(),
		pythonURL:     pythonURL,
	}
}

// HandleGetPortfolio returns current portfolio positions with values
// Faithful translation of Python: @router.get("", response_model=List[PortfolioPosition])
func (h *Handler) HandleGetPortfolio(w http.ResponseWriter, r *http.Request) {
	positions, err := h.positionRepo.GetWithSecurityInfo()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Convert to response format
	var result []map[string]interface{}
	for _, pos := range positions {
		result = append(result, map[string]interface{}{
			"symbol":           pos.Symbol,
			"quantity":         pos.Quantity,
			"avg_price":        pos.AvgPrice,
			"current_price":    pos.CurrentPrice,
			"currency":         pos.Currency,
			"currency_rate":    pos.CurrencyRate,
			"market_value_eur": pos.MarketValueEUR,
			"last_updated":     pos.LastUpdated,
			"stock_name":       pos.StockName,
			"industry":         pos.Industry,
			"country":          pos.Country,
			"fullExchangeName": pos.FullExchangeName,
		})
	}

	// Sort by market value (descending)
	sort.Slice(result, func(i, j int) bool {
		valI := result[i]["market_value_eur"].(float64)
		valJ := result[j]["market_value_eur"].(float64)
		return valI > valJ
	})

	h.writeJSON(w, http.StatusOK, result)
}

// HandleGetSummary returns portfolio summary
// Faithful translation of Python: @router.get("/summary")
func (h *Handler) HandleGetSummary(w http.ResponseWriter, r *http.Request) {
	summary, err := h.service.GetPortfolioSummary()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Calculate country percentages (hardcoded for EU, ASIA, US like Python)
	countryDict := make(map[string]float64)
	for _, alloc := range summary.CountryAllocations {
		countryDict[alloc.Name] = alloc.CurrentPct
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"total_value":  summary.TotalValue,
		"cash_balance": summary.CashBalance,
		"allocations": map[string]interface{}{
			"EU":   countryDict["EU"] * 100,
			"ASIA": countryDict["ASIA"] * 100,
			"US":   countryDict["US"] * 100,
		},
	})
}

// HandleGetHistory returns historical portfolio snapshots
// Faithful translation of Python: @router.get("/history")
func (h *Handler) HandleGetHistory(w http.ResponseWriter, r *http.Request) {
	// Default to 90 days
	days := 90
	if daysParam := r.URL.Query().Get("days"); daysParam != "" {
		if parsed, err := strconv.Atoi(daysParam); err == nil {
			days = parsed
		}
	}

	snapshots, err := h.portfolioRepo.GetHistory(days)
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Convert to response format
	var result []map[string]interface{}
	for _, s := range snapshots {
		result = append(result, map[string]interface{}{
			"id":           nil, // Not in domain model
			"date":         s.Date,
			"total_value":  s.TotalValue,
			"cash_balance": s.CashBalance,
			"geo_eu_pct":   s.GeoEUPct,
			"geo_asia_pct": s.GeoAsiaPct,
			"geo_us_pct":   s.GeoUSPct,
		})
	}

	h.writeJSON(w, http.StatusOK, result)
}

// HandleGetTransactions proxies to Python for Tradernet transaction history
// Faithful translation of Python: @router.get("/transactions")
func (h *Handler) HandleGetTransactions(w http.ResponseWriter, r *http.Request) {
	// TODO: Proxy to Python service (requires Tradernet SDK)
	h.proxyToPython(w, r, "/api/portfolio/transactions")
}

// HandleGetCashBreakdown proxies to Python for cash breakdown by currency
// Faithful translation of Python: @router.get("/cash-breakdown")
func (h *Handler) HandleGetCashBreakdown(w http.ResponseWriter, r *http.Request) {
	// TODO: Proxy to Python service (requires Tradernet SDK)
	h.proxyToPython(w, r, "/api/portfolio/cash-breakdown")
}

// HandleGetAnalytics proxies to Python for portfolio analytics
// Faithful translation of Python: @router.get("/analytics")
func (h *Handler) HandleGetAnalytics(w http.ResponseWriter, r *http.Request) {
	// TODO: Proxy to Python service (requires analytics module - pandas/numpy/PyFolio)
	h.proxyToPython(w, r, "/api/portfolio/analytics"+r.URL.RawQuery)
}

// Helper methods

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

func (h *Handler) proxyToPython(w http.ResponseWriter, r *http.Request, path string) {
	// Simple proxy to Python service during migration
	url := h.pythonURL + path

	resp, err := http.Get(url)
	if err != nil {
		h.writeError(w, http.StatusBadGateway, "Failed to contact Python service")
		return
	}
	defer resp.Body.Close()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.StatusCode)

	var result interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		h.writeError(w, http.StatusInternalServerError, "Failed to decode Python response")
		return
	}

	json.NewEncoder(w).Encode(result)
}
