package portfolio

import (
	"encoding/json"
	"net/http"
	"sort"
	"strconv"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/rs/zerolog"
)

// Handler handles portfolio HTTP requests
// Faithful translation from Python: app/modules/portfolio/api/portfolio.py
type Handler struct {
	positionRepo            *PositionRepository
	portfolioRepo           *PortfolioRepository
	service                 *PortfolioService
	tradernetClient         *tradernet.Client
	currencyExchangeService CurrencyExchangeServiceInterface
	log                     zerolog.Logger
	pythonURL               string // URL of Python service for analytics endpoint
}

// NewHandler creates a new portfolio handler
func NewHandler(
	positionRepo *PositionRepository,
	portfolioRepo *PortfolioRepository,
	service *PortfolioService,
	tradernetClient *tradernet.Client,
	currencyExchangeService CurrencyExchangeServiceInterface,
	log zerolog.Logger,
	pythonURL string,
) *Handler {
	return &Handler{
		positionRepo:            positionRepo,
		portfolioRepo:           portfolioRepo,
		service:                 service,
		tradernetClient:         tradernetClient,
		currencyExchangeService: currencyExchangeService,
		log:                     log.With().Str("handler", "portfolio").Logger(),
		pythonURL:               pythonURL,
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
	result := make([]map[string]interface{}, 0, len(positions))
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
	result := make([]map[string]interface{}, 0, len(snapshots))
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

// HandleGetTransactions gets withdrawal transaction history from Tradernet microservice
// Faithful translation of Python: @router.get("/transactions")
func (h *Handler) HandleGetTransactions(w http.ResponseWriter, r *http.Request) {
	movements, err := h.tradernetClient.GetCashMovements()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, "Failed to get transaction history")
		return
	}

	response := map[string]interface{}{
		"total_withdrawals": movements.TotalWithdrawals,
		"withdrawals":       movements.Withdrawals,
		"note":              movements.Note,
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetCashBreakdown gets cash balance breakdown by currency from Tradernet microservice
// Faithful translation of Python: @router.get("/cash-breakdown")
func (h *Handler) HandleGetCashBreakdown(w http.ResponseWriter, r *http.Request) {
	balances, err := h.tradernetClient.GetCashBalances()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, "Failed to get cash breakdown")
		return
	}

	// Calculate total in EUR by converting all currencies
	// Matches Python implementation: exchange_rate_service.batch_convert_to_eur()
	var totalEUR float64
	for _, balance := range balances {
		if balance.Currency == "EUR" {
			totalEUR += balance.Amount
			h.log.Debug().
				Str("currency", "EUR").
				Float64("amount", balance.Amount).
				Msg("Added EUR balance")
		} else {
			// Convert non-EUR currency to EUR
			if h.currencyExchangeService != nil {
				rate, err := h.currencyExchangeService.GetRate(balance.Currency, "EUR")
				if err != nil {
					h.log.Warn().
						Err(err).
						Str("currency", balance.Currency).
						Float64("amount", balance.Amount).
						Msg("Failed to get exchange rate, using fallback")

					// Fallback rates for autonomous operation
					// These rates allow the system to continue operating when exchange
					// service is unavailable. Operator can review via logs.
					eurValue := balance.Amount
					switch balance.Currency {
					case "USD":
						eurValue = balance.Amount * 0.9
					case "GBP":
						eurValue = balance.Amount * 1.2
					case "HKD":
						eurValue = balance.Amount * 0.11
					default:
						h.log.Warn().
							Str("currency", balance.Currency).
							Msg("Unknown currency, assuming 1:1 with EUR")
					}
					totalEUR += eurValue

					h.log.Info().
						Str("currency", balance.Currency).
						Float64("amount", balance.Amount).
						Float64("eur_value", eurValue).
						Msg("Converted to EUR using fallback rate")
				} else {
					eurValue := balance.Amount * rate
					totalEUR += eurValue

					h.log.Debug().
						Str("currency", balance.Currency).
						Float64("rate", rate).
						Float64("amount", balance.Amount).
						Float64("eur_value", eurValue).
						Msg("Converted to EUR using live rate")
				}
			} else {
				// No exchange service available, use fallback rates
				eurValue := balance.Amount
				switch balance.Currency {
				case "USD":
					eurValue = balance.Amount * 0.9
				case "GBP":
					eurValue = balance.Amount * 1.2
				case "HKD":
					eurValue = balance.Amount * 0.11
				default:
					h.log.Warn().
						Str("currency", balance.Currency).
						Msg("Exchange service not available, assuming 1:1 with EUR")
				}
				totalEUR += eurValue
			}
		}
	}

	response := map[string]interface{}{
		"balances":  balances,
		"total_eur": totalEUR,
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetAnalytics calculates portfolio analytics
// Faithful translation of Python: @router.get("/analytics")
func (h *Handler) HandleGetAnalytics(w http.ResponseWriter, r *http.Request) {
	// Parse days parameter (default 365)
	days := 365
	if daysParam := r.URL.Query().Get("days"); daysParam != "" {
		if parsed, err := strconv.Atoi(daysParam); err == nil && parsed > 0 {
			days = parsed
		}
	}

	// Get analytics from service
	analytics, err := h.service.GetAnalytics(days)
	if err != nil {
		h.log.Error().Err(err).Int("days", days).Msg("Failed to calculate analytics")
		h.writeError(w, http.StatusInternalServerError, "Failed to calculate analytics")
		return
	}

	h.writeJSON(w, http.StatusOK, analytics)
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
