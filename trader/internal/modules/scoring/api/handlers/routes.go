package handlers

import (
	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all scoring routes
func (h *Handlers) RegisterRoutes(r chi.Router) {
	// Scoring routes
	r.Route("/scoring", func(r chi.Router) {
		r.Post("/score", h.HandleScoreSecurity) // Calculate security score
	})
}
