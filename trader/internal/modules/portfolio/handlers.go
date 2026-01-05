package portfolio

import (
	"encoding/json"
	"net/http"
	"sort"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/rs/zerolog"
)

// Handler handles portfolio HTTP requests
// Faithful translation from Python: app/modules/portfolio/api/portfolio.py
type Handler struct {
	positionRepo            *PositionRepository
	service                 *PortfolioService
	tradernetClient         *tradernet.Client
	currencyExchangeService CurrencyExchangeServiceInterface
	cashManager             CashManager
	log                     zerolog.Logger
}

// NewHandler creates a new portfolio handler
func NewHandler(
	positionRepo *PositionRepository,
	service *PortfolioService,
	tradernetClient *tradernet.Client,
	currencyExchangeService CurrencyExchangeServiceInterface,
	cashManager CashManager,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		positionRepo:            positionRepo,
		service:                 service,
		tradernetClient:         tradernetClient,
		currencyExchangeService: currencyExchangeService,
		cashManager:             cashManager,
		log:                     log.With().Str("handler", "portfolio").Logger(),
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

// HandleGetCashBreakdown gets cash balance breakdown by currency from CashManager
// Faithful translation of Python: @router.get("/cash-breakdown")
func (h *Handler) HandleGetCashBreakdown(w http.ResponseWriter, r *http.Request) {
	cashBalancesMap, err := h.cashManager.GetAllCashBalances()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, "Failed to get cash breakdown")
		return
	}

	// Convert map to slice format for response (matching Tradernet API format)
	balances := make([]map[string]interface{}, 0, len(cashBalancesMap))
	for currency, amount := range cashBalancesMap {
		balances = append(balances, map[string]interface{}{
			"currency": currency,
			"amount":   amount,
		})
	}

	// Calculate total in EUR by converting all currencies
	// Matches Python implementation: exchange_rate_service.batch_convert_to_eur()
	var totalEUR float64
	for currency, balance := range cashBalancesMap {
		if currency == "EUR" {
			totalEUR += balance
			h.log.Debug().
				Str("currency", "EUR").
				Float64("amount", balance).
				Msg("Added EUR balance")
		} else {
			// Convert non-EUR currency to EUR
			if h.currencyExchangeService != nil {
				rate, err := h.currencyExchangeService.GetRate(currency, "EUR")
				if err != nil {
					h.log.Warn().
						Err(err).
						Str("currency", currency).
						Float64("amount", balance).
						Msg("Failed to get exchange rate, using fallback")

					// Fallback rates for autonomous operation
					// These rates allow the system to continue operating when exchange
					// service is unavailable. Operator can review via logs.
					eurValue := balance
					switch currency {
					case "USD":
						eurValue = balance * 0.9
					case "GBP":
						eurValue = balance * 1.2
					case "HKD":
						eurValue = balance * 0.11
					default:
						h.log.Warn().
							Str("currency", currency).
							Msg("Unknown currency, assuming 1:1 with EUR")
					}
					totalEUR += eurValue

					h.log.Info().
						Str("currency", currency).
						Float64("amount", balance).
						Float64("eur_value", eurValue).
						Msg("Converted to EUR using fallback rate")
				} else {
					eurValue := balance * rate
					totalEUR += eurValue

					h.log.Debug().
						Str("currency", currency).
						Float64("rate", rate).
						Float64("amount", balance).
						Float64("eur_value", eurValue).
						Msg("Converted to EUR using live rate")
				}
			} else {
				// No exchange service available, use fallback rates
				eurValue := balance
				switch currency {
				case "USD":
					eurValue = balance * 0.9
				case "GBP":
					eurValue = balance * 1.2
				case "HKD":
					eurValue = balance * 0.11
				default:
					h.log.Warn().
						Str("currency", currency).
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
