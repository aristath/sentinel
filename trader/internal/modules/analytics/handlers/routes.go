package handlers

import (
	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all analytics routes
func (h *Handler) RegisterRoutes(r chi.Router) {
	r.Route("/analytics", func(r chi.Router) {
		// Factor exposure endpoints
		r.Route("/factor-exposures", func(r chi.Router) {
			r.Get("/", h.HandleGetFactorExposures)
			r.Get("/history", h.HandleGetFactorExposureHistory)
		})
	})
}

