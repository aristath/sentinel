// Package handlers provides HTTP handlers for portfolio management.
package handlers

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"time"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/rs/zerolog"
)

// Handler handles portfolio HTTP requests
// Faithful translation from Python: app/modules/portfolio/api/portfolio.py
type Handler struct {
	positionRepo            *portfolio.PositionRepository
	service                 *portfolio.PortfolioService
	brokerClient            domain.BrokerClient
	currencyExchangeService domain.CurrencyExchangeServiceInterface
	cashManager             domain.CashManager
	configDB                *sql.DB
	log                     zerolog.Logger
}

// NewHandler creates a new portfolio handler
func NewHandler(
	positionRepo *portfolio.PositionRepository,
	service *portfolio.PortfolioService,
	brokerClient domain.BrokerClient,
	currencyExchangeService domain.CurrencyExchangeServiceInterface,
	cashManager domain.CashManager,
	configDB *sql.DB,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		positionRepo:            positionRepo,
		service:                 service,
		brokerClient:            brokerClient,
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
		// Convert Unix timestamp to RFC3339 string for API
		var lastUpdatedStr string
		if pos.LastUpdated != nil {
			t := time.Unix(*pos.LastUpdated, 0).UTC()
			lastUpdatedStr = t.Format(time.RFC3339)
		}

		result = append(result, map[string]interface{}{
			"symbol":           pos.Symbol,
			"quantity":         pos.Quantity,
			"avg_price":        pos.AvgPrice,
			"current_price":    pos.CurrentPrice,
			"currency":         pos.Currency,
			"currency_rate":    pos.CurrencyRate,
			"market_value_eur": pos.MarketValueEUR,
			"last_updated":     lastUpdatedStr,
			"stock_name":       pos.StockName,
			"industry":         pos.Industry,
			"country":          pos.Country,
			"fullExchangeName": pos.FullExchangeName,
		})
	}

	// Sort by market value (descending)
	sort.Slice(result, func(i, j int) bool {
		valI, okI := result[i]["market_value_eur"].(float64)
		valJ, okJ := result[j]["market_value_eur"].(float64)
		if !okI || !okJ {
			h.log.Error().Msg("Invalid market value type in position during sort")
			return false // Keep original order for invalid entries
		}
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
	movements, err := h.brokerClient.GetCashMovements()
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
	h.log.Debug().Bool("configDB_nil", h.configDB == nil).Msg("About to add virtual test cash")
	if err := h.addVirtualTestCash(cashBalancesMap); err != nil {
		h.log.Warn().Err(err).Msg("Failed to add virtual test cash to cash breakdown, continuing without it")
	} else {
		h.log.Debug().Int("currencies_count", len(cashBalancesMap)).Msg("After addVirtualTestCash")
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

// HandleGetPerformanceHistory handles GET /api/portfolio/performance/history
func (h *Handler) HandleGetPerformanceHistory(w http.ResponseWriter, r *http.Request) {
	period := r.URL.Query().Get("period")
	if period == "" {
		period = "1M" // Default to 1 month
	}

	// Get current positions to calculate returns
	positions, err := h.positionRepo.GetWithSecurityInfo()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Calculate unrealized P&L for current positions
	var totalGainLoss float64
	var totalCost float64
	for _, pos := range positions {
		costBasis := pos.AvgPrice * pos.Quantity * pos.CurrencyRate
		marketValue := pos.MarketValueEUR
		totalCost += costBasis
		totalGainLoss += (marketValue - costBasis)
	}

	returnPct := 0.0
	if totalCost > 0 {
		returnPct = (totalGainLoss / totalCost) * 100
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"period":             period,
			"total_return_pct":   returnPct,
			"total_gain_loss":    totalGainLoss,
			"total_cost_basis":   totalCost,
			"current_value":      totalCost + totalGainLoss,
			"note":               "Historical performance tracking requires time-series data",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetPerformanceVsBenchmark handles GET /api/portfolio/performance/vs-benchmark
func (h *Handler) HandleGetPerformanceVsBenchmark(w http.ResponseWriter, r *http.Request) {
	benchmark := r.URL.Query().Get("benchmark")
	if benchmark == "" {
		benchmark = "^STOXX50E" // Default to Euro Stoxx 50
	}

	// Get current positions
	positions, err := h.positionRepo.GetWithSecurityInfo()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Calculate portfolio return
	var totalGainLoss float64
	var totalCost float64
	for _, pos := range positions {
		costBasis := pos.AvgPrice * pos.Quantity * pos.CurrencyRate
		marketValue := pos.MarketValueEUR
		totalCost += costBasis
		totalGainLoss += (marketValue - costBasis)
	}

	portfolioReturn := 0.0
	if totalCost > 0 {
		portfolioReturn = (totalGainLoss / totalCost) * 100
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"benchmark":         benchmark,
			"portfolio_return":  portfolioReturn,
			"benchmark_return":  0.0, // Placeholder - requires market data
			"alpha":             portfolioReturn,
			"note":              "Benchmark comparison requires historical market data integration",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetPerformanceAttribution handles GET /api/portfolio/performance/attribution
func (h *Handler) HandleGetPerformanceAttribution(w http.ResponseWriter, r *http.Request) {
	// Get current positions
	positions, err := h.positionRepo.GetWithSecurityInfo()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Attribution by security
	securityAttribution := make([]map[string]interface{}, 0, len(positions))
	var totalPortfolioReturn float64
	var totalValue float64

	for _, pos := range positions {
		costBasis := pos.AvgPrice * pos.Quantity * pos.CurrencyRate
		marketValue := pos.MarketValueEUR
		gainLoss := marketValue - costBasis
		returnPct := 0.0
		if costBasis > 0 {
			returnPct = (gainLoss / costBasis) * 100
		}

		contribution := gainLoss
		totalPortfolioReturn += contribution
		totalValue += marketValue

		securityAttribution = append(securityAttribution, map[string]interface{}{
			"symbol":             pos.Symbol,
			"name":               pos.StockName,
			"return_pct":         returnPct,
			"contribution":       contribution,
			"weight":             marketValue,
		})
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"total_return":       totalPortfolioReturn,
			"total_value":        totalValue,
			"security_attribution": securityAttribution,
			"note":               "Full attribution requires factor model integration",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetConcentration handles GET /api/portfolio/concentration
func (h *Handler) HandleGetConcentration(w http.ResponseWriter, r *http.Request) {
	// Get current positions
	positions, err := h.positionRepo.GetWithSecurityInfo()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Calculate total portfolio value
	var totalValue float64
	weights := make([]float64, 0, len(positions))
	for _, pos := range positions {
		totalValue += pos.MarketValueEUR
	}

	// Calculate concentration metrics
	var herfindahlIndex float64
	var top5Weight float64
	var top10Weight float64

	// Calculate weights
	for _, pos := range positions {
		weight := pos.MarketValueEUR / totalValue
		weights = append(weights, weight)
		herfindahlIndex += weight * weight
	}

	// Sort weights descending
	sort.Float64s(weights)
	for i, j := 0, len(weights)-1; i < j; i, j = i+1, j-1 {
		weights[i], weights[j] = weights[j], weights[i]
	}

	// Calculate top N concentrations
	for i, weight := range weights {
		if i < 5 {
			top5Weight += weight
		}
		if i < 10 {
			top10Weight += weight
		}
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"herfindahl_index": herfindahlIndex,
			"top_5_weight":     top5Weight * 100,
			"top_10_weight":    top10Weight * 100,
			"num_positions":    len(positions),
			"interpretation": map[string]string{
				"herfindahl": "Lower is more diversified (1/N is perfectly equal)",
				"top_n":      "Percentage of portfolio in top N positions",
			},
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetDiversification handles GET /api/portfolio/diversification
func (h *Handler) HandleGetDiversification(w http.ResponseWriter, r *http.Request) {
	// Get current positions
	positions, err := h.positionRepo.GetWithSecurityInfo()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Calculate diversification by country and industry
	countryWeights := make(map[string]float64)
	industryWeights := make(map[string]float64)
	var totalValue float64

	for _, pos := range positions {
		totalValue += pos.MarketValueEUR
	}

	for _, pos := range positions {
		weight := pos.MarketValueEUR / totalValue

		if pos.Country != "" {
			countryWeights[pos.Country] += weight
		}
		if pos.Industry != "" {
			industryWeights[pos.Industry] += weight
		}
	}

	// Calculate Herfindahl-Hirschman Index for each dimension
	var countryHHI float64
	for _, weight := range countryWeights {
		countryHHI += weight * weight
	}

	var industryHHI float64
	for _, weight := range industryWeights {
		industryHHI += weight * weight
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"geographic": map[string]interface{}{
				"num_countries": len(countryWeights),
				"hhi":           countryHHI,
				"weights":       countryWeights,
			},
			"industry": map[string]interface{}{
				"num_industries": len(industryWeights),
				"hhi":            industryHHI,
				"weights":        industryWeights,
			},
			"interpretation": "Lower HHI indicates better diversification",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetUnrealizedPnLBreakdown handles GET /api/portfolio/unrealized-pnl/breakdown
func (h *Handler) HandleGetUnrealizedPnLBreakdown(w http.ResponseWriter, r *http.Request) {
	// Get current positions
	positions, err := h.positionRepo.GetWithSecurityInfo()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Calculate P&L by security
	securityPnL := make([]map[string]interface{}, 0, len(positions))
	countryPnL := make(map[string]float64)
	industryPnL := make(map[string]float64)
	var totalPnL float64

	for _, pos := range positions {
		costBasis := pos.AvgPrice * pos.Quantity * pos.CurrencyRate
		marketValue := pos.MarketValueEUR
		pnl := marketValue - costBasis
		pnlPct := 0.0
		if costBasis > 0 {
			pnlPct = (pnl / costBasis) * 100
		}

		totalPnL += pnl

		securityPnL = append(securityPnL, map[string]interface{}{
			"symbol":   pos.Symbol,
			"name":     pos.StockName,
			"pnl":      pnl,
			"pnl_pct":  pnlPct,
			"country":  pos.Country,
			"industry": pos.Industry,
		})

		if pos.Country != "" {
			countryPnL[pos.Country] += pnl
		}
		if pos.Industry != "" {
			industryPnL[pos.Industry] += pnl
		}
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"total_pnl":    totalPnL,
			"by_security":  securityPnL,
			"by_country":   countryPnL,
			"by_industry":  industryPnL,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetCostBasis handles GET /api/portfolio/cost-basis
func (h *Handler) HandleGetCostBasis(w http.ResponseWriter, r *http.Request) {
	// Get current positions
	positions, err := h.positionRepo.GetWithSecurityInfo()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Calculate cost basis analysis by security
	costBasisAnalysis := make([]map[string]interface{}, 0, len(positions))
	var totalCost float64
	var totalValue float64

	for _, pos := range positions {
		costBasis := pos.AvgPrice * pos.Quantity * pos.CurrencyRate
		marketValue := pos.MarketValueEUR
		unrealizedGain := marketValue - costBasis
		unrealizedGainPct := 0.0
		if costBasis > 0 {
			unrealizedGainPct = (unrealizedGain / costBasis) * 100
		}

		totalCost += costBasis
		totalValue += marketValue

		costBasisAnalysis = append(costBasisAnalysis, map[string]interface{}{
			"symbol":             pos.Symbol,
			"name":               pos.StockName,
			"quantity":           pos.Quantity,
			"avg_price":          pos.AvgPrice,
			"currency":           pos.Currency,
			"cost_basis_eur":     costBasis,
			"market_value_eur":   marketValue,
			"unrealized_gain":    unrealizedGain,
			"unrealized_gain_pct": unrealizedGainPct,
		})
	}

	totalGain := totalValue - totalCost
	totalGainPct := 0.0
	if totalCost > 0 {
		totalGainPct = (totalGain / totalCost) * 100
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"total_cost_basis":   totalCost,
			"total_market_value": totalValue,
			"total_unrealized_gain": totalGain,
			"total_unrealized_gain_pct": totalGainPct,
			"by_security":        costBasisAnalysis,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
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
		h.log.Debug().Msg("configDB is nil, skipping virtual test cash")
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
	var virtualTestCash float64
	err = h.configDB.QueryRow("SELECT value FROM settings WHERE key = 'virtual_test_cash'").Scan(&virtualTestCashStr)
	if err != nil {
		if err == sql.ErrNoRows {
			// No virtual test cash set, default to 0 so it can be edited in UI
			virtualTestCash = 0
		} else {
			return fmt.Errorf("failed to get virtual_test_cash: %w", err)
		}
	} else {
		// Parse virtual test cash amount
		_, err = fmt.Sscanf(virtualTestCashStr, "%f", &virtualTestCash)
		if err != nil {
			return fmt.Errorf("failed to parse virtual_test_cash: %w", err)
		}
	}

	// Always add TEST currency to cashBalances, even if 0 (so it can be edited in UI)
	cashBalances["TEST"] = virtualTestCash

	// Also add to EUR for AvailableCashEUR calculation (TEST is treated as EUR-equivalent)
	// Only add to EUR if > 0 to avoid reducing EUR balance when TEST is 0
	if virtualTestCash > 0 {
		// Get current EUR balance (default to 0 if not present)
		currentEUR := cashBalances["EUR"]
		cashBalances["EUR"] = currentEUR + virtualTestCash

		h.log.Info().
			Float64("virtual_test_cash", virtualTestCash).
			Float64("eur_before", currentEUR).
			Float64("eur_after", cashBalances["EUR"]).
			Str("trading_mode", tradingMode).
			Msg("Added virtual test cash to cash breakdown")
	} else {
		h.log.Debug().
			Float64("virtual_test_cash", virtualTestCash).
			Str("trading_mode", tradingMode).
			Msg("Added virtual test cash (0) to cash breakdown for UI editing")
	}

	return nil
}
