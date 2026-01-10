package handlers

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all risk metrics routes
func (h *Handler) RegisterRoutes(r chi.Router) {
	r.Route("/risk", func(r chi.Router) {
		// Portfolio risk endpoints
		r.Route("/portfolio", func(r chi.Router) {
			r.Get("/var", h.HandleGetPortfolioVaR)
			r.Get("/cvar", h.HandleGetPortfolioCVaR)
			r.Get("/volatility", h.HandleGetPortfolioVolatility)
			r.Get("/sharpe", h.HandleGetPortfolioSharpe)
			r.Get("/sortino", h.HandleGetPortfolioSortino)
			r.Get("/max-drawdown", h.HandleGetPortfolioMaxDrawdown)
		})

		// Security risk endpoints
		r.Route("/securities/{isin}", func(r chi.Router) {
			r.Get("/volatility", func(w http.ResponseWriter, r *http.Request) {
				isin := chi.URLParam(r, "isin")
				h.HandleGetSecurityVolatility(w, r, isin)
			})
			r.Get("/sharpe", func(w http.ResponseWriter, r *http.Request) {
				isin := chi.URLParam(r, "isin")
				h.HandleGetSecuritySharpe(w, r, isin)
			})
			r.Get("/sortino", func(w http.ResponseWriter, r *http.Request) {
				isin := chi.URLParam(r, "isin")
				h.HandleGetSecuritySortino(w, r, isin)
			})
			r.Get("/max-drawdown", func(w http.ResponseWriter, r *http.Request) {
				isin := chi.URLParam(r, "isin")
				h.HandleGetSecurityMaxDrawdown(w, r, isin)
			})
			r.Get("/beta", func(w http.ResponseWriter, r *http.Request) {
				isin := chi.URLParam(r, "isin")
				h.HandleGetSecurityBeta(w, r, isin)
			})
		})

		// Kelly sizing endpoints
		r.Get("/kelly-sizes", h.HandleGetKellySizes)
		r.Get("/kelly-sizes/{isin}", func(w http.ResponseWriter, r *http.Request) {
			isin := chi.URLParam(r, "isin")
			h.HandleGetKellySize(w, r, isin)
		})
	})
}
