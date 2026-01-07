package handlers

import (
	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all display routes
func (h *Handlers) RegisterRoutes(r chi.Router) {
	// Display routes (faithful translation of Python display service)
	r.Route("/display", func(r chi.Router) {
		r.Get("/state", h.HandleGetState) // Get current display state
		r.Post("/text", h.HandleSetText)  // Set display text
		r.Post("/led3", h.HandleSetLED3)  // Set LED3 color
		r.Post("/led4", h.HandleSetLED4)  // Set LED4 color
	})
}
