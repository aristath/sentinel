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
	})
}
