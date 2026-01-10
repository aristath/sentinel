package handlers

import (
	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all trading routes
func (h *TradingHandlers) RegisterRoutes(r chi.Router) {
	// Trading routes (faithful translation of Python routes)
	r.Route("/trades", func(r chi.Router) {
		r.Get("/", h.HandleGetTrades)                         // Trade history
		r.Post("/execute", h.HandleExecuteTrade)              // Execute trade (via Tradernet microservice)
		r.Get("/allocation", h.HandleGetAllocation)           // Portfolio allocation
		r.Get("/recommendations", h.HandleGetRecommendations) // Fetch existing recommendations
	})

	// Trade Validation endpoints (API extension)
	r.Route("/trade-validation", func(r chi.Router) {
		r.Post("/validate-trade", h.HandleValidateTrade)               // Full trade validation
		r.Post("/check-market-hours", h.HandleCheckMarketHours)        // Market hours check
		r.Post("/check-price-freshness", h.HandleCheckPriceFreshness)  // Price staleness check
		r.Post("/calculate-commission", h.HandleCalculateCommission)   // Commission calculation
		r.Post("/calculate-limit-price", h.HandleCalculateLimitPrice)  // Limit price calculation
		r.Post("/check-eligibility", h.HandleCheckEligibility)         // Security eligibility
		r.Post("/check-cash-sufficiency", h.HandleCheckCashSufficiency) // Cash sufficiency check
	})
}
