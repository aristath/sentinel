package portfolio

import (
	"database/sql"
	"encoding/json"
	"fmt"
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
	configDB                *sql.DB
	log                     zerolog.Logger
}

// NewHandler creates a new portfolio handler
func NewHandler(
	positionRepo *PositionRepository,
	service *PortfolioService,
	tradernetClient *tradernet.Client,
	currencyExchangeService CurrencyExchangeServiceInterface,
	cashManager CashManager,
	configDB *sql.DB,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		positionRepo:            positionRepo,
		service:                 service,
		tradernetClient:         tradernetClient,
		currencyExchangeService: currencyExchangeService,
		cashManager:             cashManager,
		configDB:                configDB,
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

	// Add virtual test cash if in research mode
	if err := h.addVirtualTestCash(cashBalancesMap); err != nil {
		h.log.Warn().Err(err).Msg("Failed to add virtual test cash to cash breakdown, continuing without it")
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

// addVirtualTestCash adds virtual test cash to cash balances if in research mode
// TEST currency is added to cashBalances map, and also added to EUR for AvailableCashEUR calculation
// This matches the implementation in scheduler/planner_batch.go and rebalancing/service.go
func (h *Handler) addVirtualTestCash(cashBalances map[string]float64) error {
	if h.configDB == nil {
		return nil // No config DB available, skip
	}

	// Check trading mode - only add test cash in research mode
	var tradingMode string
	err := h.configDB.QueryRow("SELECT value FROM settings WHERE key = 'trading_mode'").Scan(&tradingMode)
	if err != nil {
		if err == sql.ErrNoRows {
			// Default to research mode if not set
			tradingMode = "research"
		} else {
			return fmt.Errorf("failed to get trading mode: %w", err)
		}
	}

	// Only add test cash in research mode
	if tradingMode != "research" {
		return nil
	}

	// Get virtual_test_cash setting
	var virtualTestCashStr string
	err = h.configDB.QueryRow("SELECT value FROM settings WHERE key = 'virtual_test_cash'").Scan(&virtualTestCashStr)
	if err != nil {
		if err == sql.ErrNoRows {
			// No virtual test cash set, that's fine
			return nil
		}
		return fmt.Errorf("failed to get virtual_test_cash: %w", err)
	}

	// Parse virtual test cash amount
	var virtualTestCash float64
	_, err = fmt.Sscanf(virtualTestCashStr, "%f", &virtualTestCash)
	if err != nil {
		return fmt.Errorf("failed to parse virtual_test_cash: %w", err)
	}

	// Only add if > 0
	if virtualTestCash > 0 {
		// Add TEST currency to cashBalances
		cashBalances["TEST"] = virtualTestCash

		// Also add to EUR for AvailableCashEUR calculation (TEST is treated as EUR-equivalent)
		// Get current EUR balance (default to 0 if not present)
		currentEUR := cashBalances["EUR"]
		cashBalances["EUR"] = currentEUR + virtualTestCash

		h.log.Info().
			Float64("virtual_test_cash", virtualTestCash).
			Float64("eur_before", currentEUR).
			Float64("eur_after", cashBalances["EUR"]).
			Str("trading_mode", tradingMode).
			Msg("Added virtual test cash to cash breakdown")
	}

	return nil
}
