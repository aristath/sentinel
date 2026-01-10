package handlers

import (
	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all rebalancing routes
func (h *Handler) RegisterRoutes(r chi.Router) {
	r.Route("/rebalancing", func(r chi.Router) {
		r.Post("/calculate", h.HandleCalculateRebalance)
		r.Post("/calculate/target-weights", h.HandleCalculateTargetWeights)
		r.Get("/triggers", h.HandleGetTriggers)
		r.Get("/min-trade-amount", h.HandleGetMinTradeAmount)
		r.Post("/simulate-rebalance", h.HandleSimulateRebalance)
		r.Post("/negative-balance-check", h.HandleNegativeBalanceCheck)
	})
}
