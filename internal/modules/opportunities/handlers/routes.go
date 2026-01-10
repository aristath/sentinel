package handlers

import (
	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all opportunities routes
func (h *Handler) RegisterRoutes(r chi.Router) {
	r.Route("/opportunities", func(r chi.Router) {
		r.Get("/all", h.HandleGetAll)
		r.Get("/profit-taking", h.HandleGetProfitTaking)
		r.Get("/averaging-down", h.HandleGetAveragingDown)
		r.Get("/opportunity-buys", h.HandleGetOpportunityBuys)
		r.Get("/rebalance-buys", h.HandleGetRebalanceBuys)
		r.Get("/rebalance-sells", h.HandleGetRebalanceSells)
		r.Get("/weight-based", h.HandleGetWeightBased)
		r.Get("/registry", h.HandleGetRegistry)
	})
}
