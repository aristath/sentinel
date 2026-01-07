package handlers

import (
	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all allocation routes
func (h *Handler) RegisterRoutes(r chi.Router) {
	r.Route("/allocation", func(r chi.Router) {
		r.Get("/targets", h.HandleGetTargets)
		r.Get("/current", h.HandleGetCurrentAllocation)
		r.Get("/deviations", h.HandleGetDeviations)

		// Group management
		r.Get("/groups/country", h.HandleGetCountryGroups)
		r.Get("/groups/industry", h.HandleGetIndustryGroups)
		r.Put("/groups/country", h.HandleUpdateCountryGroup)
		r.Put("/groups/industry", h.HandleUpdateIndustryGroup)
		r.Delete("/groups/country/{group_name}", h.HandleDeleteCountryGroup)
		r.Delete("/groups/industry/{group_name}", h.HandleDeleteIndustryGroup)

		// Available options
		r.Get("/groups/available/countries", h.HandleGetAvailableCountries)
		r.Get("/groups/available/industries", h.HandleGetAvailableIndustries)

		// Group allocation and targets
		r.Get("/groups/allocation", h.HandleGetGroupAllocation)
		r.Put("/groups/targets/country", h.HandleUpdateCountryGroupTargets)
		r.Put("/groups/targets/industry", h.HandleUpdateIndustryGroupTargets)
	})
}
