// Package handlers provides HTTP handlers for trade execution.
package handlers

import (
	"github.com/aristath/sentinel/internal/modules/trading"
)

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/events"
	"github.com/aristath/sentinel/internal/modules/allocation"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/settings"
	"github.com/rs/zerolog"
)

// SecurityFetcher provides security information for trades
type SecurityFetcher interface {
	GetSecurityName(symbol string) (string, error)
}

// PlannerRepositoryInterface defines the interface for planner repository
type PlannerRepositoryInterface interface {
	CountEvaluations(portfolioHash string) (int, error)
}

// TradingHandlers contains HTTP handlers for trading API
type TradingHandlers struct {
	log                        zerolog.Logger
	securityFetcher            SecurityFetcher
	tradeRepo                  *trading.TradeRepository
	portfolioService           *portfolio.PortfolioService
	concentrationAlertProvider allocation.ConcentrationAlertProvider
	brokerClient               domain.BrokerClient
	safetyService              *trading.TradeSafetyService
	settingsService            *settings.Service
	recommendationRepo         RecommendationRepositoryInterface
	plannerRepo                PlannerRepositoryInterface
	eventManager               *events.Manager
}

// RecommendationRepositoryInterface defines the interface for recommendation repository
type RecommendationRepositoryInterface interface {
	GetRecommendationsAsPlan(getEvaluatedCount func(portfolioHash string) (int, error), startingCashEUR float64) (map[string]interface{}, error)
}

// NewTradingHandlers creates a new trading handlers instance
func NewTradingHandlers(
	tradeRepo *trading.TradeRepository,
	securityFetcher SecurityFetcher,
	portfolioService *portfolio.PortfolioService,
	concentrationAlertProvider allocation.ConcentrationAlertProvider,
	brokerClient domain.BrokerClient,
	safetyService *trading.TradeSafetyService,
	settingsService *settings.Service,
	recommendationRepo RecommendationRepositoryInterface,
	plannerRepo PlannerRepositoryInterface,
	eventManager *events.Manager,
	log zerolog.Logger,
) *TradingHandlers {
	return &TradingHandlers{
		tradeRepo:                  tradeRepo,
		securityFetcher:            securityFetcher,
		portfolioService:           portfolioService,
		concentrationAlertProvider: concentrationAlertProvider,
		brokerClient:               brokerClient,
		safetyService:              safetyService,
		settingsService:            settingsService,
		recommendationRepo:         recommendationRepo,
		plannerRepo:                plannerRepo,
		eventManager:               eventManager,
		log:                        log.With().Str("handler", "trading").Logger(),
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

// HandleExecuteTrade executes a trade via Tradernet microservice
// POST /api/trades/execute
func (h *TradingHandlers) HandleExecuteTrade(w http.ResponseWriter, r *http.Request) {
	// Parse request body
	var req struct {
		Symbol   string  `json:"symbol"`
		Side     string  `json:"side"`
		Quantity float64 `json:"quantity"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// Check trading mode - block real trades in research mode
	tradingMode, err := h.settingsService.GetTradingMode()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get trading mode")
		h.writeError(w, http.StatusInternalServerError, "Failed to get trading mode")
		return
	}

	if tradingMode == "research" {
		h.log.Warn().
			Str("symbol", req.Symbol).
			Str("side", req.Side).
			Float64("quantity", req.Quantity).
			Msg("Trade blocked - system in research mode")
		h.writeError(w, http.StatusForbidden, "Trading is disabled in research mode")
		return
	}

	// SAFETY LAYER: Validate trade before execution
	if h.safetyService != nil {
		if err := h.safetyService.ValidateTrade(req.Symbol, req.Side, req.Quantity); err != nil {
			h.log.Warn().
				Err(err).
				Str("symbol", req.Symbol).
				Str("side", req.Side).
				Float64("quantity", req.Quantity).
				Msg("Trade validation failed")
			h.writeError(w, http.StatusBadRequest, fmt.Sprintf("Trade validation failed: %v", err))
			return
		}
	}

	// Execute trade via Tradernet microservice
	// Manual trading uses market orders (limitPrice = 0.0) for immediate execution
	result, err := h.brokerClient.PlaceOrder(req.Symbol, req.Side, req.Quantity, 0.0)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to place order")
		h.writeError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to place order: %v", err))
		return
	}

	// Record trade in database
	if err := h.recordTrade(req.Symbol, req.Side, req.Quantity, result, tradingMode); err != nil {
		h.log.Error().Err(err).Msg("Failed to record trade")
		// Don't fail the request - trade already executed
	} else {
		// Emit TRADE_EXECUTED event
		if h.eventManager != nil {
			h.eventManager.Emit(events.TradeExecuted, "trading", map[string]interface{}{
				"symbol":   result.Symbol,
				"side":     result.Side,
				"quantity": result.Quantity,
				"price":    result.Price,
				"order_id": result.OrderID,
			})
		}
	}

	// Return success response matching Python format
	response := map[string]interface{}{
		"status":   "success",
		"order_id": result.OrderID,
		"symbol":   result.Symbol,
		"side":     result.Side,
		"quantity": result.Quantity,
		"price":    result.Price,
	}

	h.writeJSON(w, http.StatusOK, response)
}

// recordTrade records a trade in the database after execution
// Faithful translation from Python: app/modules/trading/services/trade_execution/trade_recorder.py -> record_trade()
func (h *TradingHandlers) recordTrade(
	symbol string,
	side string,
	quantity float64,
	result *domain.BrokerOrderResult,
	tradingMode string,
) error {
	now := time.Now()

	trade := trading.Trade{
		Symbol:     symbol,
		Side:       trading.TradeSide(strings.ToUpper(side)),
		Quantity:   quantity,
		Price:      result.Price,
		ExecutedAt: now,
		OrderID:    result.OrderID,
		Source:     "manual",
		Mode:       tradingMode,
		CreatedAt:  &now,
	}

	if err := h.tradeRepo.Create(trade); err != nil {
		return fmt.Errorf("failed to create trade record: %w", err)
	}

	h.log.Info().
		Str("symbol", symbol).
		Str("order_id", result.OrderID).
		Float64("price", result.Price).
		Msg("Trade recorded successfully")

	return nil
}

// HandleGetAllocation returns current portfolio allocation vs targets
// Faithful translation from Python: @router.get("/allocation")
// GET /api/trades/allocation
func (h *TradingHandlers) HandleGetAllocation(w http.ResponseWriter, r *http.Request) {
	// Get portfolio summary
	portfolioSummary, err := h.portfolioService.GetPortfolioSummary()
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Convert to allocation types for alert service
	summary := convertPortfolioSummary(portfolioSummary)

	// Detect concentration alerts
	alerts, err := h.concentrationAlertProvider.DetectAlerts(summary)
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Build response matching Python structure
	response := map[string]interface{}{
		"total_value":  summary.TotalValue,
		"cash_balance": summary.CashBalance,
		"country":      buildAllocationArray(summary.CountryAllocations),
		"industry":     buildAllocationArray(summary.IndustryAllocations),
		"alerts":       buildAlertsArray(alerts),
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetRecommendations returns current trade recommendations
// GET /api/trades/recommendations
func (h *TradingHandlers) HandleGetRecommendations(w http.ResponseWriter, r *http.Request) {
	if h.recommendationRepo == nil {
		h.log.Warn().Msg("Recommendation repository not available")
		h.writeJSON(w, http.StatusOK, map[string]interface{}{
			"steps": []interface{}{},
		})
		return
	}

	// Create function to get evaluated count if planner repository is available
	var getEvaluatedCount func(portfolioHash string) (int, error)
	if h.plannerRepo != nil {
		getEvaluatedCount = func(portfolioHash string) (int, error) {
			return h.plannerRepo.CountEvaluations(portfolioHash)
		}
	}

	// Get current cash balance (EUR) to calculate per-step cash values
	// Includes virtual test cash if in research mode
	startingCashEUR := 0.0
	if h.portfolioService != nil {
		summary, err := h.portfolioService.GetPortfolioSummary()
		if err != nil {
			h.log.Warn().
				Err(err).
				Msg("Failed to get portfolio summary for cash balance, using 0")
		} else {
			startingCashEUR = summary.CashBalance
			h.log.Debug().
				Float64("cash_balance", startingCashEUR).
				Msg("Retrieved starting cash balance from portfolio")
		}
	} else {
		h.log.Warn().Msg("Portfolio service not available, starting cash will be 0")
	}

	// Add virtual test cash if in research mode (matches how BuildOpportunityContext handles it)
	if h.settingsService != nil {
		tradingMode, err := h.settingsService.GetTradingMode()
		if err == nil && tradingMode == "research" {
			virtualTestCashVal, err := h.settingsService.Get("virtual_test_cash")
			if err == nil {
				if virtualTestCash, ok := virtualTestCashVal.(float64); ok && virtualTestCash > 0 {
					startingCashEUR += virtualTestCash
					h.log.Debug().
						Float64("virtual_test_cash", virtualTestCash).
						Float64("total_starting_cash", startingCashEUR).
						Msg("Added virtual test cash to starting cash balance")
				}
			}
		}
	}

	plan, err := h.recommendationRepo.GetRecommendationsAsPlan(getEvaluatedCount, startingCashEUR)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get recommendations")
		h.writeError(w, http.StatusInternalServerError, "Failed to get recommendations")
		return
	}

	h.writeJSON(w, http.StatusOK, plan)
}

// Helper methods

// convertPortfolioSummary converts portfolio.PortfolioSummary to allocation.PortfolioSummary
func convertPortfolioSummary(src portfolio.PortfolioSummary) allocation.PortfolioSummary {
	return allocation.PortfolioSummary{
		CountryAllocations:  convertAllocations(src.CountryAllocations),
		IndustryAllocations: convertAllocations(src.IndustryAllocations),
		TotalValue:          src.TotalValue,
		CashBalance:         src.CashBalance,
	}
}

// convertAllocations converts []portfolio.AllocationStatus to []allocation.PortfolioAllocation
func convertAllocations(src []portfolio.AllocationStatus) []allocation.PortfolioAllocation {
	result := make([]allocation.PortfolioAllocation, len(src))
	for i, a := range src {
		result[i] = allocation.PortfolioAllocation{
			Name:         a.Name,
			TargetPct:    a.TargetPct,
			CurrentPct:   a.CurrentPct,
			CurrentValue: a.CurrentValue,
			Deviation:    a.Deviation,
		}
	}
	return result
}

// buildAllocationArray converts allocation slice to response format
func buildAllocationArray(allocations []allocation.PortfolioAllocation) []map[string]interface{} {
	result := make([]map[string]interface{}, len(allocations))
	for i, a := range allocations {
		result[i] = map[string]interface{}{
			"name":          a.Name,
			"target_pct":    a.TargetPct,
			"current_pct":   a.CurrentPct,
			"current_value": a.CurrentValue,
			"deviation":     a.Deviation,
		}
	}
	return result
}

// buildAlertsArray converts ConcentrationAlert slice to response format
func buildAlertsArray(alerts []allocation.ConcentrationAlert) []map[string]interface{} {
	result := make([]map[string]interface{}, len(alerts))
	for i, alert := range alerts {
		result[i] = map[string]interface{}{
			"type":                alert.Type,
			"name":                alert.Name,
			"current_pct":         alert.CurrentPct,
			"limit_pct":           alert.LimitPct,
			"alert_threshold_pct": alert.AlertThresholdPct,
			"severity":            alert.Severity,
		}
	}
	return result
}

// writeJSON writes a JSON response
func (h *TradingHandlers) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
	}
}

// writeError writes an error response
func (h *TradingHandlers) writeError(w http.ResponseWriter, status int, message string) {
	h.writeJSON(w, status, map[string]string{"error": message})
}

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

// Trade Validation Endpoints (API Extension)

// HandleValidateTrade handles POST /api/trade-validation/validate-trade
// Full trade validation without execution
func (h *TradingHandlers) HandleValidateTrade(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Symbol   string  `json:"symbol"`
		Side     string  `json:"side"`
		Quantity float64 `json:"quantity"`
		Price    float64 `json:"price,omitempty"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// Run full validation using safety service
	validationErrors := []string{}
	warnings := []string{}
	passed := true

	if h.safetyService == nil {
		h.writeError(w, http.StatusServiceUnavailable, "Safety service not available")
		return
	}

	if err := h.safetyService.ValidateTrade(req.Symbol, req.Side, req.Quantity); err != nil {
		validationErrors = append(validationErrors, err.Error())
		passed = false
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"data": map[string]interface{}{
			"passed": passed,
			"symbol": req.Symbol,
			"side":   req.Side,
			"quantity": req.Quantity,
			"errors": validationErrors,
			"warnings": warnings,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	})
}

// HandleCheckMarketHours handles POST /api/trade-validation/check-market-hours
// Market hours validation
func (h *TradingHandlers) HandleCheckMarketHours(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Symbol string `json:"symbol"`
		Side   string `json:"side"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// This endpoint delegates to the full ValidateTrade which includes market hours check
	// Return 501 to indicate client should use /validate-trade instead
	h.writeJSON(w, http.StatusNotImplemented, map[string]interface{}{
		"error": map[string]interface{}{
			"message": "Market hours check not yet implemented as standalone endpoint",
			"code":    "NOT_IMPLEMENTED",
			"details": map[string]string{
				"reason":      "Use /trade-validation/validate-trade for full validation including market hours",
				"alternative": "/api/trade-validation/validate-trade",
			},
		},
	})
}

// HandleCheckPriceFreshness handles POST /api/trade-validation/check-price-freshness
// Price staleness check
func (h *TradingHandlers) HandleCheckPriceFreshness(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Symbol string `json:"symbol"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// Return 501 Not Implemented - requires price database access
	h.writeJSON(w, http.StatusNotImplemented, map[string]interface{}{
		"error": map[string]interface{}{
			"message": "Price freshness check not yet implemented as standalone endpoint",
			"code":    "NOT_IMPLEMENTED",
			"details": map[string]string{
				"reason":      "Requires integration with price database",
				"alternative": "/api/trade-validation/validate-trade",
			},
		},
	})
}

// HandleCalculateCommission handles POST /api/trade-validation/calculate-commission
// Commission calculation
func (h *TradingHandlers) HandleCalculateCommission(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Symbol   string  `json:"symbol"`
		Side     string  `json:"side"`
		Quantity float64 `json:"quantity"`
		Price    float64 `json:"price"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// Get commission settings (defaults: 2 EUR fixed + 0.2%)
	fixedCommissionEUR := 2.0
	variableCommissionRate := 0.002

	if h.settingsService != nil {
		if val, err := h.settingsService.Get("transaction_cost_fixed"); err == nil {
			if fixed, ok := val.(float64); ok {
				fixedCommissionEUR = fixed
			}
		}
		if val, err := h.settingsService.Get("transaction_cost_percent"); err == nil {
			if variable, ok := val.(float64); ok {
				variableCommissionRate = variable
			}
		}
	}

	tradeValue := req.Quantity * req.Price
	variableCommission := tradeValue * variableCommissionRate
	totalCommission := fixedCommissionEUR + variableCommission

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"data": map[string]interface{}{
			"symbol":               req.Symbol,
			"trade_value":          tradeValue,
			"fixed_commission":     fixedCommissionEUR,
			"variable_commission":  variableCommission,
			"total_commission":     totalCommission,
			"commission_currency":  "EUR",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	})
}

// HandleCalculateLimitPrice handles POST /api/trade-validation/calculate-limit-price
// Limit price calculation
func (h *TradingHandlers) HandleCalculateLimitPrice(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Symbol        string  `json:"symbol"`
		Side          string  `json:"side"`
		CurrentPrice  float64 `json:"current_price"`
		SlippagePct   float64 `json:"slippage_pct,omitempty"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// Default slippage: 0.5% for buys, -0.5% for sells
	slippage := req.SlippagePct
	if slippage == 0 {
		if strings.ToUpper(req.Side) == "BUY" {
			slippage = 0.005 // 0.5% above current price
		} else {
			slippage = -0.005 // 0.5% below current price
		}
	}

	limitPrice := req.CurrentPrice * (1 + slippage)

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"data": map[string]interface{}{
			"symbol":        req.Symbol,
			"side":          req.Side,
			"current_price": req.CurrentPrice,
			"slippage_pct":  slippage * 100,
			"limit_price":   limitPrice,
			"note":          "Limit price calculated with slippage buffer",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	})
}

// HandleCheckEligibility handles POST /api/trade-validation/check-eligibility
// Security trading eligibility
func (h *TradingHandlers) HandleCheckEligibility(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Symbol string `json:"symbol"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// Check if security exists and is tradeable via safety service
	eligible := true
	reasons := []string{}

	if h.safetyService == nil {
		h.writeError(w, http.StatusServiceUnavailable, "Safety service not available")
		return
	}

	// Try to validate the security (this will check if it exists)
	// Use a dummy buy with 1 share to check eligibility
	if err := h.safetyService.ValidateTrade(req.Symbol, "BUY", 1.0); err != nil {
		eligible = false
		reasons = append(reasons, err.Error())
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"data": map[string]interface{}{
			"symbol":         req.Symbol,
			"eligible":       eligible,
			"reasons":        reasons,
			"can_buy":        eligible,
			"can_sell":       eligible,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	})
}

// HandleCheckCashSufficiency handles POST /api/trade-validation/check-cash-sufficiency
// Cash requirement validation
func (h *TradingHandlers) HandleCheckCashSufficiency(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Symbol   string  `json:"symbol"`
		Side     string  `json:"side"`
		Quantity float64 `json:"quantity"`
		Price    float64 `json:"price"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// For SELL orders, no cash check needed
	if strings.ToUpper(req.Side) == "SELL" {
		h.writeJSON(w, http.StatusOK, map[string]interface{}{
			"data": map[string]interface{}{
				"sufficient": true,
				"side":       req.Side,
				"note":       "Sell orders do not require cash",
			},
			"metadata": map[string]interface{}{
				"timestamp": time.Now().Format(time.RFC3339),
			},
		})
		return
	}

	// Get current cash balance
	cashBalance := 0.0
	if h.portfolioService != nil {
		summary, err := h.portfolioService.GetPortfolioSummary()
		if err == nil {
			cashBalance = summary.CashBalance
		}
	}

	// Calculate required cash (trade value + commission)
	tradeValue := req.Quantity * req.Price
	commission := 2.0 + (tradeValue * 0.002) // Default commission
	requiredCash := tradeValue + commission

	sufficient := cashBalance >= requiredCash
	shortfall := 0.0
	if !sufficient {
		shortfall = requiredCash - cashBalance
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"data": map[string]interface{}{
			"sufficient":      sufficient,
			"cash_balance":    cashBalance,
			"required_cash":   requiredCash,
			"trade_value":     tradeValue,
			"commission":      commission,
			"shortfall":       shortfall,
			"currency":        "EUR",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	})
}
