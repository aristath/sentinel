package handlers

import (
	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all quantum routes
func (h *Handler) RegisterRoutes(r chi.Router) {
	r.Route("/quantum", func(r chi.Router) {
		r.Post("/amplitude", h.HandleCalculateAmplitude)
		r.Post("/interference", h.HandleCalculateInterference)
		r.Post("/probability", h.HandleCalculateProbability)
		r.Get("/energy-levels", h.HandleGetEnergyLevels)
		r.Post("/multimodal-correction", h.HandleCalculateMultimodalCorrection)
	})
}
