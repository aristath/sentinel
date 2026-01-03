package rebalancing

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
)

// Handlers provides HTTP handlers for rebalancing endpoints
type Handlers struct {
	service          *Service
	portfolioService *portfolio.PortfolioService
	tradernetClient  *tradernet.Client
	log              zerolog.Logger
}

// NewHandlers creates a new rebalancing handlers instance
func NewHandlers(
	service *Service,
	portfolioService *portfolio.PortfolioService,
	tradernetClient *tradernet.Client,
	log zerolog.Logger,
) *Handlers {
	return &Handlers{
		service:          service,
		portfolioService: portfolioService,
		tradernetClient:  tradernetClient,
		log:              log.With().Str("module", "rebalancing_handlers").Logger(),
	}
}

// RegisterRoutes registers all rebalancing routes
func (h *Handlers) RegisterRoutes(r chi.Router) {
	r.Route("/rebalancing", func(r chi.Router) {
		r.Get("/check-triggers", h.CheckTriggers)
		r.Get("/calculate-trades", h.CalculateTrades)
		r.Post("/check-negative-balances", h.CheckNegativeBalances)
		r.Post("/execute-rebalance", h.ExecuteRebalance)
	})
}

// CheckTriggersResponse is the response for trigger checking
type CheckTriggersResponse struct {
	Triggered bool     `json:"triggered"`
	Reasons   []string `json:"reasons"`
}

// CheckTriggers checks if rebalancing should be triggered
func (h *Handlers) CheckTriggers(w http.ResponseWriter, r *http.Request) {
	// Get query parameters
	enabled := r.URL.Query().Get("enabled") == "true"
	driftThreshold, _ := strconv.ParseFloat(r.URL.Query().Get("drift_threshold"), 64)
	if driftThreshold == 0 {
		driftThreshold = 0.05 // Default 5%
	}

	cashThresholdMultiplier, _ := strconv.ParseFloat(r.URL.Query().Get("cash_threshold_multiplier"), 64)
	if cashThresholdMultiplier == 0 {
		cashThresholdMultiplier = 2.0 // Default 2x min trade
	}

	minTradeSize, _ := strconv.ParseFloat(r.URL.Query().Get("min_trade_size"), 64)
	if minTradeSize == 0 {
		minTradeSize = 250.0 // Default €250
	}

	// Get current positions
	positions, err := h.tradernetClient.GetPortfolio()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get portfolio")
		http.Error(w, "Failed to get portfolio", http.StatusInternalServerError)
		return
	}

	// Convert Tradernet positions to portfolio positions
	portfolioPositions := make([]*portfolio.Position, len(positions))
	for i, pos := range positions {
		portfolioPositions[i] = &portfolio.Position{
			Symbol:         pos.Symbol,
			Quantity:       pos.Quantity,
			AvgPrice:       pos.AvgPrice,
			CurrentPrice:   pos.CurrentPrice,
			MarketValueEUR: pos.MarketValueEUR,
			Currency:       pos.Currency,
		}
	}

	// Get cash balances
	cashBalances, err := h.tradernetClient.GetCashBalances()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get cash balances")
		http.Error(w, "Failed to get cash balances", http.StatusInternalServerError)
		return
	}

	// Calculate total cash in EUR
	totalCash := 0.0
	for _, balance := range cashBalances {
		// Simple assumption: if currency is EUR, add directly; otherwise assume 1:1
		// TODO: Use proper exchange rate service
		if balance.Currency == "EUR" {
			totalCash += balance.Amount
		} else {
			totalCash += balance.Amount
		}
	}

	// Calculate total portfolio value
	totalValue := 0.0
	for _, pos := range portfolioPositions {
		totalValue += pos.MarketValueEUR
	}

	// TODO: Get actual target allocations from allocation repository
	// For now, use empty map to avoid nil panics
	targetAllocations := make(map[string]float64)

	// Check triggers
	result := h.service.GetTriggerChecker().CheckRebalanceTriggers(
		portfolioPositions,
		targetAllocations,
		totalValue,
		totalCash,
		enabled,
		driftThreshold,
		cashThresholdMultiplier,
		minTradeSize,
	)

	response := CheckTriggersResponse{
		Triggered: result.ShouldRebalance,
		Reasons:   []string{result.Reason},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// CalculateTradesRequest is the request for calculating rebalancing trades
type CalculateTradesRequest struct {
	AvailableCash float64 `json:"available_cash"`
}

// CalculateTradesResponse is the response for calculating trades
type CalculateTradesResponse struct {
	Trades []interface{} `json:"trades"`
}

// CalculateTrades calculates optimal rebalancing trades
func (h *Handlers) CalculateTrades(w http.ResponseWriter, r *http.Request) {
	// Get available cash from query parameter
	availableCashStr := r.URL.Query().Get("available_cash")
	availableCash, err := strconv.ParseFloat(availableCashStr, 64)
	if err != nil || availableCash <= 0 {
		// Get cash from Tradernet client
		cashBalances, err := h.tradernetClient.GetCashBalances()
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to get cash balances")
			http.Error(w, "Failed to get cash balances", http.StatusInternalServerError)
			return
		}

		availableCash = 0.0
		for _, balance := range cashBalances {
			if balance.Currency == "EUR" {
				availableCash += balance.Amount
			}
		}
	}

	// Calculate trades
	trades, err := h.service.CalculateRebalanceTrades(availableCash)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to calculate trades")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	response := CalculateTradesResponse{
		Trades: trades,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// CheckNegativeBalancesResponse is the response for checking negative balances
type CheckNegativeBalancesResponse struct {
	HasNegative       bool               `json:"has_negative"`
	BelowMinimum      bool               `json:"below_minimum"`
	Shortfalls        map[string]float64 `json:"shortfalls,omitempty"`
	TotalShortfallEUR float64            `json:"total_shortfall_eur,omitempty"`
}

// CheckNegativeBalances checks for negative balances and currencies below minimum
func (h *Handlers) CheckNegativeBalances(w http.ResponseWriter, r *http.Request) {
	// Get cash balances
	cashBalances, err := h.tradernetClient.GetCashBalances()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get cash balances")
		http.Error(w, "Failed to get cash balances", http.StatusInternalServerError)
		return
	}

	// Convert to map
	balanceMap := make(map[string]float64)
	for _, balance := range cashBalances {
		balanceMap[balance.Currency] = balance.Amount
	}

	// Check for negatives
	hasNegative := false
	for _, amount := range balanceMap {
		if amount < 0 {
			hasNegative = true
			break
		}
	}

	// Check currency minimums
	shortfalls, err := h.service.GetNegativeBalanceRebalancer().CheckCurrencyMinimums(balanceMap)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to check currency minimums")
		http.Error(w, "Failed to check currency minimums", http.StatusInternalServerError)
		return
	}
	belowMinimum := len(shortfalls) > 0

	// Calculate total shortfall in EUR
	totalShortfallEUR := 0.0
	for _, shortfall := range shortfalls {
		totalShortfallEUR += shortfall // Simple assumption: 1:1 for now
	}

	response := CheckNegativeBalancesResponse{
		HasNegative:       hasNegative,
		BelowMinimum:      belowMinimum,
		Shortfalls:        shortfalls,
		TotalShortfallEUR: totalShortfallEUR,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// ExecuteRebalanceRequest is the request for executing rebalancing
type ExecuteRebalanceRequest struct {
	AvailableCash float64 `json:"available_cash,omitempty"`
}

// ExecuteRebalanceResponse is the response for executing rebalancing
type ExecuteRebalanceResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
}

// ExecuteRebalance executes a full rebalancing cycle
func (h *Handlers) ExecuteRebalance(w http.ResponseWriter, r *http.Request) {
	var req ExecuteRebalanceRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	// Get positions and cash if not provided
	positions, err := h.tradernetClient.GetPortfolio()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get portfolio")
		http.Error(w, "Failed to get portfolio", http.StatusInternalServerError)
		return
	}

	cashBalances, err := h.tradernetClient.GetCashBalances()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get cash balances")
		http.Error(w, "Failed to get cash balances", http.StatusInternalServerError)
		return
	}

	availableCash := req.AvailableCash
	if availableCash == 0 {
		for _, balance := range cashBalances {
			if balance.Currency == "EUR" {
				availableCash += balance.Amount
			}
		}
	}

	totalValue := 0.0
	for _, pos := range positions {
		totalValue += pos.MarketValueEUR
	}

	// Execute rebalancing
	err = h.service.ExecuteRebalancing(
		positions,
		make(map[string]float64), // TODO: Get actual target allocations
		totalValue,
		availableCash,
	)

	if err != nil {
		h.log.Error().Err(err).Msg("Failed to execute rebalancing")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	response := ExecuteRebalanceResponse{
		Success: true,
		Message: "Rebalancing completed successfully",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}
