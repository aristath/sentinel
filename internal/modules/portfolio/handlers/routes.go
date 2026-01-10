package handlers

import (
	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all portfolio routes
func (h *Handler) RegisterRoutes(r chi.Router) {
	r.Route("/portfolio", func(r chi.Router) {
		r.Get("/", h.HandleGetPortfolio)                   // List positions (same as GET /portfolio)
		r.Get("/summary", h.HandleGetSummary)              // Portfolio summary
		r.Get("/transactions", h.HandleGetTransactions)    // Transaction history (via Tradernet microservice)
		r.Get("/cash-breakdown", h.HandleGetCashBreakdown) // Cash breakdown (via Tradernet microservice)

		// Performance Analytics (API extension)
		r.Route("/performance", func(r chi.Router) {
			r.Get("/history", h.HandleGetPerformanceHistory)         // Historical returns
			r.Get("/vs-benchmark", h.HandleGetPerformanceVsBenchmark) // Benchmark comparison
			r.Get("/attribution", h.HandleGetPerformanceAttribution)  // Performance attribution
		})

		// Concentration & Diversification (API extension)
		r.Get("/concentration", h.HandleGetConcentration)       // Concentration metrics
		r.Get("/diversification", h.HandleGetDiversification)   // Diversification scores

		// P&L & Cost Basis (API extension)
		r.Route("/unrealized-pnl", func(r chi.Router) {
			r.Get("/breakdown", h.HandleGetUnrealizedPnLBreakdown) // P&L breakdown
		})
		r.Get("/cost-basis", h.HandleGetCostBasis)              // Cost basis analysis
	})
}
