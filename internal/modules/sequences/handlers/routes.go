package handlers

import (
	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all sequence generation routes
func (h *Handler) RegisterRoutes(r chi.Router) {
	r.Route("/sequences", func(r chi.Router) {
		// Generation
		r.Post("/generate", h.HandleGenerate)

		// Info
		r.Get("/info", h.HandleGetInfo)

		// Filters (correlation is the only remaining meaningful filter)
		r.Post("/filter/correlation", h.HandleFilterCorrelation)
	})
}
