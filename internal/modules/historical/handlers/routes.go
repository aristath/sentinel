package handlers

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all historical data routes
func (h *Handler) RegisterRoutes(r chi.Router) {
	r.Route("/historical", func(r chi.Router) {
		// Price endpoints
		r.Route("/prices", func(r chi.Router) {
			r.Get("/daily/{isin}", func(w http.ResponseWriter, r *http.Request) {
				isin := chi.URLParam(r, "isin")
				h.HandleGetDailyPrices(w, r, isin)
			})
			r.Get("/monthly/{isin}", func(w http.ResponseWriter, r *http.Request) {
				isin := chi.URLParam(r, "isin")
				h.HandleGetMonthlyPrices(w, r, isin)
			})
			r.Get("/latest/{isin}", func(w http.ResponseWriter, r *http.Request) {
				isin := chi.URLParam(r, "isin")
				h.HandleGetLatestPrice(w, r, isin)
			})
			r.Get("/range", h.HandleGetPriceRange)
		})

		// Returns endpoints
		r.Route("/returns", func(r chi.Router) {
			r.Get("/daily/{isin}", func(w http.ResponseWriter, r *http.Request) {
				isin := chi.URLParam(r, "isin")
				h.HandleGetDailyReturns(w, r, isin)
			})
			r.Get("/monthly/{isin}", func(w http.ResponseWriter, r *http.Request) {
				isin := chi.URLParam(r, "isin")
				h.HandleGetMonthlyReturns(w, r, isin)
			})
			r.Get("/correlation-matrix", h.HandleGetCorrelationMatrix)
		})

		// Exchange rates endpoints
		r.Route("/exchange-rates", func(r chi.Router) {
			r.Get("/history", h.HandleGetExchangeRateHistory)
			r.Get("/current", h.HandleGetCurrentExchangeRates)
			r.Get("/{from}/{to}", func(w http.ResponseWriter, r *http.Request) {
				from := chi.URLParam(r, "from")
				to := chi.URLParam(r, "to")
				h.HandleGetExchangeRate(w, r, from, to)
			})
		})
	})
}
