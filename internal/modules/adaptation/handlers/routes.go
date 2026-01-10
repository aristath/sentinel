package handlers

import (
	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all market regime and adaptation routes
func (h *Handler) RegisterRoutes(r chi.Router) {
	r.Route("/adaptation", func(r chi.Router) {
		r.Get("/current", h.HandleGetCurrent)
		r.Get("/history", h.HandleGetHistory)
		r.Get("/adaptive-weights", h.HandleGetAdaptiveWeights)
		r.Get("/adaptive-parameters", h.HandleGetAdaptiveParameters)
		r.Get("/component-performance", h.HandleGetComponentPerformance)
		r.Get("/performance-history", h.HandleGetPerformanceHistory)
	})
}
