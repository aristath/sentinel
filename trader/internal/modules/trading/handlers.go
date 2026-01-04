package trading

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/modules/allocation"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/settings"
	"github.com/rs/zerolog"
)

// SecurityFetcher provides security information for trades
type SecurityFetcher interface {
	GetSecurityName(symbol string) (string, error)
}

// TradingHandlers contains HTTP handlers for trading API
type TradingHandlers struct {
	log                        zerolog.Logger
	securityFetcher            SecurityFetcher
	tradeRepo                  *TradeRepository
	portfolioService           *portfolio.PortfolioService
	concentrationAlertProvider allocation.ConcentrationAlertProvider
	tradernetClient            *tradernet.Client
	safetyService              *TradeSafetyService
	settingsService            *settings.Service
}

// NewTradingHandlers creates a new trading handlers instance
func NewTradingHandlers(
	tradeRepo *TradeRepository,
	securityFetcher SecurityFetcher,
	portfolioService *portfolio.PortfolioService,
	concentrationAlertProvider allocation.ConcentrationAlertProvider,
	tradernetClient *tradernet.Client,
	safetyService *TradeSafetyService,
	settingsService *settings.Service,
	log zerolog.Logger,
) *TradingHandlers {
	return &TradingHandlers{
		tradeRepo:                  tradeRepo,
		securityFetcher:            securityFetcher,
		portfolioService:           portfolioService,
		concentrationAlertProvider: concentrationAlertProvider,
		tradernetClient:            tradernetClient,
		safetyService:              safetyService,
		settingsService:            settingsService,
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
	result, err := h.tradernetClient.PlaceOrder(req.Symbol, req.Side, req.Quantity)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to place order")
		h.writeError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to place order: %v", err))
		return
	}

	// Record trade in database
	if err := h.recordTrade(req.Symbol, req.Side, req.Quantity, result, tradingMode); err != nil {
		h.log.Error().Err(err).Msg("Failed to record trade")
		// Don't fail the request - trade already executed
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
	result *tradernet.OrderResult,
	tradingMode string,
) error {
	now := time.Now()

	trade := Trade{
		Symbol:     symbol,
		Side:       TradeSide(strings.ToUpper(side)),
		Quantity:   quantity,
		Price:      result.Price,
		ExecutedAt: now,
		OrderID:    result.OrderID,
		Source:     "manual",
		BucketID:   "core",
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
