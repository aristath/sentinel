package handlers

import (
	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all snapshot routes
func (h *Handler) RegisterRoutes(r chi.Router) {
	r.Route("/snapshots", func(r chi.Router) {
		r.Get("/complete", h.HandleGetComplete)
		r.Get("/portfolio-state", h.HandleGetPortfolioState)
		r.Get("/market-context", h.HandleGetMarketContext)
		r.Get("/pending-actions", h.HandleGetPendingActions)
		r.Get("/historical-summary", h.HandleGetHistoricalSummary)
		r.Get("/risk-snapshot", h.HandleGetRiskSnapshot)
	})
}
