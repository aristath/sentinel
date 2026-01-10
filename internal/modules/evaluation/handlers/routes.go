package handlers

import (
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
)

// RegisterRoutes registers all evaluation routes
// Special case: routes are mounted at /api/v1 for Python client compatibility
func (h *Handler) RegisterRoutes(r chi.Router) {
	// Mount routes under /api/v1 for Python client compatibility
	r.Route("/api/v1", func(r chi.Router) {
		// Increase timeout for heavy evaluation operations
		r.Use(middleware.Timeout(120 * time.Second))

		r.Route("/evaluate", func(r chi.Router) {
			r.Post("/batch", h.HandleEvaluateBatch)
			r.Post("/single", h.HandleEvaluateSingle)
			r.Post("/compare", h.HandleEvaluateCompare)
			r.Post("/monte-carlo", h.HandleMonteCarlo)
			r.Post("/stochastic", h.HandleStochastic)
		})

		r.Route("/evaluation", func(r chi.Router) {
			r.Get("/criteria", h.HandleGetEvaluationCriteria)
		})

		r.Route("/simulate", func(r chi.Router) {
			r.Post("/batch", h.HandleSimulateBatch)
			r.Post("/custom-prices", h.HandleSimulateCustomPrices)
		})

		r.Route("/monte-carlo", func(r chi.Router) {
			r.Post("/advanced", h.HandleMonteCarloAdvanced)
		})
	})
}
