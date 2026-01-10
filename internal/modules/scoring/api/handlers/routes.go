package handlers

import (
	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all scoring routes
func (h *Handlers) RegisterRoutes(r chi.Router) {
	// Scoring routes
	r.Route("/scoring", func(r chi.Router) {
		r.Post("/score", h.HandleScoreSecurity) // Calculate security score

		// Score Components (API extension)
		r.Route("/components", func(r chi.Router) {
			r.Get("/{isin}", h.HandleGetScoreComponents) // Detailed component breakdown
			r.Get("/all", h.HandleGetAllScoreComponents)  // All securities components
		})

		// Scoring Weights (API extension)
		r.Route("/weights", func(r chi.Router) {
			r.Get("/current", h.HandleGetCurrentWeights)              // Current weights (base + adaptive)
			r.Get("/adaptive-history", h.HandleGetAdaptiveWeightHistory) // Adaptive weight changes over time
		})

		// Scoring Formulas (API extension)
		r.Route("/formulas", func(r chi.Router) {
			r.Get("/active", h.HandleGetActiveFormula) // Active scoring formula
		})

		// What-if Analysis (API extension)
		r.Post("/score/what-if", h.HandleWhatIfScore) // Score with custom weights
	})
}
