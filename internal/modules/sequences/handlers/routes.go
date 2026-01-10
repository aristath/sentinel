package handlers

import (
	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all sequence generation routes
func (h *Handler) RegisterRoutes(r chi.Router) {
	r.Route("/sequences", func(r chi.Router) {
		// Generators
		r.Post("/generate/pattern", h.HandleGenerateFromPattern)
		r.Post("/generate/combinatorial", h.HandleGenerateCombinatorial)
		r.Post("/generate/all-patterns", h.HandleGenerateFromAllPatterns)
		r.Get("/patterns", h.HandleListPatterns)

		// Filters
		r.Post("/filter/eligibility", h.HandleFilterEligibility)
		r.Post("/filter/correlation", h.HandleFilterCorrelation)
		r.Post("/filter/recently-traded", h.HandleFilterRecentlyTraded)
		r.Post("/filter/tags", h.HandleFilterTags)

		// Context
		r.Get("/context", h.HandleGetContext)
	})
}
