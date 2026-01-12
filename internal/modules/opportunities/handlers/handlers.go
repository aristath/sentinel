// Package handlers provides HTTP handlers for opportunities operations.
package handlers

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/allocation"
	"github.com/aristath/sentinel/internal/modules/opportunities"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	planningrepo "github.com/aristath/sentinel/internal/modules/planning/repository"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// Handler handles opportunities HTTP requests
type Handler struct {
	service      *opportunities.Service
	positionRepo *portfolio.PositionRepository
	securityRepo *universe.SecurityRepository
	allocRepo    *allocation.Repository
	cashManager  domain.CashManager
	configRepo   *planningrepo.ConfigRepository
	portfolioDB  *sql.DB
	log          zerolog.Logger
}

// NewHandler creates a new opportunities handler
func NewHandler(
	service *opportunities.Service,
	positionRepo *portfolio.PositionRepository,
	securityRepo *universe.SecurityRepository,
	allocRepo *allocation.Repository,
	cashManager domain.CashManager,
	configRepo *planningrepo.ConfigRepository,
	portfolioDB *sql.DB,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		service:      service,
		positionRepo: positionRepo,
		securityRepo: securityRepo,
		allocRepo:    allocRepo,
		cashManager:  cashManager,
		configRepo:   configRepo,
		portfolioDB:  portfolioDB,
		log:          log.With().Str("handler", "opportunities").Logger(),
	}
}

// HandleGetAll handles GET /api/opportunities/all
func (h *Handler) HandleGetAll(w http.ResponseWriter, r *http.Request) {
	// Build opportunity context from current state
	ctx, err := h.buildOpportunityContext()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to build opportunity context")
		http.Error(w, "Failed to build opportunity context", http.StatusInternalServerError)
		return
	}

	// Load planner configuration
	config, err := h.loadPlannerConfig()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to load planner config")
		http.Error(w, "Failed to load planner config", http.StatusInternalServerError)
		return
	}

	// Apply configuration to context (sets AllowBuy, AllowSell, transaction costs)
	ctx.ApplyConfig(config)

	// Identify opportunities
	opportunities, err := h.service.IdentifyOpportunities(ctx, config)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to identify opportunities")
		http.Error(w, "Failed to identify opportunities", http.StatusInternalServerError)
		return
	}

	// Convert to response format
	allOpportunities := make([]map[string]interface{}, 0)
	for category, candidates := range opportunities {
		for _, candidate := range candidates {
			allOpportunities = append(allOpportunities, map[string]interface{}{
				"symbol":    candidate.Symbol,
				"isin":      candidate.ISIN,
				"name":      candidate.Name,
				"side":      candidate.Side,
				"quantity":  candidate.Quantity,
				"price":     candidate.Price,
				"value_eur": candidate.ValueEUR,
				"currency":  candidate.Currency,
				"reason":    candidate.Reason,
				"priority":  candidate.Priority,
				"category":  string(category),
			})
		}
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"opportunities": allOpportunities,
			"count":         len(allOpportunities),
			"by_category":   opportunities,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// handleCategoryOpportunities is a helper for category-specific endpoints
func (h *Handler) handleCategoryOpportunities(w http.ResponseWriter, r *http.Request, category planningdomain.OpportunityCategory) {
	// Build opportunity context from current state
	ctx, err := h.buildOpportunityContext()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to build opportunity context")
		http.Error(w, "Failed to build opportunity context", http.StatusInternalServerError)
		return
	}

	// Load planner configuration
	config, err := h.loadPlannerConfig()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to load planner config")
		http.Error(w, "Failed to load planner config", http.StatusInternalServerError)
		return
	}

	// Apply configuration to context (sets AllowBuy, AllowSell, transaction costs)
	ctx.ApplyConfig(config)

	// Identify opportunities
	allOpportunities, err := h.service.IdentifyOpportunities(ctx, config)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to identify opportunities")
		http.Error(w, "Failed to identify opportunities", http.StatusInternalServerError)
		return
	}

	// Filter by category
	categoryOpps := allOpportunities[category]
	if categoryOpps == nil {
		categoryOpps = []planningdomain.ActionCandidate{}
	}

	// Convert to response format
	opps := make([]map[string]interface{}, 0, len(categoryOpps))
	for _, candidate := range categoryOpps {
		opps = append(opps, map[string]interface{}{
			"symbol":    candidate.Symbol,
			"isin":      candidate.ISIN,
			"name":      candidate.Name,
			"side":      candidate.Side,
			"quantity":  candidate.Quantity,
			"price":     candidate.Price,
			"value_eur": candidate.ValueEUR,
			"currency":  candidate.Currency,
			"reason":    candidate.Reason,
			"priority":  candidate.Priority,
		})
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"opportunities": opps,
			"count":         len(opps),
			"category":      string(category),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetProfitTaking handles GET /api/opportunities/profit-taking
func (h *Handler) HandleGetProfitTaking(w http.ResponseWriter, r *http.Request) {
	h.handleCategoryOpportunities(w, r, planningdomain.OpportunityCategoryProfitTaking)
}

// HandleGetAveragingDown handles GET /api/opportunities/averaging-down
func (h *Handler) HandleGetAveragingDown(w http.ResponseWriter, r *http.Request) {
	h.handleCategoryOpportunities(w, r, planningdomain.OpportunityCategoryAveragingDown)
}

// HandleGetOpportunityBuys handles GET /api/opportunities/opportunity-buys
func (h *Handler) HandleGetOpportunityBuys(w http.ResponseWriter, r *http.Request) {
	h.handleCategoryOpportunities(w, r, planningdomain.OpportunityCategoryOpportunityBuys)
}

// HandleGetRebalanceBuys handles GET /api/opportunities/rebalance-buys
func (h *Handler) HandleGetRebalanceBuys(w http.ResponseWriter, r *http.Request) {
	h.handleCategoryOpportunities(w, r, planningdomain.OpportunityCategoryRebalanceBuys)
}

// HandleGetRebalanceSells handles GET /api/opportunities/rebalance-sells
func (h *Handler) HandleGetRebalanceSells(w http.ResponseWriter, r *http.Request) {
	h.handleCategoryOpportunities(w, r, planningdomain.OpportunityCategoryRebalanceSells)
}

// HandleGetWeightBased handles GET /api/opportunities/weight-based
func (h *Handler) HandleGetWeightBased(w http.ResponseWriter, r *http.Request) {
	h.handleCategoryOpportunities(w, r, planningdomain.OpportunityCategoryWeightBased)
}

// HandleGetRegistry handles GET /api/opportunities/registry
func (h *Handler) HandleGetRegistry(w http.ResponseWriter, r *http.Request) {
	registry := h.service.GetRegistry()
	calculators := registry.List()

	calcInfo := make([]map[string]interface{}, 0, len(calculators))
	for _, calc := range calculators {
		calcInfo = append(calcInfo, map[string]interface{}{
			"name":     calc.Name(),
			"category": string(calc.Category()),
		})
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"calculators": calcInfo,
			"count":       len(calcInfo),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// buildOpportunityContext builds opportunity context from current portfolio state
func (h *Handler) buildOpportunityContext() (*planningdomain.OpportunityContext, error) {
	// Check for nil dependencies
	if h.positionRepo == nil {
		return nil, fmt.Errorf("position repository not initialized")
	}
	if h.securityRepo == nil {
		return nil, fmt.Errorf("security repository not initialized")
	}
	if h.allocRepo == nil {
		return nil, fmt.Errorf("allocation repository not initialized")
	}

	// Get positions
	positions, err := h.positionRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get positions: %w", err)
	}

	// Get securities
	securities, err := h.securityRepo.GetAllActive()
	if err != nil {
		return nil, fmt.Errorf("failed to get securities: %w", err)
	}

	// Get allocations
	allocations, err := h.allocRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get allocations: %w", err)
	}

	// Get cash balances
	cashBalances := make(map[string]float64)
	if h.cashManager != nil {
		balances, err := h.cashManager.GetAllCashBalances()
		if err != nil {
			h.log.Warn().Err(err).Msg("Failed to get cash balances")
		} else {
			cashBalances = balances
		}
	}

	// Convert securities to domain format
	domainSecurities := make([]domain.Security, 0, len(securities))
	stocksByISIN := make(map[string]domain.Security)
	for _, sec := range securities {
		domainSec := domain.Security{
			Symbol:   sec.Symbol,
			ISIN:     sec.ISIN,
			Active:   sec.Active,
			Country:  sec.Country,
			Currency: domain.Currency(sec.Currency),
			Name:     sec.Name,
		}
		domainSecurities = append(domainSecurities, domainSec)
		if sec.ISIN != "" {
			stocksByISIN[sec.ISIN] = domainSec
		}
	}

	// Enrich positions with security data and calculate portfolio value
	enrichedPositions := make([]planningdomain.EnrichedPosition, 0)
	totalValue := 0.0
	for _, pos := range positions {
		if pos.ISIN == "" {
			continue
		}

		// Get security from universe for trading constraints
		universeSec, err := h.securityRepo.GetByISIN(pos.ISIN)
		if err != nil {
			h.log.Warn().Err(err).Str("isin", pos.ISIN).Msg("Failed to get security from universe")
			continue
		}

		security, ok := stocksByISIN[pos.ISIN]
		if !ok {
			continue
		}

		marketValueEUR := pos.Quantity * pos.CurrentPrice
		totalValue += marketValueEUR

		enriched := planningdomain.EnrichedPosition{
			ISIN:           pos.ISIN,
			Symbol:         pos.Symbol,
			Quantity:       pos.Quantity,
			Currency:       pos.Currency,
			AverageCost:    pos.AvgPrice,
			MarketValueEUR: marketValueEUR,
			CurrentPrice:   pos.CurrentPrice,
			SecurityName:   security.Name,
			Country:        security.Country,
			Active:         security.Active,
			AllowBuy:       universeSec.AllowBuy,
			AllowSell:      universeSec.AllowSell,
			MinLot:         universeSec.MinLot,
		}
		enrichedPositions = append(enrichedPositions, enriched)
	}

	// Add cash to total value
	for _, balance := range cashBalances {
		totalValue += balance
	}

	// Calculate WeightInPortfolio for each position
	if totalValue > 0 {
		for i := range enrichedPositions {
			pos := &enrichedPositions[i]
			positionValue := pos.CurrentPrice * pos.Quantity
			if positionValue > 0 {
				pos.WeightInPortfolio = positionValue / totalValue
			}
		}
	}

	// Get available cash in EUR
	availableCashEUR := cashBalances["EUR"]

	// Build current prices map from positions (keyed by ISIN)
	currentPrices := make(map[string]float64)
	for _, pos := range positions {
		if pos.ISIN != "" && pos.CurrentPrice > 0 {
			currentPrices[pos.ISIN] = pos.CurrentPrice
		}
	}

	// Build opportunity context with all required fields
	ctx := &planningdomain.OpportunityContext{
		EnrichedPositions:      enrichedPositions,
		Securities:             domainSecurities,
		TotalPortfolioValueEUR: totalValue,
		StocksByISIN:           stocksByISIN,
		CurrentPrices:          currentPrices,
		AvailableCashEUR:       availableCashEUR,
		CountryAllocations:     allocations, // These are allocation targets
		// Initialize constraint maps to avoid nil pointer issues
		IneligibleISINs:     make(map[string]bool),
		RecentlySoldISINs:   make(map[string]bool),
		RecentlyBoughtISINs: make(map[string]bool),
		// Default transaction costs (will be overridden by ApplyConfig)
		TransactionCostFixed:   2.0,
		TransactionCostPercent: 0.002,
		// Default to true (will be overridden by ApplyConfig)
		AllowBuy:  true,
		AllowSell: true,
	}

	return ctx, nil
}

// loadPlannerConfig loads planner configuration
func (h *Handler) loadPlannerConfig() (*planningdomain.PlannerConfiguration, error) {
	if h.configRepo == nil {
		return nil, fmt.Errorf("config repository not initialized")
	}

	config, err := h.configRepo.GetDefaultConfig()
	if err != nil {
		return nil, fmt.Errorf("failed to load planner config: %w", err)
	}
	return config, nil
}

// writeJSON writes a JSON response
func (h *Handler) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)

	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
	}
}
