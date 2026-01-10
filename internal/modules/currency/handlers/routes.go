package handlers

import (
	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all currency routes
func (h *Handler) RegisterRoutes(r chi.Router) {
	r.Route("/currency", func(r chi.Router) {
		// Conversion
		r.Get("/conversion-path/{from}/{to}", h.HandleGetConversionPath)
		r.Post("/convert", h.HandleConvert)
		r.Get("/available-currencies", h.HandleGetAvailableCurrencies)

		// Rate sources
		r.Get("/rates/sources", h.HandleGetRateSources)
		r.Get("/rates/staleness", h.HandleGetRateStaleness)
		r.Get("/rates/fallback-chain", h.HandleGetFallbackChain)
		r.Post("/rates/sync", h.HandleSyncRates)

		// Balances
		r.Get("/balances", h.HandleGetBalances)
		r.Post("/balance-check", h.HandleBalanceCheck)
		r.Post("/conversion-requirements", h.HandleConversionRequirements)
	})
}
