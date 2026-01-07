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
}
